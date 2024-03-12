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

from nnabla.utils import nnabla_pb2
from six.moves import filter
import copy
import nnabla as nn
import nnabla.ext_utils as ext_utils
import nnabla.functions as F
import nnabla.utils.converter
import nnabla.dtypes as dtypes
from nnabla.testing import assert_allclose
import numpy
import numpy as np
import platform as pf


def ext_to_camel(ext):
    if ext == 'cpu':
        return ''
    return ''.join([x.title() for x in ext.split('.')])


def snake_to_camel(snake):
    return ''.join([x.title() for x in snake.split('_')])


def list_context(func_name):
    try:
        import list_context_ext
        return list_context_ext.list(func_name)
    except Exception as e:
        print(e)
        return [(nn.Context(), func_name)]


def list_ctx_and_func_name(fnames):
    l = []
    for fname in fnames:
        l += [(fname, x[0], x[1]) for x in list_context(snake_to_camel(fname))]
    return l


def list_ctx_and_func_name2(fnames):
    l = []
    for fname, func_name in fnames:
        l += [(fname, x[0], x[1]) for x in list_context(func_name)]
    return l


def randn(rng, *shape):
    return np.asarray(rng.randn(*shape), dtype=np.float32)


def quit_with_gc(func_or_gen):
    '''A decorator function attaching garbage collection
    at the end of the function.

    Args:
        func_or_gen (function or int): If an int is given, it returns a decorator with garbage collection with generation=2 for gc.collect(generation) with the specified value as generation.

    '''
    generation = 2

    def _quit_with_gc(f):
        def decorated(*args, **kw):
            import gc
            ret = f(*args, **kw)
            gc.collect(generation)
            return ret

        return decorated

    if isinstance(func_or_gen, int):
        generation = func_or_gen
        return _quit_with_gc
    func = func_or_gen
    return _quit_with_gc(func)


def compute_analytical_and_numerical_grad_graph(terminal, inputs,
                                                epsilon=1e-3,
                                                recompute_graph=True):
    def set_inputs(x0):
        begin = 0
        for i in inputs:
            end = begin + i.size
            i.d = x0[begin:end].reshape(i.shape)
            begin = end

    def func(x0):
        set_inputs(x0)
        terminal.forward()
        return terminal.d.copy()

    def grad(x0):
        set_inputs(x0)
        backups = [i.g.copy() for i in inputs]
        if recompute_graph:
            terminal.forward()
            terminal.backward()
        gx0 = []
        for i, b in zip(inputs, backups):
            if recompute_graph:
                gx0.append((i.g.copy() - b).flatten())
            else:
                gx0.append(i.g.copy().flatten())
            i.g = b
        return np.concatenate(gx0)

    inputs0 = np.concatenate([i.d.flatten() for i in inputs])
    analytical_grad = grad(inputs0)
    from scipy.optimize import approx_fprime
    numerical_grad = approx_fprime(inputs0, func, epsilon)
    return analytical_grad, numerical_grad


def compute_analytical_and_numerical_grad(f, inputs, outputs, inputs0,
                                          vgrads, epsilon=1e-8, rng=None,
                                          ref_grad=None):
    """ Compute both analytical grad and numerical grad
    using given function

    f: function to test
    inputs: function input variable
    outputs: function output variable
    inputs0: function inputs to calculate numerical grad
    vgrads: initial grads of output variable
    epsilon: small value to calculate numerical grad
    rng: random number generator
    """
    if rng is None:
        rng = np.random.RandomState(np.random.randint(1000))

    from scipy import optimize
    for i in inputs:
        if i is None:  # Optional argument
            continue
        i.g = randn(rng, *i.shape)
    for o, d in zip(outputs, vgrads):
        o.g = d

    def func(x0):
        bind = 0
        backups = []
        vinputs = []
        for i, i0 in zip(inputs, inputs0):
            if i is None:  # Optional argument
                backups.append(None)
                continue
            vinputs += [i]
            if i0 is not None:  # Not need backward
                i.d[...] = x0[bind:bind + i.size].reshape(i.shape)
                bind += i.size
            backups.append(i.d.copy())

        f.forward(vinputs, outputs)
        for ind, i in enumerate(inputs):
            if i is None:  # Optional argument
                continue
            i.d[...] = backups[ind]
        return sum([np.sum(o.g * o.d) for o in outputs])

    def grad(x0):
        bind = 0
        backups = []
        vinputs = []
        for i, i0 in zip(inputs, inputs0):
            if i is None:  # Optional argument
                continue
            vinputs += [i]
            if i0 is not None:  # Not need backward
                i.d[...] = x0[bind:bind + i.size].reshape(i.shape)
                backups.append(i.g.copy())
                bind += i.size
            else:
                assert not i.need_grad
        f.setup(vinputs, outputs)
        # Need to call reset output grads since output might be inplaced
        for o, d in zip(outputs, vgrads):
            o.g = d
        f.forward(vinputs, outputs)
        f.backward(vinputs, outputs)

        bind = 0
        g = np.zeros_like(x0)
        ind = 0
        for i, i0 in zip(inputs, inputs0):
            if i is None:  # Optional argument
                continue
            if i0 is not None:  # Not need backward
                g[bind:bind + i.size] = i.g.flatten() - backups[ind].flatten()
                i.g[...] = backups[ind]
                bind += i.size
                ind += 1
        return g

    inputs0_c = np.concatenate([i0.flatten()
                                for i0 in inputs0 if i0 is not None])
    analytical_grad = grad(inputs0_c)
    numerical_grad = None
    if not ref_grad:
        numerical_grad = optimize.approx_fprime(inputs0_c, func, epsilon)
    return analytical_grad, numerical_grad


