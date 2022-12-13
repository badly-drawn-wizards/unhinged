#!/usr/bin/env python3
from functools import wraps

def lazy(obj):
    """Wraps a class method with no additional arguments to be lazily evaluated once and the result cached. Intended to be used with immutable classes."""
    @wraps(obj)
    def thunk(self):
        cache = getattr(self, '_lazy_cache', {})
        object.__setattr__(self, '_lazy_cache', cache)
        if obj in cache:
            val = cache[obj]
        else:
            val = cache[obj] = obj(self)
        return val
    return thunk
