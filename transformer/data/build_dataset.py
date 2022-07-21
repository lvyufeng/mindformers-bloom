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
Data operations.
"""
from transformer.utils import download_data

from .dataset import create_dataset

def build_dataset(opt, rank_id, device_num):
    """get dataset from local or obs"""
    if opt.data_url.startswith == "s3://":
        # copy data from the cloud to the /cache/Data
        cache_url = '/cache/Data/'
        download_data(src_data_url=opt.data_url, tgt_data_path=cache_url, rank=rank_id)
    else:
        cache_url = opt.data_url

    ds = create_dataset(opt.model['global_batch_size'], data_path=cache_url, device_num=device_num, rank=rank_id)

    return ds