def cap_ignore_region(arr, region):
    assert len(region) == 2
    region = sorted(region)
    arr0 = arr.copy()
    arr[np.logical_and(arr > region[0], arr < region[1])] = region[0]
    return arr


class ArrayStats:

    def __init__(self, a):
        self.a = a
        self.mean = a.mean()
        self.std = a.std()
        self.max = a.max()
        self.min = a.min()
        self.amean = np.abs(a).mean()
        self.astd = np.abs(a).std()
        self.amax = np.abs(a).max()
        self.amin = np.abs(a).min()

    def __str__(self):
        lines = [
            'shape of {}'.format(self.a.shape),
            'raw))) mean(std): {}({}), [max, min]: [{}, {}]'.format(
                self.mean, self.std, self.max, self.min),
            'abs))) mean(std): {}({}), [max, min]: [{}, {}]'.format(
                self.amean, self.astd, self.amax, self.amin),
        ]
        return '\n'.join(lines)


class ArrayDiffStats:

    def __init__(self, a, b):
        self.astat = ArrayStats(a)
        self.bstat = ArrayStats(b)
        self.diffstat = ArrayStats(a - b)

    def __str__(self):
        lines = [
            '',
            '[diff]',
            str(self.diffstat),
            '[left]',
            str(self.astat),
            '[right]',
            str(self.bstat),
        ]
        return '\n'.join(lines)


def force_tuple(x):
    if isinstance(x, tuple):
        return x
    if isinstance(x, list):
        return tuple(x)
    return (x,)


def force_list(x):
    if isinstance(x, list):
        return x
    if isinstance(x, tuple):
        return list(x)
    return [x]


def half_test(rng, func, finputs, hinputs, func_args, func_kwargs, backward, ctx, func_name, atol=1e-1):

    # 0. Define utility functions
    def _filter_inputs(vinputs):
        return [v for v in vinputs if v is not None]

    def _zero_grad(vs):
        for v in vs:
            if v is None:
                continue
            v.grad.zero()

    def _get_grad_copy(vinputs, backward):
        return [i.g.copy() for i, b in zip(vinputs, backward) if b and i is not None]

    def _set_output_grad_and_copy(os, grads=None):
        if grads is None:
            grads = [randn(rng, *o.shape) for o in os]
        for o, g in zip(os, grads):
            o.g = g
        return grads

    # 1. Create a float32 function.
    with nn.context_scope(ctx):
        o_f = force_tuple(func(*(finputs + func_args), **func_kwargs))
    if True in backward:
        grad_copy = _set_output_grad_and_copy(o_f)

    # 2. Get outputs of forward and backward of the float32 function.
    o_f[0].parent.forward(_filter_inputs(finputs), o_f)
    y_f = [o.d.copy() for o in o_f]
    if True in backward:
        _zero_grad(finputs)
        o_f[0].parent.backward(_filter_inputs(finputs), o_f)
        g_f = _get_grad_copy(finputs, backward)

    # 3. Create a float16 (half) function.
    ext, dtype = ctx.backend[0].split(':')
    assert dtype == 'float'
    ctx_h = ext_utils.get_extension_context(ext, type_config='half')
    ctx_h.device_id = ctx.device_id
    with nn.context_scope(ctx_h):
        o_h = force_tuple(func(*(hinputs + func_args), **func_kwargs))
    if True in backward:
        _set_output_grad_and_copy(o_h, grad_copy)

    # 4. Get outputs of forward and backward of the float16 function.
    o_h[0].parent.forward(_filter_inputs(hinputs), o_h)
    y_h = [o.d.copy() for o in o_h]
    if True in backward:
        _zero_grad(hinputs)
        o_h[0].parent.backward(_filter_inputs(hinputs), o_h)
        g_h = _get_grad_copy(hinputs, backward)

    # 5. Check if output values are close between function data types.
    for ff, hh in zip(y_f, y_h):
        # TODO: set tol param
        assert_allclose(
            ff, hh, atol=atol, err_msg="{} half forward test fails.".format(func_name))
    if True not in backward:
        return
    for ff, hh in zip(g_f, g_h):
        # TODO: set tol param
        assert_allclose(
            ff, hh, atol=atol, err_msg="{} half backward test fails.".format(func_name))


def recomputation_test(rng, func, vinputs, func_args, func_kwargs, ctx):
    def copy_data(vinputs, voutputs):
        i_data = [copy.deepcopy(i.d) for i in vinputs]
        o_data = [copy.deepcopy(o.d) for o in voutputs]
        return i_data, o_data

    with nn.context_scope(ctx):
        voutputs = func(*(vinputs + func_args), **func_kwargs)

    voutputs = force_list(voutputs)

    for o in voutputs:
        o.recompute = True

    f = voutputs[0].parent

    need_setup_recompute = False
    for o_idx in range(len(voutputs)):
        need_setup_recompute |= f.need_setup_recompute(o_idx)

    # Filter None inputs
    vinputs = list(filter(lambda x: x is not None, vinputs))

    # Forward
    if need_setup_recompute:
        f.setup_recompute(vinputs, voutputs)
    f.forward(vinputs, voutputs)
    exp_is, exp_os = copy_data(vinputs, voutputs)

    # Claer outputs
    for o in voutputs:
        o.data.clear()

    # Recompute
    f.recompute(vinputs, voutputs)
    act_is, act_os = copy_data(vinputs, voutputs)

    for exp_i, act_i in zip(exp_is, act_is):
        assert_allclose(exp_i, act_i)

    for exp_o, act_o in zip(exp_os, act_os):
        assert_allclose(exp_o, act_o)


