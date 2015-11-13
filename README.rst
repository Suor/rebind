Rebind
======

Example code:

.. code:: python

    # example.py
    def f(x, y, n=1):
        k = 10
        z = x**n + y**n + k
        return z

    def g(x):
        alpha = 42
        return f(x, alpha)

    beta = 17
    def h(x):
        return beta * x

Introspect constants:

.. code:: python

    assert introspect(f) == {'example.f.n': 1, 'example.f.k': 10}
    assert introspect('example.f') == {'example.f.n': 1, 'example.f.k': 10}
    assert introspect(g) == {'example.f.n': 1, 'example.f.k': 10,
                             'example.g.alpha': 42, 'example.g.f': f}
    assert introspect(h) == {'example.h.beta': 17}


Rebind on the fly:

.. code:: python

    # Rebind inline constants
    f20 = rebind('example.f', {'example.f.k': 20})

    # Rebind enclosed constant
    h_beta_18 = rebind(h, {'example.h.beta': 18})

    # Recursively rebind g and f
    g2 = rebind(g, {'example.f.k': 11, 'example.g.alpha': 43})
