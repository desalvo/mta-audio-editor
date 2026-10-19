# PayPal operator checklist — MTA 0.3.0-r210

1. Create a PayPal Developer REST application for **Sandbox**. Keep Sandbox and
   Live credentials separate. Record Client ID and Client Secret.
2. Create a public HTTPS webhook at
   `https://mta.apps.desalvo.eu/api/billing/paypal/webhook` for
   `PAYMENT.CAPTURE.COMPLETED` and `PAYMENT.CAPTURE.REFUNDED`. Record Webhook ID.
3. In server Settings → Subscriptions and credits → PayPal, select the environment,
   enter all three values and enable the provider. Empty credential fields retain
   existing values. Secret values are sealed at rest and never returned by APIs.
4. Users can pay outstanding subscription fees from their profile, including a
   prorated fee after termination, or purchase configured credit denominations
   from the credit shop. Credit top-ups require subscription eligibility and an
   active subscription/promotion, plus the global credit switch.
5. Orders v2 provides **one-off CAPTURE checkout**. This implementation does not
   automatically charge PayPal on every subscription renewal. Subscription fees
   and overage credit balances are separate: paying a fee never tops up credits.
6. Only authenticated server API responses or provider-verified webhook events can
   fulfill an order. Currency, amount, merchant configuration, canonical order and
   completed captures must match. Approval/return URLs alone grant nothing.
   Repeated callbacks/captures cannot duplicate fulfillment. Verified credit
   refunds reverse top-ups, including when the remaining balance becomes negative.
7. Run Sandbox acceptance for success, pending capture, cancellation, repeated
   callbacks, ownership/amount mismatch, credit refund and subscription termination
   during checkout. Verify webhook delivery through the actual ingress/HAProxy.
   Returning an already paid order after a policy change must still reconcile the
   actual completed payment; it must not silently discard received money.
8. A terminated prepaid plan records the unused fee as a refund liability visible
   in contract history. The operator settles that monetary refund through PayPal;
   it is not silently converted into overage credits. Cent rounding differences
   and payments completed after a concurrent contract change remain explicit
   amounts to reconcile.

No production credentials or live payments were used during development. Local
regressions use controlled provider responses and do not certify the real merchant
account, provider webhook registration, taxes or banking settlement.

Official integration references:
[Orders API](https://developer.paypal.com/api/rest/integration/orders-api),
[Checkout example](https://developer.paypal.com/checkout/put-it-all-together/),
[Webhook verification](https://developer.paypal.com/api/webhooks/v1).
