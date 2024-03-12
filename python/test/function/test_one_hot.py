# Copyright 2017,2018,2019,2020,2021 Sony Corporation.
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

ctxs = list_context('OneHot')


def ref_one_hot(x, shape):
    num_classes = shape
    result = np.zeros((x.shape[0],) + shape)
    for i in range(x.shape[0]):
        class_idxs = []
        valid_class = True
        for class_idx, num_classes in zip(x[i], shape):
            if class_idx < 0:
                class_idx += num_classes
            if class_idx < 0 or num_classes <= class_idx:
                valid_class = False
                break
            class_idxs.append(class_idx)
        idx = (i, ) + tuple(class_idxs)
        if valid_class:
            result[idx] = 1
    return result


@pytest.mark.parametrize("ctx, func_name", ctxs)
@pytest.mark.parametrize("seed", [313])
@pytest.mark.parametrize("inshape", [(100, 1), (100, 2)])
@pytest.mark.parametrize("shape", [(10, ), (10, 8)])
def test_one_hot_forward(seed, inshape, shape, ctx, func_name):
    # Input
    input = np.zeros(inshape, dtype=int)
    rng = np.random.RandomState(seed)

    if len(shape) != inshape[-1]:
        # input inshape and shape don't match.
        with pytest.raises(RuntimeError):
            y = F.one_hot(nn.Variable(input.shape), shape)
    else:
        for i in range(inshape[-1]):
            # this input data contains out-of-range class index.
            num_classes = shape[i]
            low = -2 * num_classes
            high = 2 * num_classes
            input[:, i] = rng.randint(low, high, size=inshape[0])
        vinput = nn.Variable(input.shape, need_grad=False)
        vinput.d = input

        with nn.context_scope(ctx), nn.auto_forward():
            o = F.one_hot(vinput, shape)
        r = ref_one_hot(input, shape)
        assert_allclose(o.d, r)
        assert func_name == o.parent.name


@pytest.mark.parametrize("ctx, func_name", ctxs)
@pytest.mark.parametrize("seed", [313])
@pytest.mark.parametrize("inshape,reset_inshape", [((100, 1), (50, 1))])
@pytest.mark.parametrize("shape", [(10,), (10, 8)])
def test_one_hot_forward_with_reset(seed, inshape, reset_inshape, shape, ctx, func_name):
    # Input
    input = np.zeros(inshape, dtype=int)
    reset_input = np.zeros(reset_inshape, dtype=int)
    rng = np.random.RandomState(seed)

    if len(shape) != inshape[-1]:
        # input inshape and shape don't match.
        with pytest.raises(RuntimeError):
            y = F.one_hot(nn.Variable(input.shape), shape)
    else:
        for i in range(inshape[-1]):
            # this input data contains out-of-range class index.
            num_classes = shape[i]
            low = -2 * num_classes
            high = 2 * num_classes
            input[:, i] = rng.randint(low, high, size=inshape[0])
        vinput = nn.Variable(input.shape, need_grad=False)
        vinput.d = input
        with nn.context_scope(ctx):
            o = F.one_hot(vinput, shape)
        o.forward()
        # reset input
        for i in range(reset_inshape[-1]):
            reset_input[:, i] = rng.randint(low, high, size=reset_inshape[0])
        vinput.reset_shape(reset_input.shape, True)
        vinput.d = reset_input
        o.forward()
        r = ref_one_hot(reset_input, shape)
        assert_allclose(o.d, r)
        assert func_name == o.parent.name
