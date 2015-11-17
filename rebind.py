import sys
import ast
import inspect
from collections import defaultdict
from itertools import count

from byteplay import Code, LOAD_GLOBAL, LOAD_CONST
from funcy import (
    walk_keys, zipdict, merge, join, project, flip,
    post_processing, unwrap, memoize, none, cached_property
)


@memoize
def introspect(func):
    if isinstance(func, str):
        func = import_func(func)

    if isinstance(func, type):
        methods = inspect.getmembers(func, predicate=inspect.ismethod)
        return join(introspect(meth) for _, meth in methods)

    func_name = _full_name(func)
    consts = merge(get_defaults(func), get_assignments(func))
    consts_spec = walk_keys(lambda k: '%s.%s' % (func_name, k), consts)
    consts_spec.update({'%s.%s' % (func.__module__, name): value
                        for name, value in get_closure(func).items()})

    # Recurse
    callables = filter(callable, consts_spec.values())
    recurse_specs = (introspect(f) for f in callables)
    return merge(join(recurse_specs) or {}, consts_spec)


def lookup(func):
    pass


def rebind(func, bindings):
    if isinstance(func, str):
        func = import_func(func)

    refs = set(bindings) | _get_refs(func)

    # Collect attrs to rebind and module dependencies
    attrs = defaultdict(set)
    deps = defaultdict(set)
    for ref in refs:
        module, attr = _resolve_ref(ref)
        attrs[module].add(attr)
        deps[module].update(_get_deps(attr))

    # Rebind modules starting from most independent ones
    rebound = {}
    for module, module_deps in sorted(deps.items(), key=lambda (_, deps): len(deps)):
        if not module_deps <= set(rebound) | {module}:
            raise ImportError('Cyclic dependency while rebinding %s' % module.__name__)
        rebound[module] = _rebind_module(module, bindings, attrs=attrs[module], rebound=rebound)

    if func.__module__ in rebound:
        return rebound[func.__module__][func.__name__]
    else:
        return func


def _rebind_module(module, bindings, attrs=None, rebound=None):
    rewriter = ConstRewriter(module, bindings)

    global_vars = _rebound_globals(module, rebound)
    global_vars.update(rewriter.local_bindings)

    tree = ast.Module(body=[get_ast(f) for f in attrs if callable(f)])
    tree = rewriter.visit(tree)
    ast.fix_missing_locations(tree)
    code = compile(tree, sys.modules[module].__file__, 'exec')

    exec(code, global_vars)
    return global_vars


@post_processing(dict)
def _rebound_globals(module, rebound):
    for name, value in sys.modules[module].__dict__.items():
        if inspect.ismodule(value):
            yield rebound.get(value.__name__, value)
        elif hasattr(value, '__module__') and value.__module__ in rebound:
            yield getattr(rebound[value.__module__], name)
        else:
            yield name, value


def _get_refs(func):
    closure = get_closure(func)
    deps = {func} | set(closure.values())
    return {'%s.%s' % (f.__module__, f.__name__) for f in deps
            if hasattr(f, '__module__') and hasattr(f, '__name__')}

def _get_deps(value):
    if callable(value):
        closure = get_closure(value)
        return {f.__module__ for f in closure if hasattr(f, '__module__')} \
            | {m.__name__ for m in closure if inspect.ismodule(m)}
    else:
        return set()  # constant

def _resolve_ref(ref):
    words = ref.split('.')
    for tail in range(1, len(words)):
        module_name = '.'.join(words[:-tail])
        try:
            module = import_module(module_name)
        except ImportError:
            pass
        else:
            attr = words[-tail]
            return module.__name__, getattr(module, attr)
    else:
        raise ImportError('Failed to resolve %s' % ref)


class ConstRewriter(ast.NodeTransformer):
    def __init__(self, module, bindings):
        self.bindings = bindings
        self.ns = module.split('.')

    def push_scope(self, name):
        self.ns.append(name)
        if hasattr(self, 'local_bindings'):
            del self.local_bindings

    def pop_scope(self):
        self.ns.pop()
        if hasattr(self, 'local_bindings'):
            del self.local_bindings

    @cached_property
    def local_bindings(self):
        prefix = ''.join('%s.' % name for name in self.ns)
        return {key[len(prefix):]: value for key, value in self.bindings.items()
                if key.startswith(prefix)}

    def visit_FunctionDef(self, node):
        self.push_scope(node.name)
        node = self.generic_visit(node)
        self.pop_scope()
        return node
    visit_ClassDef = visit_FunctionDef

    def visit_Assign(self, node):
        if not is_literal(node.value):
            return node

        to_rebind = [isinstance(target, ast.Name) and target.id in self.local_bindings
                     for target in node.targets]
        if none(to_rebind):
            return node
        if any(to_rebind) and len(node.targets) > 1:
            raise NotImplementedError('Rebinding in mass assignment is not supported')

        node.value = literal_to_ast(self.local_bindings[node.targets[0].id])
        return node

    def visit_arguments(self, node):
        kwargs = node.args[len(node.args)-len(node.defaults):]
        for i, kwarg, default in zip(count(), kwargs, node.defaults):
            if kwarg.id in self.local_bindings:
                node.defaults[i] = literal_to_ast(self.local_bindings[kwarg.id])
        return node


