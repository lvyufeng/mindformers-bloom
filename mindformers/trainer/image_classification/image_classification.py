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
"""Image Classification Trainer."""
from typing import Optional, List, Union

import numpy as np
from PIL.Image import Image

from mindspore.train import Callback
from mindspore.nn import TrainOneStepCell, Optimizer
from mindspore import Tensor

from mindformers.dataset import BaseDataset
from mindformers.models import BaseModel, BaseImageProcessor
from mindformers.pipeline import pipeline
from mindformers.tools.logger import logger
from mindformers.tools.utils import count_params
from mindformers.tools.image_tools import load_image
from mindformers.tools.register import MindFormerRegister, \
    MindFormerModuleType, MindFormerConfig
from ..base_trainer import BaseTrainer


__all__ = ['ImageClassificationTrainer']


@MindFormerRegister.register(MindFormerModuleType.TRAINER, alias="image_classification")
class ImageClassificationTrainer(BaseTrainer):
    r"""ImageClassification Task For Trainer.
    Args:
        model_name (str): The model name of Task-Trainer. Default: None

        Examples:
            >>> import numpy as np
            >>> from mindspore.dataset import GeneratorDataset
            >>> from mindspore.nn import AdamWeightDecay, WarmUpLR, \
            ...      DynamicLossScaleUpdateCell, TrainOneStepWithLossScaleCell, Accuracy
            >>> from mindformers.trainer import ImageClassificationTrainer
            >>> from mindformers.tools.register import MindFormerConfig
            >>> from mindformers.models import ViTForImageClassification, ViTConfig, VitImageProcessor
            >>> class MyDataLoader:
            ...    def __init__(self):
            ...        self._data = [np.zeros((3, 224, 224), np.float32) for _ in range(64)]
            ...        self._label = [np.ones(1000, np.float32) for _ in range(64)]
            ...
            ...    def __getitem__(self, index):
            ...        return self._data[index], self._label[index]
            ...
            ...    def __len__(self):
            ...        return len(self._data)
            >>> dataset = GeneratorDataset(source=MyDataLoader(), column_names=['image', 'label'])
            >>> dataset = dataset.batch(batch_size=2)
            >>> #1) use config to train
            >>> cls_task = ImageClassificationTrainer(model_name='vit_base_p16')
            >>> cls_task.train()
            >>> cls_task.evaluate(dataset=dataset)
            >>> input_data = np.uint8(np.random.random((5, 3, 255, 255)))
            >>> cls_task.predict(input_data=input_data, top_k=5)
            >>> #2) use instance function to train
            >>> vit_config = ViTConfig(batch_size=2)
            >>> network_with_loss = ViTForImageClassification(vit_config)
            >>> lr_schedule = WarmUpLR(learning_rate=0.001, warmup_steps=100)
            >>> optimizer = AdamWeightDecay(beta1=0.009, beta2=0.999,
            ...                             learning_rate=lr_schedule,
            ...                             params=network_with_loss.trainable_params())
            >>> loss_scale = DynamicLossScaleUpdateCell(loss_scale_value=2**12, scale_factor=2, scale_window=1000)
            >>> wrapper = TrainOneStepWithLossScaleCell(network_with_loss, optimizer, scale_sense=loss_scale)
            >>> cls_task.train(wrapper=wrapper, dataset=dataset)
            >>> compute_metrics = {"Accuracy": Accuracy(eval_type='classification')}
            >>> cls_task.evaluate(network=network_with_loss, dataset=dataset, compute_metrics=compute_metrics)
            >>> image_processor = VitImageProcessor(image_resolution=224)
            >>> cls_task.predict(input_data=input_data, image_processor=image_processor, top_k=5)

    Raises:
        NotImplementedError: If train method or evaluate method or predict method not implemented.
    """

    def __init__(self, model_name: str = None):
        super().__init__('image_classification', model_name)

    def train(self,
              config: Optional[Union[dict, MindFormerConfig]] = None,
              network: Optional[Union[str, BaseModel]] = None,
              dataset: Optional[Union[str, BaseDataset]] = None,
              wrapper: Optional[TrainOneStepCell] = None,
              optimizer: Optional[Optimizer] = None,
              callbacks: Optional[Union[Callback, List[Callback]]] = None,
              **kwargs):
        r"""Train task for ImageClassification Trainer.
        This function is used to train or fine-tune the network.

        The trainer interface is used to quickly start training for general task.
        It also allows users to customize the network, optimizer, dataset, wrapper, callback.

        Args:
            config (Optional[Union[dict, MindFormerConfig]]): The task config which is used to
                configure the dataset, the hyper-parameter, optimizer, etc.
                It support config dict or MindFormerConfig class.
                Default: None.
            network (Optional[Union[str, BaseModel]]): The network for trainer. It support model name supported
                or BaseModel class. Supported model name can refer to ****.
                Default: None.
            dataset (Optional[Union[str, BaseDataset]]): The training dataset. It support real dataset path or
                BaseDateset class or MindSpore Dataset class.
                Default: None.
            optimizer (Optional[Optimizer]): The training network's optimizer. It support Optimizer class of MindSpore.
                Default: None.
            wrapper (Optional[TrainOneStepCell]): Wraps the `network` with the `optimizer`.
                It support TrainOneStepCell class of MindSpore.
                Default: None.
            callbacks (Optional[Union[Callback, List[Callback]]]): The training callback function.
                It support CallBack or CallBack List of MindSpore.
                Default: None.

        Raises:
            NotImplementedError: If wrapper not implemented.
        """
        super().train(
            config=config,
            network=network,
            callbacks=callbacks,
            dataset=dataset,
            wrapper=wrapper,
            optimizer=optimizer,
            **kwargs)

    def evaluate(self,
                 config: Optional[Union[dict, MindFormerConfig]] = None,
                 network: Optional[Union[str, BaseModel]] = None,
                 dataset: Optional[Union[str, BaseDataset]] = None,
                 callbacks: Optional[Union[Callback, List[Callback]]] = None,
                 compute_metrics: Optional[Union[dict, set]] = None,
                 **kwargs):
        r"""Evaluate task for ImageClassification Trainer.
        This function is used to evaluate the network.

        The trainer interface is used to quickly start training for general task.
        It also allows users to customize the network, dataset, callbacks, compute_metrics.

        Args:
            config (Optional[Union[dict,MindFormerConfig]]): The task config which is used to
                configure the dataset, the hyper-parameter, optimizer, etc.
                It support config dict or MindFormerConfig class.
                Default: None.
            network (Optional[Union[str, BaseModel]]): The network for trainer. It support model name supported
                or BaseModel class. Supported model name can refer to ****.
                Default: None.
            dataset (Optional[Union[str, BaseDataset]]): The training dataset. It support real dataset path or
                BaseDateset class or MindSpore Dataset class.
                Default: None.
            callbacks (Optional[Union[Callback, List[Callback]]]): The training callback function.
                It support CallBack or CallBack List of MindSpore.
                Default: None.
            compute_metrics (Optional[Union[dict, set]]): The metric of evaluating.
                It support dict or set in MindSpore's Metric class.
                Default: None.
        """
        metric_name = "Top1 Accuracy"
        kwargs.setdefault("metric_name", metric_name)
        super().evaluate(
            config=config,
            network=network,
            dataset=dataset,
            compute_metrics=compute_metrics,
            callbacks=callbacks,
            **kwargs
        )

    def predict(self,
                config: Optional[Union[dict, MindFormerConfig]] = None,
                input_data: Optional[Union[Tensor, np.ndarray, Image, str, list]] = None,
                network: Optional[Union[str, BaseModel]] = None,
                image_processor: Optional[BaseImageProcessor] = None, **kwargs):
        r"""Predict task for ImageClassification Trainer.
        This function is used to predict the network.

        The trainer interface is used to quickly start training for general task.
        It also allows users to customize the network, tokenizer, image_processor, audio_processor.

        Args:
            config (Optional[Union[dict]]): The task config which is used to
                configure the dataset, the hyper-parameter, optimizer, etc.
                It support config dict or MindFormerConfig class.
                Default: None.
            input_data (Optional[Union[Tensor, np.ndarray, Image, str, list]]): The predict data. Default: None.
            network (Optional[Union[str, BaseModel]]): The network for trainer. It support model name supported
                or BaseModel class. Supported model name can refer to ****.
                Default: None.
            image_processor (Optional[BaseImageProcessor]): The processor for image preprocessing.
                It support BaseImageProcessor class.
                Default: None.
        """
        self.kwargs = kwargs
        config = self.set_config(config)

        logger.info(".........Build Input Data For Predict..........")
        if input_data is None:
            input_data = config.input_data
        if not isinstance(input_data, (Tensor, np.ndarray, Image, str, list)):
            raise ValueError("Input data's type must be one of "
                             "[str, ms.Tensor, np.ndarray, PIL.Image.Image, list]")
        batch_input_data = []
        if isinstance(input_data, str):
            batch_input_data.append(load_image(input_data))
        elif isinstance(input_data, list):
            for data_path in input_data:
                batch_input_data.append(load_image(data_path))
        else:
            batch_input_data = input_data

        logger.info(".........Build Net For Predict..........")
        if network is None:
            network = self.create_network()
        logger.info("Network Parameters: %s M.", str(count_params(network)))

        logger.info(".........Build Image Processor For Predict..........")
        if image_processor is None:
            image_processor = self.create_image_processor()

        pipeline_task = pipeline(task='image_classification',
                                 model=network,
                                 image_processor=image_processor, **kwargs)
        output_result = pipeline_task(batch_input_data)
        logger.info("output result is: %s", str(output_result))
        logger.info(".........Predict Over!.............")
        return output_result
