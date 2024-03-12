# Copyright 2018,2019,2020,2021 Sony Corporation.
# Copyright 2021 Sony Group Corporation.
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
from nbla_test_utils import list_context, function_tester

ctxs = list_context('TopKGrad')


def ref_top_k_grad(k, abs, base_axis, grad):
    outer_dim = np.prod(grad.shape[:base_axis], dtype=int)
    inner_dim = np.prod(grad.shape[base_axis:], dtype=int)
    gg = grad.reshape(outer_dim, inner_dim).copy()
    ix = np.argsort(np.abs(gg) if abs else gg)[:, -k:]
    dx = np.zeros((outer_dim, inner_dim))
    for idx, row in enumerate(ix):
        dx[idx, row] = gg[idx, row]
    dx = dx.squeeze(axis=0) if base_axis == 0 else dx
    return dx.reshape(grad.shape)


def ref_top_k_grad_fw(x, k, abs, base_axis):
    return x


def ref_top_k_grad_bw(x, g, k, abs, base_axis, **kw):
    return ref_top_k_grad(k, abs, base_axis, g).flatten()


@pytest.mark.parametrize("ctx, fname", ctxs)
@pytest.mark.parametrize("seed", [313])
@pytest.mark.parametrize("abs", [False, True])
@pytest.mark.parametrize("ishape, k, base_axis", [
    ((4, 5, 6), 1, 0), ((4, 5, 6), 1, 1), ((4, 5, 6), 1, 2), ((4, 5, 6), 1, -2),
    ((4, 5, 6), 5, 0), ((4, 5, 6), 5, 1), ((4, 5, 6), 5, 2), ((4, 5, 6), 5, -1),
    ((1, 1000), 10, 1), ((1, 100000), 1024, 1), ((
        1, 100000), 1025, 1), ((1, 100000), 1025, -2)
])
def test_forward_backward(seed, ishape, k, abs, base_axis, ctx, fname):
    rng = np.random.RandomState(seed)
    inputs = [rng.randn(*ishape).astype(np.float32)]
    grad_unstable = False
    if fname.endswith('Cuda'):
        # TopKGradCuda backward use unstable sort, so the result will change each run.
        grad_unstable = True

    function_tester(rng, F.top_k_grad, ref_top_k_grad_fw, inputs, ctx=ctx,
                    func_name=fname, ref_grad=ref_top_k_grad_bw,
                    func_args=[k, abs, base_axis],
                    disable_half_test=k > 10,
                    disable_clear_no_need_grad_test=grad_unstable,
                    disable_auto_forward_backward_tester=grad_unstable)

    # Note: FP16 has too many duplicate value for larger K to get the
    # same sort order as FP32 and this makes the function tester fail
    # when comparing FP16 to FP32 results of gradient computation.


@pytest.mark.parametrize("ctx, fname", ctxs)
@pytest.mark.parametrize("seed", [314])
@pytest.mark.parametrize("abs", [False, True])
@pytest.mark.parametrize("ishape, reset_inshape , k, base_axis", [
    ((4, 5, 6), (4, 6, 5), 1, 0), ((4, 5, 6),
                                   (4, 6, 5), 1, 1), ((4, 5, 6), (4, 6, 5), 1, 2),
    ((4, 5, 6), (4, 6, 5), 1, -2),
    ((4, 5, 6), (4, 6, 5), 5, 0), ((4, 5, 6),
                                   (4, 6, 5), 5, 1), ((4, 5, 6), (4, 6, 5), 5, 2),
    ((4, 5, 6), (4, 6, 5), 5, -1),
    ((1, 1000), (1, 500), 10, 1), ((1, 100000), (1, 50000),
                                   1024, 1), ((1, 100000), (1, 50000), 1025, 1),
    ((1, 100000), (1, 50000), 1025, -2)
])
def test_forward_backward_with_reset(seed, ishape, reset_inshape, k, abs, base_axis, ctx, fname):
    rng = np.random.RandomState(seed)
    inputs = [rng.randn(*ishape).astype(np.float32)]
    reset_inputs = [rng.randn(*reset_inshape).astype(np.float32)]
    grad_unstable = False
    if fname.endswith('Cuda'):
        # TopKGradCuda backward use unstable sort, so the result will change each run.
        grad_unstable = True

    function_tester(rng, F.top_k_grad, ref_top_k_grad_fw, inputs, ctx=ctx,
                    func_name=fname, ref_grad=ref_top_k_grad_bw,
                    func_args=[k, abs, base_axis],
                    disable_half_test=k > 10,
                    disable_clear_no_need_grad_test=grad_unstable,
                    disable_auto_forward_backward_tester=grad_unstable,
                    reset_inputs=reset_inputs)
