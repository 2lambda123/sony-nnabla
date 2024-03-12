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
import nnabla.functions as F
from nbla_test_utils import list_context

ctxs = list_context('PReLU')


def ref_prelu(x, w, base_axis=1):
    wshape = [1 for _ in range(x.ndim)]
    if w.size != 1:
        wshape[base_axis] = w.size
    return np.maximum(0, x) + w.reshape(wshape) * np.minimum(0, x)


@pytest.mark.parametrize("seed", [313])
@pytest.mark.parametrize("inshape, wshape, base_axis",
                         [((2, 3, 2, 3, 2), tuple(), 4),
                          ((2, 3, 1, 3), (3,), 1),
                          ((2, 3, 1, 3), (3,), -1),
                          ((2, 5, 3, 6), (3,), -2)
                          ]
                         )
@pytest.mark.parametrize("ctx, func_name", ctxs)
def test_prelu_forward_backward(seed, inshape, wshape, base_axis, ctx, func_name):
    from nbla_test_utils import cap_ignore_region, function_tester
    rng = np.random.RandomState(seed)
    x = rng.randn(*inshape).astype(np.float32)
    w = np.array(rng.randn(*wshape)).astype(np.float32)
    inputs = [x, w]
    function_tester(rng, F.prelu, ref_prelu, inputs,
                    func_args=[base_axis],
                    ctx=ctx, func_name=func_name, atol_b=1e-2)


@pytest.mark.parametrize("seed", [313])
@pytest.mark.parametrize("inshape, wshape, base_axis",
                         [((2, 3, 2, 3, 2), tuple(), 4),
                          ((2, 3, 1, 3), (3,), 1),
                          ((2, 5, 3, 6), (3,), -2)
                          ])
@pytest.mark.parametrize("ctx, func_name", ctxs)
def test_prelu_double_backward(seed, inshape, wshape, base_axis, ctx, func_name):
    from nbla_test_utils import cap_ignore_region, backward_function_tester
    rng = np.random.RandomState(seed)
    x = rng.randn(*inshape).astype(np.float32)
    w = np.array(rng.randn(*wshape)).astype(np.float32)
    inputs = [x, w]
    backward_function_tester(rng, F.prelu, inputs,
                             func_args=[base_axis],
                             ctx=ctx, atol_accum=1e-1, dstep=1e-3)


@pytest.mark.parametrize("seed", [313])
@pytest.mark.parametrize("inshape, wshape,reset_inshape, reset_wshape, base_axis",
                         [((2, 3, 2, 3, 2), tuple(), (3, 2, 2, 2, 3), tuple(), 4),
                          ((2, 3, 1, 3), (3,), (2, 4, 1, 3), (4,), 1),
                          ((2, 3, 1, 3), (3,), (2, 3, 1, 4), (4,), -1),
                          ((2, 5, 3, 6), (3,), (2, 5, 4, 6), (4,), -2)
                          ]
                         )
@pytest.mark.parametrize("ctx, func_name", ctxs)
def test_prelu_forward_backward_with_reset(seed, inshape, wshape, reset_inshape, reset_wshape, base_axis, ctx,
                                           func_name):
    from nbla_test_utils import function_tester
    rng = np.random.RandomState(seed)
    x = rng.randn(*inshape).astype(np.float32)
    w = np.array(rng.randn(*wshape)).astype(np.float32)
    inputs = [x, w]
    # reset input
    reset_x = rng.randn(*reset_inshape).astype(np.float32)
    reset_w = np.array(rng.randn(*reset_wshape)).astype(np.float32)
    reset_inputs = [reset_x, reset_w]
    function_tester(rng, F.prelu, ref_prelu, inputs,
                    func_args=[base_axis],
                    ctx=ctx, func_name=func_name, atol_b=1e-2, reset_inputs=reset_inputs)