def create_function_nnp(inputs, outputs, func_name, func_args, func_kwargs):
    if func_name is None:
        return

    for category_name, category in nnabla.utils.converter.get_category_info().items():
        if func_name in category:
            function = category[func_name]

    nnp = nnabla_pb2.NNablaProtoBuf()
    net = nnp.network.add()
    net.name = 'network1'
    net.batch_size = 1

    func = net.function.add()
    func.name = func_name
    func.type = func_name

    # Prepare input
    func_inputs = []
    data_names = []
    parameter_names = []
    input_data = []
    for n, i in enumerate(inputs):
        if i is not None:
            if len(list(function['inputs'].items())) == 1:
                input_name, input_info = list(function['inputs'].items())[0]
                if 'variadic' in input_info and input_info['variadic']:
                    input_name += str(n)
            else:
                input_name, input_info = list(function['inputs'].items())[n]
            func_inputs.append(input_name)
            var = net.variable.add()
            var.name = input_name
            if 'parameter' in input_info and input_info['parameter']:
                parameter_names.append(input_name)

                var.type = 'Parameter'
                shape = list(i.d.shape)[:]
                if func.name == 'BatchNormalization':
                    shape = [1] + shape
                var.shape.dim.extend(shape)

                param = nnp.parameter.add()
                param.variable_name = input_name
                param.shape.dim.extend(shape)
                param.data.extend(i.d.flatten())

            else:
                input_data.append(i.d.flatten())
                data_names.append(input_name)

                var.type = 'Buffer'
                shape = list(i.d.shape)[:]
                # exclude the cases no need to extend dimension
                if input_name == 'rmean' or input_name == 't':
                    pass
                elif func.name == 'PReLU' and input_name == "x1":
                    pass
                elif func.name == 'Transpose':
                    pass
                elif func.name == 'Concatenate':
                    pass
                else:
                    shape = [1] + shape
                var.shape.dim.extend(shape)

    func.input.extend(func_inputs)

    # Prepare output
    func_outputs = []
    output_data = []
    for n, o in enumerate(outputs):
        output_name = 'y{}'.format(n)
        func_outputs.append(output_name)
        var = net.variable.add()
        var.name = output_name
        var.type = 'Buffer'
        shape = list(o.d.shape)[:]
        shape = [-1] + shape
        var.shape.dim.extend(shape)
        output_data.append(o.d.flatten())

    func.output.extend(func_outputs)

    # Prepare argument
    if 'arguments' in function:
        for n, (arg_name, arg) in enumerate(function['arguments'].items()):
            param = eval('func.{}_param'.format(function['snake_name']))
            if not func_args and not func_kwargs:
                continue
            if func.name == 'Interpolate':
                del func_args[0]
            if n < len(func_args):
                a = func_args[n]
            else:
                if func.name == 'Concatenate' or func.name == 'Stack':
                    a = func_kwargs['axis']
                else:
                    a = func_kwargs.get('keepdims')
            # This is used to fix the problem of flip (axes == None)
            if a is None:
                f = ['Sum', 'Mean', 'Max', 'Min', 'Prod']
                if 'axes' in arg_name:
                    if func.name in f:
                        a = net.variable[0].shape.dim[:-1]
                        a = [x - 1 for x in a]
                    else:
                        a = len(net.variable[0].shape.dim) - 2

            if a is not None:
                if 'axis' == arg_name:
                    if func.name == 'Concatenate':
                        pass
                    else:
                        a += 1
                if 'axes' in arg_name:
                    if func.name == 'Transpose':
                        pass
                    else:
                        if isinstance(a, tuple) or isinstance(a, list):
                            a = list(a)
                        else:
                            a = [a]
                        a = [x + 1 for x in a]
                if isinstance(a, tuple) or isinstance(a, list):
                    if arg['type'] == 'Shape':
                        exec('param.{}.dim.extend(list(a))'.format(arg_name))
                    else:
                        exec('param.{}.extend(a)'.format(arg_name))
                elif isinstance(a, numpy.ndarray):
                    a = a.flatten()
                    if arg['type'] == 'Shape':
                        if function['snake_name'] == 'broadcast':
                            exec(
                                'param.{}.dim.extend([1] + list(a))'.format(arg_name))
                        else:
                            exec('param.{}.dim.extend(list(a))'.format(arg_name))
                    else:
                        exec('param.{}.extend(a)'.format(arg_name))
                elif isinstance(a, type):
                    exec('param.{} = {}'.format(
                        arg_name, dtypes.np_dtpye_to_int[a]))
                else:
                    if 'repeated' in arg['type']:
                        exec('param.{}.extend([a])'.format(arg_name))
                    elif arg['type'] == 'string':
                        exec('param.{} = "{}"'.format(arg_name, a))
                    else:
                        if arg_name == 'base_axis':
                            a = a + 1
                        exec('param.{} = {}'.format(arg_name, a))

    # Prepare executor
    exe = nnp.executor.add()
    exe.name = 'inference'
    exe.network_name = 'network1'
    for d in data_names:
        dat = exe.data_variable.add()
        dat.variable_name = d
        dat.data_name = d

    for o in func_outputs:
        out = exe.output_variable.add()
        out.variable_name = o
        out.data_name = o

    for p in parameter_names:
        par = exe.parameter_variable.add()
        par.variable_name = p

    return nnp, input_data, output_data


