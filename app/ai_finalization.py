"""Conservative cross-resource AI publication/accounting reconciliation.

This is a recoverable saga, not a cross-database ACID transaction.  Billing
association is opt-in and always references an existing ledger job.  Neither
usage nor billing identities are inferred from a generated audio job.
"""
from __future__ import annotations

from . import ai_billing_outbox, ai_publish_outbox, ai_arranger_runtime, ai_metering_bridge


def readiness(job_id):
    """Return durable evidence without inventing an accounting obligation."""
    audio = ai_publish_outbox.status(job_id)
    billing = ai_billing_outbox.inspect(job_id)
    required = billing is not None or ai_metering_bridge.billing_required(job_id)
    return {
        'job_id': job_id,
        'publication': audio['state'] if audio else None,
        'billing': billing['state'] if billing else None,
        'billing_required': required,
        'ready': bool(audio and audio['state'] == 'published'
                      and (not required or (billing is not None and billing['state'] == 'delivered'))),
    }


def reconcile(job_id, *, deliver_billing=True):
    """Recover completion only after the required durable receipts exist.

    A pending settlement remains pending if billing delivery fails; the error
    stays available from the billing outbox, and the next recovery can retry.
    """
    initial = readiness(job_id)
    if initial['publication'] != 'published':
        return False
    # A crash may occur after publishing audio but before the billing intent
    # is written. Recreate it from immutable metering evidence, never from
    # inferred resource consumption. The ledger provisioning is idempotent.
    if initial.get('billing_required') and initial.get('billing') is None and deliver_billing:
        ai_metering_bridge.register_settlement(job_id)
        initial = readiness(job_id)
    if initial['billing'] == 'pending' and deliver_billing:
        ai_billing_outbox.deliver(job_id=job_id)
    evidence = readiness(job_id)
    if not evidence['ready']:
        return False
    return ai_arranger_runtime.reconcile_published_audio(job_id)
