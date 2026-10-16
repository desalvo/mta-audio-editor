"""Bounded per-generation wall-clock budget shared by MTA and ACE adapters."""
DEFAULT_INFERENCE_TIMEOUT_SECONDS = 3600
MAX_INFERENCE_TIMEOUT_SECONDS = 14400


def inference_timeout(plan: dict, override: int | None = None) -> int:
    value = plan.get('inference_timeout_seconds', DEFAULT_INFERENCE_TIMEOUT_SECONDS) if override is None else override
    minimum = 60 if override is None else 1
    if type(value) is not int or not minimum <= value <= MAX_INFERENCE_TIMEOUT_SECONDS:
        raise ValueError('Invalid inference timeout (60–14400 seconds)')
    return value
