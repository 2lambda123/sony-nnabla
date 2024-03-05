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

ctxs = list_context('VATNoise')


def ref_vat_noise(r, base_axis, eps):
    base_axis = base_axis + r.ndim*(base_axis < 0)
    shape = r.shape
    r = r.reshape(shape[0:base_axis] + (np.prod(shape[base_axis:]), ))
    r = r / np.sqrt(np.sum(r**2, axis=base_axis)
                    ).reshape(shape[0:base_axis] + (1,))
    r = r.reshape(shape).astype(np.float32)
    return eps * r


@pytest.mark.parametrize("ctx, func_name", ctxs)
@pytest.mark.parametrize("seed", [313])
@pytest.mark.parametrize("base_axis, shape", [(1, (3, 6)), (1, (5, 8)), (2, (3, 7, 13)), (-1, (3, 6)), (-2, (3, 7, 13))])
@pytest.mark.parametrize("eps", [10, 1.4])
def test_vat_noise(seed, base_axis, shape, eps, ctx, func_name):
    rng = np.random.RandomState(313)
    r = 1.0e-6 + rng.randn(*(shape)).astype(np.float32)
    ref = ref_vat_noise(r, base_axis, eps)

    x = nn.Variable(shape, need_grad=True)
    w = nn.Variable(shape, need_grad=True)
    y = F.vat_noise(x, w, base_axis, eps)
    x.d = r
    y.forward()
    y.backward()
    res = y.d

    atol_f = 1e-6
    assert_allclose(ref, res, atol=atol_f)

    atol_b = 1e-6
    ref = np.ones(shape) * eps
    res = w.d
    assert_allclose(ref, res, atol=atol_b)


@pytest.mark.parametrize("ctx, func_name", ctxs)
@pytest.mark.parametrize("seed", [313])
@pytest.mark.parametrize("base_axis, shape,reset_shape", [(1, (3, 6), (5, 8))])
@pytest.mark.parametrize("eps", [10, 1.4])
def test_vat_noise_with_reset(seed, base_axis, shape, reset_shape, eps, ctx, func_name):
    rng = np.random.RandomState(313)
    r = 1.0e-6 + rng.randn(*(shape)).astype(np.float32)
    ref = ref_vat_noise(r, base_axis, eps)

    reset_r = rng.randn(*(reset_shape)).astype(np.float32)
    reset_ref = ref_vat_noise(reset_r, base_axis, eps)

    x = nn.Variable(shape, need_grad=True)
    w = nn.Variable(shape, need_grad=True)
    y = F.vat_noise(x, w, base_axis, eps)
    x.d = r
    y.forward()
    y.backward()
    res = y.d

    atol_f = 1e-6
    assert_allclose(ref, res, atol=atol_f)

    atol_b = 1e-6
    ref = np.ones(shape) * eps
    res = w.d
    assert_allclose(ref, res, atol=atol_b)

    # reset inputs
    x.reset_shape(reset_shape, True)
    w.reset_shape(reset_shape, True)
    x.d = reset_r
    y.forward()
    y.backward()
    res = y.d

    atol_f = 1e-6
    assert_allclose(reset_ref, res, atol=atol_f)

    atol_b = 1e-6
    reset_ref = np.ones(reset_shape) * eps
    res = w.d
    assert_allclose(reset_ref, res, atol=atol_b)
