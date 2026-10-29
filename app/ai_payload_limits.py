"""Shared finite bounds for full-length AI audio and multi-stem results.

Keep worker publication, HTTP delivery and durable replay in agreement. These
are byte ceilings, not authorization or evidence that inference was metered.
"""

import os

MAX_SOURCE_BYTES = 512 * 1024 * 1024
MAX_ARTIFACT_BYTES = 1024 * 1024 * 1024
MIN_ARTIFACT_MIB = 64
MAX_ARTIFACT_MIB = 8192
MAX_ARTIFACT_CEILING_BYTES = MAX_ARTIFACT_MIB * 1024 * 1024
MAX_MANIFEST_BYTES = 256_000
# ZIP headers, compression overhead and the bounded manifest are not audio.
RESULT_OVERHEAD_BYTES = 2 * 1024 * 1024
MAX_RESULT_BYTES = MAX_ARTIFACT_CEILING_BYTES + RESULT_OVERHEAD_BYTES


def validate_artifact_mib(value):
    if type(value) is not int or not MIN_ARTIFACT_MIB <= value <= MAX_ARTIFACT_MIB:
        raise ValueError('Artifact size must be an integer from 64 to 8192 MiB')
    return value


def worker_artifact_bytes(default=MAX_ARTIFACT_BYTES):
    """Read the operator snapshot, never a request-plan option."""
    value = os.environ.get('MTA_AI_JOB_MAX_ARTIFACT_MIB')
    if value is None:
        return default
    try:
        parsed = int(value)
        if str(parsed) != value:
            raise ValueError('Noncanonical artifact limit')
        # Private pull workers use a stricter16MiB transport ceiling. This
        # trusted process envelope is separate from the public64MiB minimum.
        if parsed == 16:
            return 16 * 1024 * 1024
        return validate_artifact_mib(parsed) * 1024 * 1024
    except (ValueError, TypeError) as exc:
        raise ValueError('Invalid trusted worker artifact size limit') from exc
