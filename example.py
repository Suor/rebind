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