def clear_no_need_grad_tester(rng, func, inputs, func_args=[], func_kwargs={}, backward=None, atol_f=1e-6, ctx=None,
                              func_name=None, insert_identity=[], auto_forward=False):
    if ctx is None:
        ctx = nn.Context()
    if backward is None:
        backward = [True for _ in inputs]
    if not True in backward:
        return

    state_rng = None
    if rng is not None:
        state_rng = rng.get_state()
    else:
        rng = rng = np.random.RandomState(313)

    def create_variables(inputs, backward):
        vinputs = []
        for i, b in zip(inputs, backward):
            if i is None:
                vinputs += [None]
                continue
            vinputs += [nn.Variable(i.shape, need_grad=b)]
            vinputs[-1].data.cast(i.dtype)[...] = i
        return vinputs

    vinputs = create_variables(inputs, backward)
    vinputs_clear_buffer = create_variables(inputs, backward)
    vinputs_identity_clear_buffer = []
    if not insert_identity:
        insert_identity = [True] * len(vinputs)

    with nn.context_scope(ctx), nn.auto_forward(auto_forward):
        for idx, i in enumerate(vinputs_clear_buffer):
            if i is None:
                vinputs_identity_clear_buffer += [None]
            elif insert_identity[idx]:
                vinputs_identity_clear_buffer += [F.identity(i)]
            else:
                vinputs_identity_clear_buffer += [i]

    # Checking forward(clear_no_need_grad=True)
    with nn.context_scope(ctx), nn.auto_forward(auto_forward):
        o = func(*(vinputs + func_args), **func_kwargs)
        o = force_tuple(o)
        F.sink(*o).forward(clear_no_need_grad=False)

        o_clear_buffer = func(
            *(vinputs_identity_clear_buffer + func_args), **func_kwargs)
        o_clear_buffer = force_tuple(o_clear_buffer)
        o_identity_clear_buffer = list(map(lambda x: F.identity(
            x) if x is not None else None, o_clear_buffer))
        o_identity_clear_buffer = list(
            filter(lambda x: x is not None, o_identity_clear_buffer))

        F.sink(*o_identity_clear_buffer).forward(clear_no_need_grad=True)

    for i in range(len(o)):
        if o[i] is None:
            continue
        ref = o[i].d
        res = o_identity_clear_buffer[i].d
        assert_allclose(ref, res, atol=atol_f,
                        err_msg="{} forward(clear_no_need_grad=True) test fails".format(func_name))

    vinputs = list(filter(lambda x: x is not None, vinputs))
    vinputs_clear_buffer = list(
        filter(lambda x: x is not None, vinputs_clear_buffer))

    for i in range(len(vinputs)):
        vinputs[i].grad.zero()
        vinputs_clear_buffer[i].grad.zero()

    for i in range(len(o)):
        if o[i] is None:
            continue
        o[i].g = randn(rng, *o[i].shape)
        o_identity_clear_buffer[i].g = o[i].g

    F.sink(*o).backward()
    F.sink(*o_identity_clear_buffer).backward(clear_buffer=True)

    for i in range(len(vinputs)):
        ref = vinputs[i].g
        res = vinputs_clear_buffer[i].g
        assert_allclose(ref, res, atol=atol_f,
                        err_msg="{} forward(clear_no_need_grad=True) and backward test fails".format(func_name))

    if state_rng:
        rng.set_state(state_rng)


def auto_forward_backward_tester(ctx, vinputs, func, func_args, func_kwargs, backward):
    '''Check if auto-forward and static mode give the same (close) gradients.

    It mainly tests clear buffer mechanism in auto-forward mode.

    '''
    from contextlib import contextmanager

    def zero_grads():
        for v, b in zip(vinputs, backward):
            if v is not None and b:
                v.grad.zero()

    def build_function():
        zero_grads()
        vinputs2 = [((F.identity(v) if b else v) if v is not None else None)
                    for v, b in zip(vinputs, backward)]
        outputs = func(*(vinputs2 + func_args), **func_kwargs)
        outputs = force_tuple(outputs)
        if len(outputs) == 1:
            return outputs[0]
        return F.add_n(*[(F.sum(o) if o.ndim != 0 else o) for o in outputs])

    def copy_grads():
        return [i.g.copy() if i is not None and b else None for i, b in zip(vinputs, backward)]

    @contextmanager
    def backup_inputs():
        bak_inputs = [None if v is None else v.data.get_data(
            'r').copy() for v in vinputs]
        try:
            yield
        finally:
            for v, bak in zip(vinputs, bak_inputs):
                if v is not None:
                    v.d = bak

    # Static reference.
    with backup_inputs():
        with nn.context_scope(ctx):
            out = build_function()
        out.forward()
        out.backward()
        ref_grads = copy_grads()

    # Auto-forward.
    with nn.context_scope(ctx), nn.auto_forward():
        out = build_function()
    out.backward(clear_buffer=True)
    act_grads = copy_grads()
    for i, (v, b) in enumerate(zip(vinputs, backward)):
        if v is None or not b:
            continue
        err_msg = f'Error in {i}-th input in auto-forward. It suggests that any member function of grad_depends_* or auto_grad_depends_* in nbla::Function is not properly defined.'
        assert_allclose(ref_grads[i], act_grads[i], err_msg=err_msg)


