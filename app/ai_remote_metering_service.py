"""Optional CPU delivery evidence shared by HTTP delivery and durable execution."""
import json
import os


def headers(meta, request_key):
    from .ai_remote_metering_attestation import sign_rotating, verify_rotating
    from .ai_remote_keyring import active_keyring
    if '_pull_metering_headers' in meta:
        result = meta['_pull_metering_headers']
        if result:
            envelope = json.loads(result['X-MTA-AI-Metering-V2'])
            verify_rotating(active_keyring(), envelope, job_id=meta['job_id'], request_id=request_key,
                            worker_id=envelope['worker_id'])
        return result
    key_id = os.getenv('MTA_AI_REMOTE_METERING_SIGNING_KEY_ID', '')
    if not key_id or not request_key or not meta.get('process_tree_metered'):
        return {}
    usage = meta.get('usage')
    if not isinstance(usage, dict) or 'cpu_seconds' not in usage:
        return {}
    worker_id = os.getenv('MTA_AI_REMOTE_METERING_WORKER_ID', '')
    keys = active_keyring()
    if key_id not in keys:
        raise ValueError('Configured metering signing key unavailable or revoked')
    envelope = sign_rotating(keys[key_id], key_id=key_id, job_id=meta['job_id'], request_id=request_key,
                            worker_id=worker_id, usage={'cpu_seconds': usage['cpu_seconds']})
    return {'X-MTA-AI-Metering-V2': json.dumps(envelope, sort_keys=True, separators=(',', ':'))}
