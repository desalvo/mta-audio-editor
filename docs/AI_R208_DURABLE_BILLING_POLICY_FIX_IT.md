# MTA 0.3.0-r208 — obbligo contabile persistente

## Modifica verificata
Un job già provisionato nel ledger mantiene l'obbligo di finalizzazione anche quando la preferenza billing dell'utente viene disabilitata successivamente. Il lookup di identità è read-only e non genera nuovi addebiti. I job senza provisioning e con billing disabilitato rimangono non fatturabili.

Moduli: `app/ai_billing.py`, `app/ai_metering_bridge.py`.

## Test
`PYTHONPATH=. pytest -q tests/test_r208_*.py`: 184 passed (ambiente locale). Non sostituisce test hardware EL10/ROCm né certificazione generale di tutti gli adapter.

## Restano aperti
- attestazione GPU attendibile per singolo job, in particolare inferenze remote e processi multipli;
- migrazione e smoke test di tutti gli ingressi AI legacy, native e remoti;
- fault injection end-to-end su stack isolato, inclusi crash concorrenti e recovery con filesystem e ledger reali;
- certificazione dei backend e delle inferenze su ollama-02 (Rocky EL10 / ROCm 7.2.4).

Nessuna variazione alla versione 0.3.0-r208.
