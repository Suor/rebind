import ast
from byteplay import Code, LOAD_GLOBAL, LOAD_CONST
from funcy import (
    map, split, walk_keys, zipdict, merge, join, project, flip,
    post_processing, unwrap, memoize, none, partial
)


@memoize
def introspect(func):
    if isinstance(func, str):
        func = import_func(func)

    func_name = _full_name(func)
    consts = merge(get_closure(func), get_defaults(func), get_assignments(func))
    consts_spec = walk_keys(lambda k: '%s.%s' % (func_name, k), consts)

    # Recurse
    callables = filter(callable, consts.values())
    recurse_specs = (introspect(f) for f in callables)
    return merge(join(recurse_specs) or {}, consts_spec)


def lookup(func):
    pass


def rebind(func, bindings):
    if not bindings:
        return func

    tree = get_ast(func)

    # Rebind assignments
    prefix = _full_name(func) + '.'
    my_bindings, other_bindings = split_keys(lambda s: s.startswith(prefix), bindings)
    local_bindings = walk_keys(lambda s: s[len(prefix):], my_bindings)
    tree = AssignRewriter(local_bindings).visit(tree)

    # Recurse
    closure = get_closure(func)
    rebound_closure = {name: rebind(f, other_bindings) for name, f in closure.items()
                       if callable(f) and f is not func}
    local_bindings.update(rebound_closure)

    # Compile and rebind enclosed values
    func = compile_func(func, tree, local_bindings)
    return partial(func, **project(local_bindings, get_kwargnames(func)))


@post_processing(dict)
def _local_bindings(func, bindings):
    func_name = _full_name(func)
    for spec, value in bindings.items():
        spec_func, spec_var = spec.rsplit('.', 1)
        if spec_func == func_name:
            yield spec_var, value


class AssignRewriter(ast.NodeTransformer):
    def __init__(self, bindings):
        self.bindings = bindings

    def visit_Assign(self, node):
        if not is_literal(node.value):
            return node

        to_rebind = [isinstance(target, ast.Name) and target.id in self.bindings
                     for target in node.targets]
        if none(to_rebind):
            return node
        if any(to_rebind) and len(node.targets) > 1:
            raise NotImplementedError('Rebinding in mass assignment is not supported')

        node.value = literal_to_ast(self.bindings[node.targets[0].id])
        return node


def compile_func(func, tree, bindings):
    ast.fix_missing_locations(tree)
    code = compile(tree, func_file(func), 'single')
    global_vars = merge(func.__globals__, bindings)
    local_vars = merge(_locals(func), bindings)
    exec(code, global_vars, local_vars)
    return local_vars[func.__name__]


# Utilities

from importlib import import_module


def _full_name(func):
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

import sys
import inspect
import textwrap


def get_ast(func):
    # Get function source
    source = inspect.getsource(func)
    source = textwrap.dedent(source)

    # Preserve line numbers
    source = '\n' * (func.__code__.co_firstlineno - 2) + source
    return ast.parse(source, func_file(func), 'single')

def func_file(func):
    return getattr(sys.modules[func.__module__], '__file__', '<nofile>')

def is_name(node, name):
    return isinstance(node, ast.Name) and node.id == name


# Introspect enclosed

def _locals(func):
    if func.__closure__:
        names = func.__code__.co_freevars
        values = [cell.cell_contents for cell in func.__closure__]
        return zipdict(names, values)
    else:
        return {}

def _code_names(code):
    names = set()
    for cmd, param in code.code:
        if cmd == LOAD_GLOBAL:
            names.add(param)
        elif cmd == LOAD_CONST and isinstance(param, Code):
            names.update(_code_names(param))
    return names

def _globals(func):
    code = Code.from_code(func.__code__)
    names = _code_names(code)
    return project(func.__globals__, names)
    # return merge(project(__builtins__, names), project(func.__globals__, names))

def get_closure(func):
    return merge(_globals(func), _locals(func))


# To funcy

def split_keys(pred, coll):
    yes, no = split(lambda (k, v): pred(k), coll.items())
    return dict(yes), dict(no)
