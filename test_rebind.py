from rebind import introspect, rebind
from mod import f, g, h


def test_introspect():
    assert introspect(f) == {'mod.f.n': 1, 'mod.f.k': 10}
    assert introspect('mod.f') == {'mod.f.n': 1, 'mod.f.k': 10}
    assert introspect(g) == {'mod.f.n': 1, 'mod.f.k': 10,
                             'mod.g.alpha': 42, 'mod.f': f}
    assert introspect(h) == {'mod.beta': 17}


def test_lookup():
    pass


def test_rebind():
    assert rebind(f, {'mod.f.k': 11})(0, 0) == 11
    assert rebind(f, {'mod.f.n': 2})(0, 2) == 14
    assert rebind(h, {'mod.beta': 18})(1) == 18
    assert rebind(h, {})(1) == 17
    assert rebind(g, {'mod.f.k': 11, 'mod.g.alpha': 43})(0) == 54


def test_mutual_recursion():
    assert rebind('mod.f2', {'mod.f2.k': 3, 'mod.f3.l': 5})(3) == 45


def test_modules():
    assert introspect('mod2.m') == {'mod.f.k': 10, 'mod.f.n': 1, 'mod2.f': f}
    assert rebind('mod2.m', {'mod2.f.k': 11})(0) == 11


def test_classes():
    assert introspect('mod.A') == {'mod.A.__init__.h': 3}
    A = rebind('mod.A', {'mod.A.__init__.h': 4})
    assert A(1).prop == 4
    assert rebind('mod.a', {'mod.A.__init__.h': 4})(1) == 4
