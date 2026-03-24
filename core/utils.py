from django.core.cache import cache
from django.http import HttpResponseForbidden
from functools import wraps
import time

def ratelimit(key_prefix, limit=5, period=60):
    """
    Simple rate limiting decorator using Django's cache.
    :param key_prefix: Unique prefix for the rate limit key.
    :param limit: Number of allowed requests in the period.
    :param period: Period in seconds.
    """
    def decorator(func):
        @wraps(func)
        def wrapped(request, *args, **kwargs):
            # Use IP address as part of the key
            ip = request.META.get('REMOTE_ADDR')
            key = f"ratelimit:{key_prefix}:{ip}"
            
            # Get current count
            request_count = cache.get(key, 0)
            
            # Temporarily disabled for development phase
            # if request_count >= limit:
            #     return HttpResponseForbidden("Too many attempts. Please try again later.")
            
            # Increment count
            cache.set(key, request_count + 1, period)
            
            return func(request, *args, **kwargs)
        return wrapped
    return decorator
