# QuantBridge v1

Broker-agnostic execution infrastructure for trading bots.

## Why This Exists

QuantBridge separates strategy logic from broker execution:

bot -> risk -> routing -> broker adapter -> broker API -> execution result

This enables:
- faster broker switching
- multi-account deployment
- centralized risk enforcement
- execution resilience for propfirm workflows

## Current Status

This repository is a clean execution-focused codebase.

Implemented now:
- broker contract (canonical interface)
- cTrader adapter layer
- transport split (mock client + openapi client)
- symbol registry (mapping, precision, pip size, volume rules)
- error taxonomy
- health model
- smoke test flow (connect, price, place, close)

Partially implemented:
- cTrader Open API connect/auth + basic request flows

Not yet complete:
- production-grade reconnect and retry policy
- reconciliation persistence across process restarts
- multi-account routing engine

## Repository Structure

```text
configs/
  ctrader_icmarkets_demo.yaml
docs/
  ROADMAP.md
scripts/
  ctrader_smoke.py
src/quantbridge/
  execution/
    broker_contract.py
    errors.py
    health.py
    models.py
    symbol_registry.py
    brokers/
      ctrader_broker.py
    clients/
      ctrader_mock_client.py
      ctrader_openapi_client.py
```

## Quick Start

1) Create and activate a virtual environment.
2) Fill `.env` from `.env.example`.
3) Run smoke test in mock mode:

```bash
python scripts/ctrader_smoke.py --config configs/ctrader_icmarkets_demo.yaml
```

4) Run smoke test in Open API mode:

```bash
python scripts/ctrader_smoke.py --config configs/ctrader_icmarkets_demo.yaml --mode openapi
```

Auth help:
- `docs/AUTH_SETUP.md`

Expected output:

```json
{
  "connect": true,
  "price": true,
  "place_order": true,
  "close_order": true
}
```

## Milestones

- Milestone A: mock abstraction (done)
- Milestone B: real cTrader demo execution (in progress)
- Milestone C: reconciliation + restart safety
- Milestone D: prop-risk above broker layer
- Milestone E: multi-account scaling

## Engineering Rules

- strategy code contains no broker API calls
- broker differences stay in adapter + transport layers
- broker responses are normalized into internal models
- health and error codes are first-class data
