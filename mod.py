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


def f2(x):
    k = 2
    if x:
        return f3(x-1) * k
    else:
        return 1

def f3(x):
    l = 3
    if x:
        return f2(x-1) * l
    else:
        return 1


class A(object):
    def __init__(self, x):
        h = 3
        self.prop = h * x * (beta / beta)


def a(x):
    return A(1).prop


from datetime import datetime as datetime2

def builtin_dep():
    x = datetime2(2015, 11, 20)
    return x