def function_tester(rng, func, ref_func, inputs,
                    func_args=[], func_kwargs={},
                    atol_f=1e-6, atol_b=1e-3, atol_accum=1e-6, dstep=1e-3, backward=None,
                    ctx=None, func_name=None, ref_grad=None, disable_half_test=False, atol_half=1e-1,
                    insert_identity=[], disable_clear_no_need_grad_test=False, auto_forward=False,
                    disable_auto_forward_backward_tester=False,
                    reset_inputs=None):
    """ Automatic testing of forward/backward pass of `func` by comparing it
    to the reference implementation in `ref_func`.

    Syntax of `ref_func`: inputs, parameters
    Syntax of `ref_grad`: inputs, output grads, parameters
    """

    if ctx is None:
        ctx = nn.Context()
    if backward is None:
        backward = [True for _ in inputs]

    # Create Variables
    # print('create_variable')

    def create_variables(inputs, backward):
        vinputs = []
        for i, b in zip(inputs, backward):
            if i is None:
                vinputs += [None]
                continue
            vinputs += [nn.Variable(i.shape, need_grad=b)]
            vinputs[-1].data.cast(i.dtype)[...] = i
        return vinputs

    def re_setup_inputs(vinputs):
        for v, r in zip(vinputs, reset_inputs):
            if v:
                v.reset_shape(r.shape, True)
                v.d = r
        return vinputs

    # Half test
    if not disable_half_test:
        finputs = create_variables(inputs, backward)
        hinputs = create_variables(inputs, backward)
        half_test(rng, func, finputs, hinputs, func_args,
                  func_kwargs, backward, ctx, func_name, atol=atol_half)

    vinputs = create_variables(inputs, backward)
    # Checking forward
    # print('checking forward')
    if reset_inputs is None:
        with nn.context_scope(ctx), nn.auto_forward():
            o = func(*(vinputs + func_args), **func_kwargs)
    else:
        # Check if resetup is supported
        with nn.context_scope(ctx):
            o = func(*(vinputs + func_args), **func_kwargs)
        re_setup_inputs(vinputs)
        sink_out = F.sink(*force_tuple(o))
        sink_out.forward()
        inputs = reset_inputs

    rinputs = copy.deepcopy(inputs)  # inputs for ref_func
    refs = ref_func(*(rinputs + func_args), **func_kwargs)

    refs = force_tuple(refs)
    o = force_tuple(o)
    assert len(o) == len(refs)
    for i, ref in enumerate(refs):
        res = o[i].d
        assert_allclose(ref, res, atol=atol_f,
                        err_msg="{} forward test fails".format(func_name))

    # Checking recomputation
    vinputs = create_variables(inputs, backward)
    recomputation_test(rng, func, vinputs, func_args,
                       func_kwargs, ctx)

    # Checking forward(clear_no_need_grad=True)
    if not disable_clear_no_need_grad_test:
        clear_no_need_grad_tester(rng, func, inputs, func_args, func_kwargs,
                                  backward, atol_f, ctx, func_name, insert_identity,
                                  auto_forward)

    # Checking function name
    try:
        import function_test_callback
        result = create_function_nnp(
            vinputs, o, func_name, func_args, func_kwargs)
        if result is not None:
            function_test_callback.callback(func_name, *result)
    except UnboundLocalError:
        pass
    except IndexError:
        pass
    except ImportError:
        pass

    # print('checking function name')
    if func_name is not None:
        assert o[0].parent.name == func_name

    # Checking backward
    # print('checking backward')
    if not True in backward:
        return

    # NNabla backward
    for v in vinputs:
        if v is None:
            continue
        if len(v.shape) == 0:
            v.g = randn(rng)
            continue
        v.g = randn(rng, *v.shape)
    # Verify grad
    vinputs = create_variables(inputs, backward)
    rinputs = copy.deepcopy(inputs)
    rinputs = [rinput if test else None for rinput,
               test in zip(rinputs, backward)]
    vgrads = [randn(rng, *o_.shape) for o_ in o]

    def reset_ograds():
        '''
        Reset output grads everytime we call backward.
        This is required because the output grad might
        be inplaced and modified during backward operation.
        '''
        for ovar, g in zip(o, vgrads):
            ovar.g = g

    agrads, ngrads = compute_analytical_and_numerical_grad(
        o[0].parent, vinputs, o, rinputs, vgrads, epsilon=dstep,
        rng=rng, ref_grad=ref_grad)
    if ref_grad is not None:
        rinputs = copy.deepcopy(inputs)
        doutputs = copy.deepcopy(vgrads)
        ngrads = ref_grad(*(rinputs + doutputs + func_args),
                          **func_kwargs, need_grad_flags=backward)

    assert_allclose(ngrads, agrads, atol=atol_b,
                    err_msg="{} backward w/o accumulation test fails".format(func_name))

    # Check if need_grad works
    for v, b in zip(vinputs, backward):
        if not b or v is None:
            continue
        v.grad.zero()
        v.need_grad = False
        reset_ograds()
        try:
            o[0].parent.forward(
                list(filter(lambda x: x is not None, vinputs)), o)
            o[0].parent.backward(
                list(filter(lambda x: x is not None, vinputs)), o)
        except RuntimeError as e:
            continue  # TODO
        assert np.all(v.g == 0)

    # test accum=False
    for i in range(len(vinputs)):
        if vinputs[i] is None:
            continue
        v = vinputs[i]
        v.need_grad = backward[i]

    for i in range(len(vinputs)):
        if vinputs[i] is None:
            continue
        v = vinputs[i]

        if not backward[i]:
            continue
        f = o[0].parent

        # Prepare function inputs
        finputs = list(filter(lambda x: x is not None, vinputs))

        # Save accum gradient result
        g = randn(rng, *v.shape)
        v.g = g
        reset_ograds()
        f.forward(finputs, o)
        f.backward(finputs, o)
        true_g = v.g - g

        # Check accum=False
        accum = [j != i for j, vv in enumerate(vinputs) if vv is not None]
        v.g = randn(rng, *v.shape)
        reset_ograds()
        f.forward(finputs, o)
        f.backward(finputs, o, accum)
        assert_allclose(
            v.g, true_g, atol=atol_accum,
            err_msg="{} backward w/ accumulation test fails.".format(func_name))

        # Check accum=False with NaN gradient
        v.g = np.float32('nan')
        reset_ograds()
        f.forward(finputs, o)
        f.backward(finputs, o, accum)
        assert not np.any(np.isnan(v.g))

    # Testing clear buffer mechanism in auto forward mode
    if not disable_auto_forward_backward_tester:
        auto_forward_backward_tester(
            ctx, vinputs, func, func_args, func_kwargs, backward)


