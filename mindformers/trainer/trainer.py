# Copyright 2022 Huawei Technologies Co., Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============================================================================
"""Trainer API For Import."""
import os
import shutil
from pprint import pprint
from collections import OrderedDict
from typing import List, Optional, Union

import numpy as np
from PIL.Image import Image

from mindspore import Tensor
from mindspore.common import set_seed
from mindspore.nn import TrainOneStepCell, Optimizer
from mindspore.train import Callback
from mindspore import load_param_into_net, load_checkpoint

from mindformers.mindformer_book import MindFormerBook
from mindformers.tools.register import MindFormerConfig, MindFormerRegister
from mindformers.models import build_model, build_tokenizer, build_feature_extractor, \
    BaseModel, BaseFeatureExtractor, BaseTokenizer
from mindformers.dataset import build_dataset, build_dataset_loader, \
    check_dataset_config, BaseDataset
from mindformers.wrapper import build_wrapper
from mindformers.common.optim import build_optim
from mindformers.common.lr import build_lr
from mindformers.common.callback import build_callback
from mindformers.common.parallel_config import build_parallel_config
from mindformers.tools.cloud_adapter import CFTS
from mindformers.tools.logger import logger
from mindformers.tools.utils import count_params
from mindformers.tools.image_tools import load_image
from mindformers.tools.register.config import ordered_yaml_dump

from .build_trainer import build_trainer
from .config_args import ConfigArguments
from .utils import check_train_data_loader_type, check_eval_data_loader_type, \
    check_optimizer_and_lr_type, check_wrapper_config, config2dict


__all__ = ['Trainer']


SUPPORT_TASKS = MindFormerBook().get_trainer_support_task_list()
SUPPORT_MODEL_NAMES = MindFormerBook().get_model_name_support_list()
SUPPORT_PIPELINES = MindFormerBook().get_pipeline_support_task_list()
SUPPORT_PIPELINE_INPUT_DATA = MindFormerBook().get_pipeline_support_input_data_list()
CURRENT_PROJECT_PATH = MindFormerBook().get_project_path()
DEFAULT_CHECKPOINT_DIR = 'checkpoint'
DEFAULT_CONFIG_DIR = 'configs'


