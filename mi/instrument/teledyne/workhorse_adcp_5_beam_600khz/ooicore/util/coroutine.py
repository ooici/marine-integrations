"""
Adapted from http://www.python.org/dev/peps/pep-0342/ and
http://www.dabeaz.com/coroutines/
"""


def coroutine(func):
    """
    decorator that makes a generator function automatically advance to its
    first yield point when initially called.
    """

    def wrapper(*args, **kwargs):
        gen = func(*args, **kwargs)
        gen.next()
        return gen

    wrapper.__name__ = func.__name__
    wrapper.__dict__ = func.__dict__
    wrapper.__doc__ = func.__doc__

    return wrapper
