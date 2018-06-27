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

from six.moves import range
import pytest
import numpy as np
import nnabla as nn
import nnabla.functions as F
import nnabla.parametric_functions as PF


@pytest.mark.parametrize("seed", [313])
def test_nnp_graph(seed):

    rng = np.random.RandomState(seed)

    def unit(i, prefix):
        c1 = PF.convolution(i, 4, (3, 3), pad=(1, 1), name=prefix + '-c1')
        c2 = PF.convolution(F.relu(c1), 4,
                            (3, 3), pad=(1, 1), name=prefix + '-c2')
        c = F.add2(c2, c1, inplace=True)
        return c
    x = nn.Variable([2, 3, 4, 4])
    c1 = unit(x, 'c1')
    c2 = unit(x, 'c2')
    y = PF.affine(c2, 5, name='fc')

    runtime_contents = {
        'networks': [
            {'name': 'graph',
             'batch_size': 2,
             'outputs': {'y': y},
             'names': {'x': x}}],
    }
    import tempfile
    tmpdir = tempfile.mkdtemp()
    import os
    nnp_file = os.path.join(tmpdir, 'tmp.nnp')
    try:
        from nnabla.utils.save import save
        save(nnp_file, runtime_contents)
        from nnabla.utils import nnp_graph
        nnp = nnp_graph.NnpLoader(nnp_file)
    finally:
        import shutil
        shutil.rmtree(tmpdir)
    graph = nnp.get_network('graph')
    x2 = graph.inputs['x']
    y2 = graph.outputs['y']

    d = rng.randn(*x.shape).astype(np.float32)
    x.d = d
    x2.d = d
    y.forward(clear_buffer=True)
    y2.forward(clear_buffer=True)
    from nbla_test_utils import ArrayDiffStats
    assert np.allclose(y.d, y2.d), str(ArrayDiffStats(y.d, y2.d))
