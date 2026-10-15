# MTA 0.3.0-r208 — verified AI/ledger binding refinement

Implemented: `ai_billing_outbox.register_verified` validates a durable Arranger/Remix inference, the account owner of an existing billing ledger job, the operation kind, and compatible ledger state before registering an immutable outbox settlement intent. No billing user, AI job, usage, or GPU consumption is inferred. This protects explicit associations, but it is **not an automatic lifecycle association** and is not a certificate of end-to-end atomicity.

SQLite queue startup migrations now tolerate precisely the duplicate-column race from a concurrent opener, without masking unrelated errors.

Local validation: r208 tests 154 passed, including 5 dedicated binding tests. Actual EL10/ROCm adapter execution, automatic identity propagation and zero-duplicate end-to-end crash certification are pending.