class Trainer:
    """Trainer API."""
    def __init__(self,
                 config: Optional[Union[str, dict, ConfigArguments]] = None,
                 task_name: Optional[str] = 'general',
                 model: Optional[Union[str, BaseModel]] = None,
                 train_dataset: Optional[Union[str, BaseDataset]] = None,
                 eval_dataset: Optional[Union[str, BaseDataset]] = None,
                 tokenizer: Optional[BaseTokenizer] = None,
                 feature_extractor: Optional[BaseFeatureExtractor] = None,
                 optimizers: Optional[Optimizer] = None,
                 wrapper: Optional[TrainOneStepCell] = None,
                 callbacks: Optional[Union[Callback, List[Callback]]] = None,
                 compute_metrics: Optional[Union[dict, set]] = None,
                 save_config: bool = False,
                 **kwargs):

        self.task_name = task_name
        self.model = model
        self.train_dataset = train_dataset
        self.eval_dataset = eval_dataset
        self.optimizers = optimizers
        self.wrapper = wrapper
        self.tokenizer = tokenizer
        self.feature_extractor = feature_extractor
        self.callbacks = callbacks
        self.compute_metrics = compute_metrics
        self.configs_directory = os.path.join('.', DEFAULT_CONFIG_DIR)
        self.kwargs = kwargs

        if not os.path.exists(os.path.join('.', DEFAULT_CONFIG_DIR)):
            configs_directory = os.path.join('.', DEFAULT_CONFIG_DIR)
            if os.path.exists(os.path.join(CURRENT_PROJECT_PATH, DEFAULT_CONFIG_DIR)):
                mindformers_configs_directory = os.path.join(CURRENT_PROJECT_PATH, DEFAULT_CONFIG_DIR)
                shutil.copytree(mindformers_configs_directory, configs_directory)

        if wrapper is not None:
            if model is not None:
                logger.warning(
                    'wrapper has existed, input model invalid, it should be include in wrapper.')
            if optimizers is not None:
                logger.warning(
                    'wrapper has existed, input optimizers invalid, it should be include in wrapper.')

        assert task_name in SUPPORT_TASKS.keys(), \
            f"task name must be in {SUPPORT_TASKS.keys()}, but get {task_name}."
        if isinstance(model, str):
            assert model in SUPPORT_MODEL_NAMES, \
                f"model must be in {SUPPORT_MODEL_NAMES} when model's type is string, but get {model}."
            self.model_name = model
            self.model = None
        else:
            self.model_name = "common"

        task_config = MindFormerConfig(SUPPORT_TASKS.get(self.task_name).get(self.model_name))

        if self.model_name == "common":
            if self.model is not None:
                task_config.trainer.model_name = self.model.__class__.__name__
            if self.wrapper is not None:
                task_config.trainer.model_name = self.wrapper.network.__class__.__name__

        if config is None:
            self.config = task_config
        else:
            if isinstance(config, dict):
                task_config.merge_from_dict(config)
            elif isinstance(config, str):
                assert os.path.realpath(config) and os.path.exists(config), \
                    f"config path must be exist, but get {config}."
                assert config.endswith(('.yaml', '.yml')), \
                    f"config file must be end with .yaml or .yml, but get {config}"
                task_config = MindFormerConfig(config)
            elif isinstance(config, ConfigArguments):
                if hasattr(config, 'train_dataset'):
                    check_train_data_loader_type(config, task_config)
                if hasattr(config, 'eval_dataset'):
                    check_eval_data_loader_type(config, task_config)
                if hasattr(config, 'optimizer'):
                    check_optimizer_and_lr_type(config, task_config)
                if hasattr(config, 'runner_wrapper'):
                    check_wrapper_config(config, task_config)
                task_config.merge_from_dict(config.__dict__)

            self.config = task_config

        if save_config:
            self.save_config_to_yaml(self.config)
            logger.info("save running config success of %s_new.", task_config.trainer.model_name.lower())

        # check dataset config
        if isinstance(train_dataset, str):
            assert os.path.exists(train_dataset), \
                f"train dataset path must be exist, but get {train_dataset}."
            self.config.train_dataset.data_loader.dataset_dir = train_dataset
            self.train_dataset = None
        if isinstance(eval_dataset, str):
            assert os.path.exists(eval_dataset), \
                f"eval dataset path must be exist, but get {eval_dataset}."
            self.config.eval_dataset.data_loader.dataset_dir = eval_dataset
            self.eval_dataset = None

        if tokenizer is not None:
            if self.config.train_dataset is not None:
                self.config.train_dataset.tokenizer = tokenizer
            if self.config.eval_dataset is not None:
                self.config.eval_dataset.tokenizer = tokenizer
        check_dataset_config(self.config)

        # build parallel config
        self.rank_id = int(os.getenv("RANK_ID", "0"))
        self.context_config = self.config.context
        self.parallel_config = self.config.parallel
        build_parallel_config(self.config)

        # set cloud file transform for ModelArts.
        cfts = CFTS(**self.config.aicc_config)
        MindFormerRegister.register_cls(cfts, alias='cfts')

        # set seed
        set_seed(self.config.seed)
        np.random.seed(self.config.seed)

        # set output directory
        os.environ.setdefault("LOCAL_DEFAULT_PATH", self.config.output_dir)

        # pprint last config
        pprint(self.config)

    def train(self, resume_from_checkpoint: Optional[Union[str, bool]] = None,
              initial_epoch: int = 0, do_eval: bool = False, **kwargs):
        """train."""
        if resume_from_checkpoint is False:
            resume_from_checkpoint = None

        if self.train_dataset is None:
            self.train_dataset = build_dataset(self.config.train_dataset_task)

        if do_eval:
            if self.eval_dataset is None:
                self.eval_dataset = build_dataset(self.config.eval_dataset_task)

        if self.model is None and self.wrapper is None:
            if resume_from_checkpoint is True or isinstance(resume_from_checkpoint, str):
                if isinstance(resume_from_checkpoint, str) and resume_from_checkpoint in SUPPORT_MODEL_NAMES:
                    self.config.model.model_config.checkpoint_name_or_path = resume_from_checkpoint
                else:
                    self.config.model.model_config.checkpoint_name_or_path = None
            self.model = build_model(self.config.model)

        if self.optimizers is None and self.wrapper is None:
            self.optimizers = self.create_optimizer_and_scheduler()

        if self.wrapper is None:
            self.wrapper = self.create_train_one_step_wrapper()

        if self.callbacks is None:
            self.callbacks = self.create_callbacks()

        self.load_checkpoint(resume_from_checkpoint)
        if initial_epoch != 0:
            self.config.runner_config.initial_epoch = initial_epoch

        trainer = build_trainer(self.config.trainer)
        trainer.train(
            config=self.config, network=self.model,
            dataset=self.train_dataset, optimizer=self.optimizers,
            eval_dataset=self.eval_dataset if do_eval else None,
            wrapper=self.wrapper,
            callbacks=self.callbacks, **kwargs)

    def evaluate(self, eval_checkpoint: Optional[Union[str, bool]] = None, **kwargs):
        """eval."""
        if eval_checkpoint is False:
            eval_checkpoint = None

        if self.eval_dataset is None:
            self.eval_dataset = build_dataset(self.config.eval_dataset_task)

        if self.model is None:
            if eval_checkpoint is True or isinstance(eval_checkpoint, str):
                self.config.model.model_config.checkpoint_name_or_path = None
            self.model = build_model(self.config.model)

        if self.callbacks is None:
            self.callbacks = self.create_callbacks()

        filter_prefix = ["adam_v", "adam_m", "epoch_num", "step_num", "global_step"]
        self.load_checkpoint(eval_checkpoint, filter_prefix=filter_prefix, is_train=False)

        trainer = build_trainer(self.config.trainer)
        trainer.evaluate(
            config=self.config, network=self.model,
            dataset=self.eval_dataset, callbacks=self.callbacks, **kwargs)

    def predict(self,
                predict_checkpoint: Optional[Union[str, bool]] = None,
                input_data: Optional[Union[Tensor, np.ndarray, Image, str, list]] = None, **kwargs):
        """predict."""
        if self.task_name not in SUPPORT_PIPELINES.keys():
            raise NotImplementedError(f"The {self.task_name} not support predict, "
                                      f"now this tasks {SUPPORT_PIPELINES.keys()} is support predict.")

        if predict_checkpoint is False:
            predict_checkpoint = None

        if input_data is None:
            input_data = load_image(SUPPORT_PIPELINE_INPUT_DATA.get(self.task_name))
        assert isinstance(input_data, (Tensor, np.ndarray, Image, str, list)), \
            "Input data's type must be one of [str, ms.Tensor, np.ndarray, PIL.Image.Image]"

        if self.model is None:
            if predict_checkpoint is True or isinstance(predict_checkpoint, str):
                self.config.model.model_config.checkpoint_name_or_path = None
            self.model = build_model(self.config.model)

        if self.tokenizer is None:
            self.tokenizer = build_tokenizer(self.config.processor.tokenizer)

        if self.feature_extractor is None:
            self.feature_extractor = build_feature_extractor(self.config.processor.feature_extractor)

        filter_prefix = ["adam_v", "adam_m", "epoch_num", "step_num", "global_step"]
        self.load_checkpoint(predict_checkpoint, filter_prefix=filter_prefix, is_train=False)

        trainer = build_trainer(self.config.trainer)
        output_result = trainer.predict(
            config=self.config, input_data=input_data,
            network=self.model, feature_extractor=self.feature_extractor,
            tokenizer=self.tokenizer, **kwargs)
        return output_result

    def create_optimizer_and_scheduler(self):
        """create_optimizer_and_scheduler."""
        lr_schedule = self.create_scheduler()
        params = self.model.trainable_params()
        return self.create_optimizer(lr_schedule, params)

    def create_scheduler(self):
        """create_scheduler."""
        return build_lr(self.config.lr_schedule)

    def create_optimizer(self, lr_schedule, params):
        """create_optimizer."""
        if lr_schedule is not None:
            return build_optim(self.config.optimizer, default_args={"params": params,
                                                                    "learning_rate": lr_schedule})
        assert self.config.optimizer.learning_rate, "learning_rate must be input"
        return build_optim(self.config.optimizer, default_args={"params": params})

    def create_train_one_step_wrapper(self):
        """create_train_one_step_wrapper."""
        if self.model is not None and self.optimizers is not None:
            return build_wrapper(
                self.config.wrapper,
                default_args={"network": self.model, "optimizer": self.optimizers})
        return None

    def create_callbacks(self):
        """create_callbacks."""
        return build_callback(self.config.callbacks)

    def set_parallel_config(
            self, data_parallel=1, model_parallel=1, expert_parallel=1, pipeline_stage=1,
            micro_batch_num=1, optimizer_shard=False, gradient_aggregation_group=4, vocab_emb_dp=True):
        """set_parallel_config."""
        self.config.parallel_config.data_parallel = data_parallel
        self.config.parallel_config.model_parallel = model_parallel
        self.config.parallel_config.expert_parallel = expert_parallel
        self.config.parallel_config.pipeline_stage = pipeline_stage
        self.config.parallel_config.optimizer_shard = optimizer_shard
        self.config.parallel_config.micro_batch_num = micro_batch_num
        self.config.parallel_config.vocab_emb_dp = vocab_emb_dp
        self.config.parallel_config.gradient_aggregation_group = gradient_aggregation_group

    def set_recompute_config(self, recompute=False, parallel_optimizer_comm_recompute=False,
                             mp_comm_recompute=True, recompute_slice_activation=False):
        """set_recompute_config."""
        self.config.recompute_config.recompute = recompute
        self.config.recompute_config.parallel_optimizer_comm_recompute = parallel_optimizer_comm_recompute
        self.config.recompute_config.mp_comm_recompute = mp_comm_recompute
        self.config.recompute_config.recompute_slice_activation = recompute_slice_activation

    def set_moe_config(self, expert_num=1, capacity_factor=1.1, aux_loss_factor=0.05, num_experts_chosen=1):
        """set_moe_config."""
        self.config.moe_config.expert_num = expert_num
        self.config.moe_config.capacity_factor = capacity_factor
        self.config.moe_config.aux_loss_factor = aux_loss_factor
        self.config.moe_config.num_experts_chosen = num_experts_chosen

    def get_train_dataloader(self):
        """get_train_dataloader."""
        return build_dataset_loader(self.config.train_dataset.data_loader)

    def get_eval_dataloader(self):
        """get_eval_dataloader."""
        return build_dataset_loader(self.config.eval_dataset.data_loader)

    def compute_loss(self):
        """compute_loss."""

    def count_parameter(self):
        """count_parameter."""
        logger.info("%s parameter is: %s M",
                    self.config.trainer.model_name, str(count_params(self.model)))

    def load_checkpoint(self, model_checkpoint, filter_prefix=None, is_train=True):
        """Load Checkpoint."""
        if model_checkpoint is not None:
            if isinstance(model_checkpoint, bool):
                last_checkpoint = load_checkpoint(
                    self.get_last_checkpoint(), filter_prefix=filter_prefix)
                not_load_net_params = load_param_into_net(self.model, last_checkpoint)
                logger.info("not_load_net_params: %s", str(not_load_net_params))
                if is_train:
                    not_load_optim_params = load_param_into_net(self.optimizers, last_checkpoint)
                    logger.info("not_load_optim_params: %s", str(not_load_optim_params))
            elif isinstance(model_checkpoint, str):
                assert os.path.realpath(model_checkpoint) and os.path.exists(model_checkpoint), \
                    f"predict checkpoint must be correct and exist path, but get {model_checkpoint}"
                checkpoint = load_checkpoint(model_checkpoint, filter_prefix=filter_prefix)
                not_load_net_params = load_param_into_net(self.model, checkpoint)
                logger.info("not_load_net_params: %s", str(not_load_net_params))
                if is_train:
                    not_load_optim_params = load_param_into_net(self.optimizers, checkpoint)
                    logger.info("not_load_optim_params: %s", str(not_load_optim_params))
            else:
                raise KeyError("resume_from_checkpoint input type should be in [string(checkpoint path), bool],"
                               f"but get {model_checkpoint}")

    def get_last_checkpoint(self):
        """get last checkpoint for resuming."""
        output_folder = self.config.output_dir
        checkpoint_dir = os.path.join(
            output_folder, 'rank_{}'.format(self.rank_id), DEFAULT_CHECKPOINT_DIR)
        output_checkpoint_path = [
            checkpoint for checkpoint in os.listdir(checkpoint_dir)
            if checkpoint.endswith('.ckpt')
        ]
        if not output_checkpoint_path:
            return None
        output_checkpoint_path = sorted(output_checkpoint_path,
                                        key=lambda x: os.path.getmtime(os.path.join(checkpoint_dir, x)))
        return os.path.join(checkpoint_dir, output_checkpoint_path[-1])

    def save_config_to_yaml(self, config: dict = None):
        """save now config file to yaml file."""
        if config is None:
            config = self.config
        model_name = self.config.trainer.model_name
        config_dict = _reset_config_for_save(config, model_name)
        config_dir = os.path.join(
            self.configs_directory, model_name.lower() + '_new')
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)

        model_config_dir = os.path.join(config_dir, 'model_config')
        task_config_dir = os.path.join(config_dir, 'task_config')
        if not os.path.exists(model_config_dir):
            os.makedirs(model_config_dir, exist_ok=True)

        if not os.path.exists(task_config_dir):
            os.makedirs(task_config_dir, exist_ok=True)

        model_config_yaml_path = os.path.join(
            model_config_dir, '{}.yaml'.format(model_name.lower()))
        dataset_config_yaml_path = os.path.join(
            task_config_dir, '{}_dataset.yaml'.format(model_name.lower()))
        runner_yaml_path = os.path.join(task_config_dir, 'runner.yaml')
        context_yaml_path = os.path.join(task_config_dir, 'context.yaml')
        run_yaml_path = os.path.join(config_dir, 'run_{}.yaml'.format(model_name.lower()))

        _save_config_to_yaml(model_config_yaml_path, config_dict.get('model_config'))
        _save_config_to_yaml(dataset_config_yaml_path, config_dict.get('dataset_config'))
        _save_config_to_yaml(runner_yaml_path, config_dict.get('runner_config'))
        _save_config_to_yaml(context_yaml_path, config_dict.get('context_config'))
        _save_config_to_yaml(run_yaml_path, config_dict.get('run_config'))


