Current PayPal dispute-history review: PayPal merchant client call shape unchanged; newly used financial paths are fixed GET-only. Pagination links are parsed only after exact merchant host/path/query/method checks and never followed. Original owner/configuration/epoch is rechecked at transactional settlement; no new remote model permission. Inventory29 sites/20 files; checker unchanged.

Current PayPal dispute-history review: PayPal merchant client call shape unchanged; newly used financial paths are fixed GET-only. Pagination links are parsed only after exact merchant host/path/query/method checks and never followed. Original owner/configuration/epoch is rechecked at transactional settlement; no new remote model permission. Inventory29 sites/20 files; checker unchanged.

Current owner workflow review: original PayPal merchant transport unchanged; exact original owner/configuration/quote/epoch/outbox admission is rechecked after approval readback and before capture. GET-only owner history stays separate. Inventory remains 29 sites /20 files; no new remote model permission.

# Explicit Python transport inventory — r210

Explicit app-owned Python HTTP/client/openers and socket constructors. Opaque operator commands, native libraries and dynamic code are separate trust boundaries; this inventory never grants rights or proves a remote checkpoint.

29 reviewed callsites in 20 application files. Run `python3 scripts/check_remote_transport_inventory.py`. The checker and reviewed source/call shapes are hash-bound. It rejects new/missing calls and missing dispositions; it never approves changes automatically.

ACE HTTP inference always rechecks model/regime permission, including loopback which may be an SSH tunnel. No loopback commercial exemption; existing recovery/control unchanged. Three literal loopback variants deny commercial inference; existing local NC HTTP E2E remains passing.

Direct ACE gateway requests must stay inside the exact configured path prefix before polling/control exemptions; forged same-length or sibling prefixes cannot bypass the inference policy. Valid scoped query_result polling remains available.

Operator refunds add explicit single-dispatch Stripe mutation and authenticated GET-only refund recovery clients. PayPal refunds reuse the reviewed merchant helper. No model rights permission is granted.

| Source / function | Line | Classification |
| --- | --- | --- |
| app/ace_step_desktop_manager.py::_health_ready | 374 | local_health |
| app/ace_step_desktop_manager.py::_download_source | 453 | asset_download |
| app/ace_step_http_worker.py::_request | 104 | inference_guarded |
| app/ai_gateway.py::ai_gateway | 65 | inference_guarded |
| app/ai_proxmox_gpu_agent_client.py::snapshot | 67 | local_health |
| app/ai_remote_client.py::infer_audio | 121 | inference_guarded |
| app/ai_remote_client.py::remote_request_status | 166 | recovery_or_metadata |
| app/ai_remote_client.py::recover_audio | 255 | recovery_or_metadata |
| app/ai_remote_client.py::cancel_remote_request | 424 | recovery_or_metadata |
| app/ai_remote_client.py::list_remote_requests | 459 | recovery_or_metadata |
| app/ai_remote_client.py::remote_resources | 493 | recovery_or_metadata |
| app/ai_remote_client.py::studio_capabilities | 512 | recovery_or_metadata |
| app/auth.py::_oauth_json | 571 | authentication |
| app/checkout_reference_recovery.py::recover | 37 | payment_provider |
| app/chord_ml.py::_download_zip | 122 | asset_download |
| app/credit_purchases.py::_stripe | 53 | payment_provider |
| app/gm_installer.py::install | 58 | asset_download |
| app/main.py::_download_drumsep_model | 5640 | asset_download |
| app/model_asset_admin.py::_source_spec | 330 | asset_download |
| app/model_asset_admin.py::download | 381 | asset_download |
| app/model_updater.py::_read_url | 40 | asset_download |
| app/native_ai_account.py::_request | 52 | authentication |
| app/operator_refunds.py::_dispatch | 240 | payment_provider |
| app/operator_refunds.py::verify | 292 | payment_provider |
| app/payment_reconcile_service.py::reconcile_checkout | 208 | payment_provider |
| app/paypal_payments.py::_api | 64 | payment_provider |
| app/rights_registry.py::_read_json | 65 | rights_metadata |
| app/secure_https.py::https_urlopen | 24 | recovery_or_metadata |
| app/vocal_banks.py::install | 106 | asset_download |
