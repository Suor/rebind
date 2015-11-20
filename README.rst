Rebind
======

Inprospect hard-coded constants in some messy code and rebind them on the fly.


Installation
------------

::

    pip install rebind


Usage
-----

.. code:: python

    from rebind import introspect, rebind, lookup, plookup

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
                             'example.g.alpha': 42, 'example.f': f}
    assert introspect(h) == {'example.beta': 17}


Rebind on the fly:

.. code:: python

    # Rebind inline constants
    f20 = rebind('example.f', {'example.f.k': 20})

    # Rebind enclosed constant
    h_beta_18 = rebind(h, {'example.beta': 18})

    # Recursively rebind g and f
    g2 = rebind(g, {'example.f.k': 11, 'example.g.alpha': 43})


Lookup function code, file and line easily:

.. code:: python

    >>> print lookup(f)
    # example.py:5
    def g(x):
        alpha = 42
        return f(x, alpha)

    >>> plookup('example.A.__init__')
    # example.py:31
        def __init__(self, x):
            h = 3
            self.prop = h * x
