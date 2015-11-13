from rebind import introspect, rebind
from example import f, g, h


def test_introspect():
    assert introspect(f) == {'example.f.n': 1, 'example.f.k': 10}
    assert introspect('example.f') == {'example.f.n': 1, 'example.f.k': 10}
    assert introspect(g) == {'example.f.n': 1, 'example.f.k': 10,
                             'example.g.alpha': 42, 'example.g.f': f}
    assert introspect(h) == {'example.h.beta': 17}


def test_lookup():
    pass


def test_rebind():
    assert rebind(f, {'example.f.k': 11})(0, 0) == 11
    assert rebind(h, {'example.h.beta': 18})(1) == 18
    assert rebind(h, {})(1) == 17
    assert rebind(g, {'example.f.k': 11, 'example.g.alpha': 43})(0) == 54