def inplace_function_test_helper(inputs, func, func_args=[], func_kwargs={},
                                 ctx=None, func_name=None, rng=None):
    if rng is None:
        rng = np.random.RandomState(313)
    if ctx is None:
        ctx = nn.Context()
    with nn.context_scope(ctx):
        a_s = [inp * 1.0 for inp in inputs]
        y = func(*(a_s + list(func_args)), inplace=False, **func_kwargs)
        l = F.sum(y)
        a_s_i = [inp * 1.0 for inp in inputs]
        y_i = func(*(a_s_i + list(func_args)), inplace=True, **func_kwargs)
        l_i = F.sum(y_i)
    data = [(randn(rng, *inp.shape), randn(rng, *inp.shape)) for inp in inputs]
    for i in range(len(data)):
        inputs[i].d = data[i][0]
        inputs[i].g = data[i][1]
    l.forward()
    l.backward()
    grads = [inp.g.copy() for inp in inputs]
    for i in range(len(data)):
        inputs[i].d = data[i][0]
        inputs[i].g = data[i][1]
    l_i.forward()
    l_i.backward()
    grads_i = [inp.g.copy() for inp in inputs]
    for g, g_i in zip(grads, grads_i):
        assert_allclose(
            g, g_i, err_msg="{} inplace test fails.".format(func_name))


def convert_to_float2_array(x_complex, dtype=np.float32):
    real = np.real(x_complex)
    imag = np.imag(x_complex)
    real_s = real.reshape((real.shape)+(1, ))
    imag_s = imag.reshape((imag.shape)+(1, ))
    x_float2 = np.concatenate([real_s, imag_s], axis=len(real_s.shape)-1)
    return x_float2.astype(dtype)


def convert_to_complex_array(x_float2, dtype=np.complex64):
    x_real = x_float2[..., 0]
    x_imag = x_float2[..., 1]
    x_complex = x_real + 1j * x_imag
    return x_complex


