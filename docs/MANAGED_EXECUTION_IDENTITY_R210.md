# Managed execution identity — 2026-10-26 — PRE-RC

## Delivered behavior

The existing admitted license snapshot now binds the complete verified managed asset manifest: checkpoint/runtime/configuration/license bytes, component policy assignments and selected bindings. It is portable between installation directories. The same asset ID and license policy with different checkpoint or runtime bytes no longer compare equal. No dataclass/API/schema migration, added credential, new network request or commercial permission is introduced. Unmanaged decisions remain byte-compatible.

Actual admission checks require an enabled bundle and its complete pinned inventory. Files added after installation, symlinks (including directory links), hardlinked model files, missing/corrupt files or notices are rejected. Every manifest file still requires a component permission. Install a new versioned bundle containing all required immutable assets; do not add unpinned runtime modules/checkpoints inside an installed bundle. Existing runtime caches inside managed bundles with unpinned files will be rejected and need an explicitly pinned replacement; no deletion or migration is automatic.

The existing authenticated pull assignment carries this decision in its original immutable policy_json. The authority compares it again before assignment; the worker verifies its independent installation and compares the complete decision before heartbeat/process launch. Existing ownership, journal, TLS, nonce and completion barriers are reused. Different bytes fail without a process, invented zero CPU or output publication. Matching synthetic bytes run exactly once; replay finds no new task. An admitted old managed policy cannot silently adopt the new identity: it remains held before dispatch and needs an explicit supported cancellation/new request. Historical completed snapshots are not rewritten.

Byte digests are cached per path/device/inode/mode/link-count/size/mtime_ns/ctime_ns (bounded32768 entries per process). Each verification still checks inventory and file identity; cache misses open the file without following links where supported and check the same descriptor before/after hashing. This avoids rehashing multi-GiB unchanged checkpoints at every heartbeat. Replacement or write invalidates the cache even if mtime is restored. Cache entries are neither persisted nor accepted from a client. Kernel/privileged timestamp manipulation and mutations after verification are outside this admission-time proof.

## Acceptance and remaining work

**176 distinct affected cases passed,16 new,zero unresolved failures/errors/skips.** See validation/r210/managed-execution-identity-result.json for exact distinct cases, original fixture failure and correction, final source hashes and current security proof. Fixtures install synthetic bundles into separate authority/node roots, use the actual authenticated coordinator/SQLite/journal/process lifecycle and preserve original immutable triggers. Existing HTTPS/partition/SIGKILL/no-reexecution regressions were rerun because policy dispatch changed. No real model was installed, no provider called and no target OS certification inferred.

This closes the managed-installed-inventory substitution defect end-to-end; it does **not** close original F3/F4/F6. A hash of installed files is not proof that an opaque adapter loaded those bytes. Next implementation exit: executing-process identity/load binding for supported adapters and every remote transport, strict refusal for opaque/unsupported executors, then independent checkpoint rights review. Commercial remote inference remains explicitly denied. Whole-service cutover stays disabled. The RC checklist remains23/42(54.8%),0/7 whole macroareas,14 implementation/review criteria plus5 external criteria.

## IT — istruzioni

Usare bundle versionati e completi. Autorità e worker devono avere gli stessi byte e le stesse revisioni dei permessi; i percorsi locali possono essere diversi. Un rifiuto per checksum/inventario non si risolve disabilitando i controlli: verificare il bundle e inoltrare una nuova richiesta supportata. Non modificare i job storici. Il servizio commerciale remoto resta bloccato.

## EN — instructions

Use complete versioned bundles. Authority and worker need identical bytes and rights decisions, although local installation paths may differ. Investigate checksum/inventory rejection and submit a supported new request; do not bypass validation or rewrite historical jobs. Commercial remote inference remains blocked.
