"""Authenticated request identity propagated to queue admission, never from plans."""
from contextvars import ContextVar
actor = ContextVar('mta_ai_request_actor', default=None)