def _save_config_to_yaml(save_file_path: str = None, save_config: dict = None):
    """Save Config to Yaml File."""
    if save_config is None:
        save_config = {}
    with open(save_file_path, 'w', encoding='utf-8') as file_pointer:
        file_pointer.write(
            ordered_yaml_dump(
                save_config,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False))


def _reset_config_for_save(config: dict = None, model_name: str = 'common'):
    """Reset Config According to Yaml File Number."""
    if config is None:
        config = {}
    config = config.copy()

    config_dict = {
        "model_config": OrderedDict(),
        "dataset_config": OrderedDict(),
        "runner_config": OrderedDict(),
        "context_config": OrderedDict(),
        "run_config": OrderedDict()
    }

    if config.get('model') is not None:
        model_config = config2dict(config.pop('model'))
        config_dict["model_config"].setdefault('model', model_config)

    if config.get('processor') is not None:
        processor_config = config2dict(config.config.pop('processor'))
        config_dict["model_config"].setdefault('processor', processor_config)

    if config.get('train_dataset_task') is not None and config.get('train_dataset') is not None:
        train_dataset_config = config2dict(config.pop('train_dataset'))
        train_dataset_task_config = config2dict(config.pop('train_dataset_task'))
        config_dict["dataset_config"].setdefault('train_dataset', train_dataset_config)
        config_dict["dataset_config"].setdefault('train_dataset_task', train_dataset_task_config)

    if config.get('eval_dataset_task') is not None and config.get('eval_dataset') is not None:
        eval_dataset_config = config2dict(config.pop('eval_dataset'))
        eval_dataset_task_config = config2dict(config.pop('eval_dataset_task'))
        config_dict["dataset_config"].setdefault('train_dataset', eval_dataset_config)
        config_dict["dataset_config"].setdefault('train_dataset_task', eval_dataset_task_config)

    if config.get('context') is not None:
        context_config = config2dict(config.pop('context'))
        parallel_context_config = config2dict(config.pop('parallel'))
        moe_conifg = config2dict(config.pop('moe_config'))
        recompute_config = config2dict(config.pop('recompute_config'))
        parallel_config = config2dict(config.pop('parallel_config'))
        config_dict['context_config'].setdefault('context', context_config)
        config_dict['context_config'].setdefault('parallel', parallel_context_config)
        config_dict['context_config'].setdefault('moe_conifg', moe_conifg)
        config_dict['context_config'].setdefault('recompute_config', recompute_config)
        config_dict['context_config'].setdefault('parallel_config', parallel_config)

    if config.get('runner_config') is not None:
        runner_config = config2dict(config.pop('runner_config'))
        config_dict['runner_config'].setdefault('runner_config', runner_config)

    if config.get('runner_wrapper') is not None:
        wrapper_config = config2dict(config.pop('runner_wrapper'))
        config_dict['runner_config'].setdefault('runner_wrapper', wrapper_config)

    if config.get('optimizer') is not None:
        optim_config = config2dict(config.pop('optimizer'))
        config_dict['runner_config'].setdefault('optimizer', optim_config)

    if config.get('lr_schedule') is not None:
        lr_config = config2dict(config.pop('lr_schedule'))
        config_dict['runner_config'].setdefault('lr_schedule', lr_config)

    if config.get('callbacks') is not None:
        cb_config = config2dict(config.pop('callbacks'))
        config_dict['runner_config'].setdefault('callbacks', cb_config)

    config_dict['run_config'].setdefault('base_config', [
        './task_config/context.yaml',
        './task_config/runner.yaml',
        './task_config/{}_dataset.yaml'.format(model_name.lower()),
        './model_config/{}.yaml'.format(model_name.lower())])

    run_config = config2dict(config)
    for key, value in run_config.items():
        config_dict['run_config'].setdefault(key, value)

    return config_dict
