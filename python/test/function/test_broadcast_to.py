# Copyright (c) 2017 Sony Corporation. All Rights Reserved.
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
import pdb

from nbla_test_utils import (
    function_tester,
    list_ctx_and_func_name)

def ref_broadcast_to(x, y, axis):
    return x


PARAMS = [
    #((2, 3, 4, 5), (5), -1),
    ((2, 3, 4, 5), (4, 5), -1),
    #((2, 3, 4, 5), (3, 4), 1),
    #((2, 3, 4, 5), (2), 0),
]

@pytest.mark.parametrize("seed", [314])
@pytest.mark.parametrize("fname, ctx, func_name", list_ctx_and_func_name(['broadcast_to']))
@pytest.mark.parametrize("xs, ys, axis", PARAMS)
def test_broadcast_to_forward_backward(xs, ys, axis, seed, fname, ctx, func_name):
    rng = np.random.RandomState(seed)
    ref_func = eval('ref_' + fname)
    func = getattr(F, fname)
    inputs = [rng.randn(*xs), rng.randn(*ys)]
    function_tester(rng, func, ref_func, inputs, [axis],
                    ctx=ctx, func_name=func_name,
                    atol_b=4e-3)
    #shape = rng.randint(2, 5, size=(ndim,))
    #inshape = shape.copy()
    #inshape[broadcast_dim] = 1
    #if np.prod(inshape) == 1:
    #    # Performing 0-dim array test too.
    #    inputs = [np.array(rng.randn())]
    #    function_tester(rng, func, ref_func, inputs, [shape],
    #                    ctx=ctx, backward=[True], func_name=func_name,
    #                    atol_b=4e-3)
    #inputs = [np.array(rng.randn(*inshape))]
    #function_tester(rng, func, ref_func, inputs, [shape],
    #                ctx=ctx, backward=[True], func_name=func_name,
    #                atol_b=4e-3)
    pass