# Utilities

from importlib import import_module


def _full_name(func):
    if hasattr(func, 'im_class'):
        return '%s.%s.%s' % (func.__module__, func.im_class.__name__, func.__name__)
    else:
        return '%s.%s' % (func.__module__, func.__name__)

def import_func(full_name):
    module_name, func_name = full_name.rsplit('.', 1)
    module = import_module(module_name)
    try:
        return getattr(module, func_name)
    except AttributeError:
        raise ImportError("Module %s doesn't have function %s" % (module_name, func_name))


# Introspect arguments

def get_defaults(func):
    func = unwrap(func)
    return zipdict(get_kwargnames(func), func.__defaults__ or ())

def get_kwargnames(func):
    if not func.__defaults__:
        return ()
    argnames = func.__code__.co_varnames[:func.__code__.co_argcount]
    return argnames[len(argnames) - len(func.__defaults__):]


# Introspect assignments

@post_processing(dict)
def get_assignments(func):
    tree = get_ast(func)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        try:
            value = ast_eval(node.value)
        except ValueError:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                yield target.id, value


NAMED_CONSTS = {'None': None, 'True': True, 'False': False}
CONST_NAMES = flip(NAMED_CONSTS)


def is_literal(node):
    return isinstance(node, (ast.Str, ast.Num)) \
        or isinstance(node, ast.Name) and node.id in NAMED_CONSTS \
        or isinstance(node, (ast.List, ast.Tuple)) and all(is_literal, node.elts) \
        or isinstance(node, ast.Dict) and all(is_literal, node.keys + node.values)


def ast_eval(node):
    """
    Faster ast.literal_eval() with better error messages.
    Works only with nodes not strings.
    """
    if isinstance(node, ast.Num):
        return node.n
    elif isinstance(node, ast.Str):
        return node.s
    elif isinstance(node, ast.Name) and node.id in NAMED_CONSTS:
        return NAMED_CONSTS[node.id]
    elif isinstance(node, ast.Tuple):
        return tuple(ast_eval(n) for n in node.elts)
    elif isinstance(node, ast.List):
        return [ast_eval(n) for n in node.elts]
    elif isinstance(node, ast.Dict):
        return zipdict(ast_eval(node.keys), ast_eval(node.values))
    else:
        raise ValueError("Don't know how to eval %s" % node.__class__.__name__)


def literal_to_ast(value):
    if isinstance(value, (int, float)):
        return ast.Num(n=value)
    elif isinstance(value, (str, unicode)):
        return ast.Str(s=value)
    elif value in CONST_NAMES:
        return ast.Name(id=CONST_NAMES[value])
    elif isinstance(value, tuple):
        return ast.Tuple(elts=map(literal_to_ast, value))
    elif isinstance(value, ast.List):
        return ast.List(elts=map(literal_to_ast, value))
    elif isinstance(value, ast.Dict):
        return ast.Dict(
            keys=map(literal_to_ast, value.keys()),
            values=map(literal_to_ast, value.values())
        )
    else:
        raise ValueError("Can't convert %s to AST" % value)


# AST helpers

import textwrap


def get_ast(func):
    # Get function source
    source = inspect.getsource(func)
    source = textwrap.dedent(source)

    # Preserve line numbers
    if hasattr(func, '__code__'):
        source = '\n' * (func.__code__.co_firstlineno - 2) + source
    elif hasattr(func, '__init__'):
        source = '\n' * (func.__init__.im_func.__code__.co_firstlineno - 3) + source

    return ast.parse(source, func_file(func), 'single').body[0]

def func_file(func):
    return getattr(sys.modules[func.__module__], '__file__', '<nofile>')


# Introspect enclosed

def _code_names(code):
    names = set()
    for cmd, param in code.code:
        if cmd == LOAD_GLOBAL:
            names.add(param)
        elif cmd == LOAD_CONST and isinstance(param, Code):
            names.update(_code_names(param))
    return names

def get_closure(func):
    if isinstance(func, type):
        methods = inspect.getmembers(func, predicate=inspect.ismethod)
        return join(get_closure(meth.im_func) for _, meth in methods)

    code = Code.from_code(func.__code__)
    names = _code_names(code)
    return project(func.__globals__, names)
