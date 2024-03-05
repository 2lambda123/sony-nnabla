# Copyright 2018,2019,2020,2021 Sony Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
import numpy as np
import nnabla as nn
import nnabla.functions as F
from nbla_test_utils import list_context
from nnabla.testing import assert_allclose

ctxs = list_context('ClipByValue')


def ref_clip_by_value(x, min_, max_):
    if np.isscalar(min_):
        min_ = min_ * np.ones(x.shape)
    min_idx = np.where(x < min_)
    x[min_idx] = min_[min_idx]

    if np.isscalar(max_):
        max_ = max_ * np.ones(x.shape)
    max_idx = np.where(x > max_)
    x[max_idx] = max_[max_idx]
    return x


def convert(value, dtype):
    converter = dtype if dtype in (
        float, np.array) else dtype.from_numpy_array
    return converter(value)


@pytest.mark.parametrize("seed", [313])
@pytest.mark.parametrize("shape", [(2, 8, 8, 8), (2, 3)])
@pytest.mark.parametrize("dtype", [nn.Variable, nn.NdArray, float, np.array])
def test_clip_by_value_forward(seed, shape, dtype):
    rng = np.random.RandomState(seed)
    x_data = rng.randn(*shape)
    x = nn.Variable.from_numpy_array(x_data)
    if dtype is float:
        min_data = rng.randn()
        max_data = rng.randn()
    else:
        min_data = rng.randn(*shape)
        max_data = rng.randn(*shape)
    min_ = convert(min_data, dtype)
    max_ = convert(max_data, dtype)

    if dtype is not np.array:
        with nn.auto_forward(True):
            y = F.clip_by_value(x, min_, max_)
        y_ref = ref_clip_by_value(x_data, min_data, max_data)

        if dtype in (nn.Variable, float):
            assert_allclose(y.d, y_ref)
        elif dtype is nn.NdArray:
            assert_allclose(y.data, y_ref)
    else:
        with pytest.raises(TypeError):
            y = F.clip_by_value(x, min_data, max_data)


@pytest.mark.parametrize("ctx, func_name", ctxs)
@pytest.mark.parametrize("seed", [313])
@pytest.mark.parametrize("shape,reset_shape", [((2, 8, 8, 8), (2, 6, 6, 6))])
def test_clip_by_value_forward_with_reset(ctx, func_name, seed, shape, reset_shape):
    rng = np.random.RandomState(seed)
    x_data = rng.randn(*shape)
    x = nn.Variable.from_numpy_array(x_data)
    reset_x_data = rng.randn(*reset_shape)

    min_data = rng.randn(*shape)
    max_data = rng.randn(*shape)
    reset_min_data = rng.randn(*reset_shape)
    reset_max_data = rng.randn(*reset_shape)
    min_ = convert(min_data, nn.Variable)
    max_ = convert(max_data, nn.Variable)
    y_ref = ref_clip_by_value(reset_x_data, reset_min_data, reset_max_data)
    with nn.context_scope(ctx):
        y = F.clip_by_value(x, min_, max_)
    # forward
    y.forward()
    # reset and forward
    x.reset_shape(reset_shape, True)
    x.d = reset_x_data
    min_.reset_shape(reset_shape, True)
    max_.reset_shape(reset_shape, True)
    min_.d = reset_min_data
    max_.d = reset_max_data
    y.forward()
    assert_allclose(y.d, y_ref)