def backward_function_tester(rng, func, inputs=None,
                             func_args=[], func_kwargs={},
                             rtol_accum=1e-5,
                             atol_f=1e-4, atol_b=1e-3, atol_accum=5e-2,
                             dstep=1e-3, backward=None, backward_b=None,
                             ctx=None, non_accum_check=False, skip_backward_check=False, insert_identity=[],
                             auto_forward=False):
    """ Automatic testing of backward function and backward pass of `func` by comparing it.
    The backward pass of `func` is the reference; therefore,
    the backward pass of `func` must be tested first!

    Syntax of `ref_func`: inputs, parameters
    """

    if ctx is None:
        ctx = nn.Context()
    if backward is None:
        backward = [True for _ in inputs]
    if pf.machine() == "aarch64":
        rtol_accum = 1e-3

    def create_variables(inputs, backward):
        vinputs = []
        for i, b in zip(inputs, backward):
            if i is None:
                vinputs += [None]
                continue
            vinp = nn.Variable(i.shape, need_grad=b)
            vinp.grad.zero()  # grads always not accumulation
            vinputs += [vinp]
            vinputs[-1].data.cast(i.dtype)[...] = i
        return vinputs

    vinputs = create_variables(inputs, backward)
    vinputs_for_clear_buffer = create_variables(inputs, backward)
    vinputs_for_nn_grad = create_variables(inputs, backward)

    vinputs_identity = []
    vinputs_identity_for_clear_buffer = []
    vinputs_identity_for_nn_grad = []
    if not insert_identity:
        insert_identity = [True] * len(vinputs)

    for idx, i in enumerate(zip(vinputs, vinputs_for_clear_buffer, vinputs_for_nn_grad)):
        with nn.auto_forward(auto_forward):
            i0, i1, i2 = i
            if i0 is None:
                vinputs_identity += [None]
                vinputs_identity_for_clear_buffer += [None]
                vinputs_identity_for_nn_grad += [None]
            elif insert_identity[idx]:
                vinputs_identity += [F.identity(i0)]
                vinputs_identity_for_clear_buffer += [F.identity(i1)]
                vinputs_identity_for_nn_grad += [F.identity(i2)]
            else:
                vinputs_identity += [i0]
                vinputs_identity_for_clear_buffer += [i1]
                vinputs_identity_for_nn_grad += [i2]

    # Forward and backward of the forward function with no buffer clear
    with nn.context_scope(ctx), nn.auto_forward(auto_forward):
        outputs0 = func(*(vinputs_identity + func_args), **func_kwargs)
        outputs0 = force_list(outputs0)
        voutputs_identity = outputs0
        F.sink(*outputs0).forward(clear_no_need_grad=False)
    grad_voutputs = []
    for output in outputs0:
        ograd = rng.randn(*output.shape)
        grad_voutputs.append(nn.Variable.from_numpy_array(
            ograd).apply(need_grad=True))
        output.g = ograd
    F.sink(*outputs0, one_input_grad=False).backward()
    vinputs = list(filter(lambda x: x is not None, vinputs))
    vinputs_identity = list(filter(lambda x: x is not None, vinputs_identity))
    vinputs_for_clear_buffer = list(
        filter(lambda x: x is not None, vinputs_for_clear_buffer))
    grad_inputs0 = [inp.g.copy() for inp in vinputs]

    # Forward and backward of the forward function with clear redundant buffer
    with nn.context_scope(ctx), nn.auto_forward(auto_forward):
        outputs_for_clear_buffer = func(
            *(vinputs_identity_for_clear_buffer + func_args), **func_kwargs)
        outputs_for_clear_buffer = force_list(outputs_for_clear_buffer)
        outputs_for_clear_buffer = list(map(lambda x: F.identity(
            x) if x is not None else None, outputs_for_clear_buffer))
        F.sink(*outputs_for_clear_buffer).forward(clear_no_need_grad=True)

    for o, ref_o in zip(outputs_for_clear_buffer, outputs0):
        o.g = ref_o.g

    # Check backward
    F.sink(*outputs_for_clear_buffer,
           one_input_grad=False).backward(clear_buffer=True)

    grad_inputs_for_clear_buffer = [inp.g.copy()
                                    for inp in vinputs_for_clear_buffer]
    for grad_ref, grad_res in zip(grad_inputs0, grad_inputs_for_clear_buffer):
        if grad_ref is None or grad_res is None:
            continue
        assert_allclose(grad_ref, grad_res, atol=atol_f,
                        err_msg="backward(clear_buffer=True) and backward(clear_buffer=False) results differ.")

    # Forward of the backward function
    from nnabla.backward_functions import registry
    func_name = output.parent.info.type_name
    func_backward = registry[func_name]
    grad_vinputs = grad_voutputs + vinputs
    grad_vinputs_identity = grad_voutputs + vinputs_identity
    vinput_identity_shapes = [inp.shape for inp in vinputs_identity]
    voutput_identity_shapes = [inp.shape for inp in voutputs_identity]
    func_info_args = output.parent.info.args
    with nn.context_scope(ctx), nn.auto_forward(auto_forward):
        ograds0 = func_backward(grad_voutputs, vinputs_identity, vinput_identity_shapes,
                                voutputs_identity, voutput_identity_shapes, **func_info_args)
        ograds0 = force_list(ograds0)
        ograds0_ = list(filter(lambda o: o is not None, ograds0))
        F.sink(*ograds0_).forward(clear_no_need_grad=True)
    outputs1 = []
    for i, ograd in enumerate(ograds0):
        outputs1.append(ograd.d.copy()) if ograd is not None else \
          outputs1.append(None)

    # Check num of returned elements
    assert_allclose(len(vinputs), len(outputs1),
                    err_msg="Length of the outputs ({}) does not match "
                    "the length of the inputs ({}) to the backward function".format(len(outputs1), len(vinputs)))

    # Check forward
    for i, elm in enumerate(zip(grad_inputs0, outputs1)):
        grad_ref, grad_res = elm
        if grad_ref is None or grad_res is None:
            continue
        assert_allclose(grad_ref, grad_res, atol=atol_f,
                        err_msg="Forward of the backward function ({}) fails at {}-th output.".format(
                            func_backward.__name__, i))

    # Check the same results between backward_function and nn.grad
    vinputs = [v for b, v in zip(backward, vinputs) if b]
    vinputs = list(filter(lambda x: x is not None, vinputs))

    with nn.context_scope(ctx), nn.auto_forward(auto_forward):
        outputs0_for_nn_grad = func(
            *(vinputs_identity_for_nn_grad + func_args), **func_kwargs)
        outputs0_for_nn_grad = force_list(outputs0_for_nn_grad)
        vinputs_identity_for_nn_grad = [v for b, v in zip(
            backward, vinputs_identity_for_nn_grad) if b]
        vinputs_identity_for_nn_grad = list(
            filter(lambda x: x is not None, vinputs_identity_for_nn_grad))

        ograds1 = nn.grad(outputs0_for_nn_grad, vinputs_identity_for_nn_grad,
                          grad_outputs=[g.d.copy() for g in grad_voutputs])
        F.sink(*ograds1).forward(clear_no_need_grad=True)
    ograds0 = list(filter(lambda o: o is not None, ograds0))
    ograds1 = list(filter(lambda o: o is not None, ograds1))
    for i in range(len(ograds0)):
        if ograds0[i].parent is None:
            continue
        assert_allclose(ograds0[i].d, ograds1[i].d, atol=atol_f,
                        err_msg="nn.grad and backward_functon results differ.")

    # Check backward
    # needed since we sometimes do need_grad=False for optimization, e.g., mask.
    def set_inputs(inputs0, vinputs):
        begin = 0
        for i in vinputs:
            end = begin + i.size
            i.d = inputs0[begin:end].reshape(i.shape)
            begin = end

    def obj_func(inputs0, voutput, vinputs):
        set_inputs(inputs0, vinputs)
        voutput.forward()
        y = voutput.d.copy()
        return y

    initial_grads = []
    for grad_vinput in grad_vinputs:
        if grad_vinput is None:
            continue
        g = np.asarray(rng.randn(*grad_vinput.shape))
        initial_grads.append(g)
    grad_inputs1 = np.concatenate([v.d.flatten()
                                   for v in grad_vinputs if v is not None])

    for i, ograd in enumerate(ograds0):
        # We can skip if the backward is the functions composite.
        # If the backward is of functions composite,
        # the numerical difference is really different from the analytical one for some functions.
        if skip_backward_check:
            continue

        if ograd is None or not backward[i]:
            continue
        for ig, v in zip(initial_grads, grad_vinputs):
            v.g = ig

        # This must be first since approx_fprime destroys the input values
        # analytical grad.
        rgrad = rng.randn()
        with nn.auto_forward(auto_forward):
            sum_ograd = F.sum(ograd) * rgrad
        sum_ograd.forward(clear_no_need_grad=True)
        sum_ograd.backward()
        analytical_grads = np.concatenate(
            [v.g.flatten() for v in grad_vinputs])
        analytical_grads -= np.concatenate([g.flatten()
                                            for g in initial_grads])
        # numerical grad
        from scipy.optimize import approx_fprime
        numerical_grads = approx_fprime(
            grad_inputs1, obj_func, dstep, sum_ograd, grad_vinputs)

        # grad_vinputs: dy_1, ..., dy_n, x_1, ..., x_n
        # grad_voutputs: dy_1, ..., dy_n
        seps = [0] + np.cumsum([int(np.prod(v.shape))
                                for v in grad_vinputs]).tolist()
        ngrads = len(grad_voutputs)
        ninputs = len(grad_vinputs)
        backward_b = [True] * ninputs if backward_b is None else backward_b
        for k, sep in enumerate(zip(seps[:-1], seps[1:])):
            if k >= ngrads and not backward[k - ngrads] or not backward_b[k]:
                continue
            s0, s1 = sep
            analytical_grad = analytical_grads[s0:s1]
            numerical_grad = numerical_grads[s0:s1]
            assert_allclose(analytical_grad, numerical_grad, rtol=rtol_accum, atol=atol_accum,
                            err_msg="Backward (accum) of the backward function ({}) wrt {}-th / {} input fails.".format(
                                func_backward.__name__, k, ninputs))

    # Some functions backward like AffineDataGrad and AffineFilterGrad does not check non-accum anywhere
    # so check those non-accum backward method here.
    if non_accum_check:
        # for any outputs, parents are the same function.
        parent = outputs0[0].parent
        inputs = parent.inputs
        # Accum
        initial_grads = np.concatenate(
            [inp.g.flatten() for inp, b in zip(inputs, backward) if b])
        accum = [True] * len(inputs)
        parent.backward(inputs, outputs0, accum=accum)
        accum_grads = np.concatenate([inp.g.flatten()
                                      for inp, b in zip(inputs, backward) if b])
        non_accum_grads0 = accum_grads - initial_grads
        # Non-accum
        accum = [False] * len(inputs)
        parent.backward(inputs, outputs0, accum=accum)
        non_accum_grads1 = np.concatenate(
            [inp.g.flatten() for inp, b in zip(inputs, backward) if b])
        # Check
        assert_allclose(non_accum_grads0, non_accum_grads1, atol=atol_b,
                        err_msg="Backward (non-accum) of the backward function ({}) fails.".format(
                            func_backward.__name__))


def grad_function_forward_function_output(bwd_func_class, fwd_func, ctx, inputs,
                                          *func_args, **func_kwargs):
    vinputs = [nn.Variable(inp.shape)
               if inp is not None else None for inp in inputs]
    y = fwd_func(*(vinputs + force_list(func_args)), **func_kwargs)
    bwd_func = bwd_func_class(ctx, *func_args, **func_kwargs)
    return bwd_func, y
