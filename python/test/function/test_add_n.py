# Copyright 2020,2021 Sony Corporation.
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

ctxs = list_context('AddN')


def ref_function(*inputs, **params):
    y = 0
    for i in range(len(inputs)):
        y += inputs[i]
    return y


@pytest.mark.parametrize("ctx, func_name", ctxs)
@pytest.mark.parametrize("seed", [314])
@pytest.mark.parametrize('num_inputs', [2, 3, 5])
def test_add_n_forward_backward(num_inputs, seed, ctx, func_name):
    from nbla_test_utils import function_tester
    rng = np.random.RandomState(seed)
    shape0 = [2, 3, 4]
    inputs = []
    for i in range(num_inputs):
        inputs.append(rng.randn(*shape0).astype(np.float32))
    function_tester(rng, F.add_n, ref_function, inputs,
                    ctx=ctx, func_name=func_name, atol_b=2e-3)


@pytest.mark.parametrize("ctx, func_name", ctxs)
@pytest.mark.parametrize("seed", [313])
@pytest.mark.parametrize('num_inputs', [2, 3, 5])
def test_add_n_double_backward(num_inputs, seed, ctx, func_name):
    from nbla_test_utils import backward_function_tester
    rng = np.random.RandomState(seed)
    shape0 = [2, 3, 4]
    inputs = []
    for i in range(num_inputs):
        inputs.append(rng.randn(*shape0).astype(np.float32))
    backward_function_tester(rng, F.add_n,
                             inputs=inputs,
                             func_args=[], func_kwargs={},
                             atol_accum=5e-2,
                             dstep=1e-3,
                             ctx=ctx)


@pytest.mark.parametrize("seed", [313])
@pytest.mark.parametrize("input_shape", [(2, 3, 4)])
@pytest.mark.parametrize("n_inputs, n_active", [(3, 1), (5, 2), (10, 6)])
def test_add_n_active_inputs(n_inputs, n_active, input_shape, seed):
    from nnabla.testing import assert_allclose
    rng = np.random.RandomState(seed)
    inputs = [rng.randn(*input_shape).astype('f4') for _ in range(n_inputs)]
    active = np.random.permutation(n_inputs) < n_active

    y = F.add_n(*[nn.Variable.from_numpy_array(inp).apply(need_grad=True)
                  for inp in inputs])
    y.parent.set_active_input_mask(active)
    y_ref = F.add_n(*[nn.Variable.from_numpy_array(inp).apply(need_grad=True)
                      for (act, inp) in zip(active, inputs) if act])

    y.forward()
    y_ref.forward()
    assert_allclose(y.d, y_ref.d)

    for inp in y.parent.inputs + y_ref.parent.inputs:
        inp.g = 0

    y.backward()
    y_ref.backward()
    active_inputs = [y.parent.inputs[i] for i, act in enumerate(active) if act]
    for inp, ref in zip(active_inputs, y_ref.parent.inputs):
        assert_allclose(inp.g, ref.g)


@pytest.mark.parametrize("ctx, func_name", ctxs)
@pytest.mark.parametrize("seed", [42])
@pytest.mark.parametrize('num_inputs', [2, 3, 5])
def test_add_n_forward_backward_with_reset(num_inputs, seed, ctx, func_name):
    from nbla_test_utils import function_tester
    rng = np.random.RandomState(seed)
    shape0, reset_shape0 = [2, 3, 4], [3, 4, 5]
    inputs, reset_inputs = [], []
    for _ in range(num_inputs):
        inputs.append(rng.randn(*shape0).astype(np.float32))
        reset_inputs.append(rng.randn(*reset_shape0).astype(np.float32))
    function_tester(rng, F.add_n, ref_function, inputs,
                    ctx=ctx, func_name=func_name, atol_b=2e-3, reset_inputs=reset_inputs)
