# Copyright 2017,2018,2019,2020,2021 Sony Corporation.
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
import nnabla as nn
import nnabla.functions as F
from test_flip import ref_flip
from nbla_test_utils import list_context

ctxs = list_context('ImageAugmentation')


@pytest.mark.parametrize("ctx, func_name", ctxs)
@pytest.mark.parametrize("seed", [313])
@pytest.mark.parametrize("shape", [(3, 5, 8), (3, 10, 10)])
def test_image_augmentation_forward(seed, shape, ctx, func_name):
    rng = np.random.RandomState(seed)
    inputs = [rng.randn(16, 3, 8, 8).astype(np.float32)]
    i = nn.Variable(inputs[0].shape)
    # NNabla forward
    with nn.context_scope(ctx), nn.auto_forward():
        o = F.image_augmentation(i)
    assert o.d.shape == inputs[0].shape

    func_kargs = {
        'shape': shape,
        'pad': (2, 2),
        'min_scale': 0.8,
        'max_scale': 1.2,
        'angle': 0.2,
        'aspect_ratio': 1.1,
        'distortion': 0.1,
        'flip_lr': True,
        'flip_ud': False,
        'brightness': 0.1,
        'brightness_each': True,
        'contrast': 1.1,
        'contrast_center': 0.5,
        'contrast_each': True,
        'noise': 0.1,
        'seed': 0}

    with nn.context_scope(ctx), nn.auto_forward():
        o = F.image_augmentation(i, **func_kargs)
    assert o.d.shape == (inputs[0].shape[0],) + shape

    # Checking recomputation
    from nbla_test_utils import recomputation_test

    recomputation_test(rng=rng, func=F.image_augmentation, vinputs=[i],
                       func_args=[], func_kwargs=func_kargs, ctx=ctx)

    func_kargs['seed'] = -1
    recomputation_test(rng=rng, func=F.image_augmentation, vinputs=[i],
                       func_args=[], func_kwargs=func_kargs, ctx=ctx)

# reset forward fail with reset input in a diff shape


@pytest.mark.parametrize("ctx, func_name", ctxs)
@pytest.mark.parametrize("seed", [313])
@pytest.mark.parametrize("shape", [(3, 5, 8), (3, 10, 10)])
def test_image_augmentation_forward_with_reset(seed, shape, ctx, func_name):
    pytest.skip(
            'Reset input for ImageAugmentation is not support yet')
    rng = np.random.RandomState(seed)
    inputs = [rng.randn(16, 3, 8, 8).astype(np.float32)]
    # reset
    reset_inputs = [rng.randn(16, 3, 4, 4).astype(np.float32)]
    i = nn.Variable(inputs[0].shape)
    # NNabla forward
    with nn.context_scope(ctx):
        o = F.image_augmentation(i)
    o.forward()
    assert o.d.shape == inputs[0].shape
    # reset and forward
    i.reset_shape(reset_inputs[0].shape, True)
    i.d = reset_inputs[0]
    o.forward()
    assert o.d.shape == reset_inputs[0].shape
