"""Shared finite bounds for full-length AI audio and multi-stem results.

Keep worker publication, HTTP delivery and durable replay in agreement. These
are byte ceilings, not authorization or evidence that inference was metered.
"""

MAX_SOURCE_BYTES = 512 * 1024 * 1024
MAX_ARTIFACT_BYTES = 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 256_000
# ZIP headers, compression overhead and the bounded manifest are not audio.
MAX_RESULT_BYTES = MAX_ARTIFACT_BYTES + 2 * 1024 * 1024
