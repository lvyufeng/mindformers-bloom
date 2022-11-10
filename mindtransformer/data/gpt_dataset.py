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

"""
Create dataset for training and evaluating
"""

import os
import mindspore.dataset as ds
import mindspore.dataset.transforms.c_transforms as C
import mindspore.common.dtype as mstype

ds.config.set_seed(1)


def create_gpt_dataset(config):
    """Create gpt dataset"""
    device_num = config.dataset_device_num
    rank = config.dataset_rank
    batch_size = config.dataset_batch_size
    data_path = config.dataset_path
    drop = config.dataset_drop_remainder

    home_path = os.path.join(os.getcwd(), data_path)
    data = [os.path.join(home_path, name) for name in os.listdir(data_path) if name.endswith("mindrecord")]
    print(data)
    dataset = ds.MindDataset(data, columns_list=["text"], shuffle=True, num_shards=device_num, shard_id=rank)
    type_cast_op = C.TypeCast(mstype.int32)
    dataset = dataset.map(input_columns="text", operations=type_cast_op)
    dataset = dataset.batch(batch_size, drop_remainder=drop)
    return dataset