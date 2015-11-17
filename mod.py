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
