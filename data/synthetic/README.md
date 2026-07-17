# Synthetic Data Seed

Deterministic synthetic data for the Medication Operations Platform.
All generated data is labeled `is_synthetic = TRUE` and contains **no patient data**.

## Deterministic Seed Value

**Seed: 42** — applied via `SELECT setseed(0.42)` in PostgreSQL.

The seed ensures that `random()` calls within the consumption history
generation produce identical results on every run. All other data uses
fixed UUIDs, so the entire dataset is fully reproducible.

## What Gets Created

| Resource                 | Count  | Notes                                       |
|--------------------------|--------|---------------------------------------------|
| Locations                | 5      | 3 pharmacies, 1 ward, 1 warehouse           |
| Medications              | 10     | Common generics with realistic NDCs          |
| Suppliers                | 3      | Varied lead times (3, 5, 7 days)            |
| Supplier-medication links| 14     | With preferred flags and unit costs          |
| Inventory lots           | 21     | 2-3 lots per medication-location pair        |
| Inventory levels         | 17     | Aggregated on-hand quantities                |
| Consumption history      | ~900   | 10 med-location pairs × 90 days             |
| Supplier shortage events | 1      | PharmaCorp / Amoxicillin                     |
| Delivery failure (task)  | 1      | Atorvastatin transfer with full state log    |
| Config entries           | 7      | Operational thresholds                       |

## Planted Patterns

1. **Weekly seasonality** — All consumption data uses a weekday multiplier
   of 1.0 and a weekend multiplier of 0.6, creating a clear Mon-Fri vs
   Sat-Sun pattern visible in any time-series chart.

2. **Demand surge** — Lisinopril at Downtown Pharmacy, days 60-67
   (2026-06-16 to 2026-06-23). Consumption jumps to 3× normal (~45/day
   vs ~15/day). Simulates a sudden increase in prescriptions.

3. **Confirmed stockout** — Metformin at Westside Clinic, days 70-77
   (2026-06-26 to 2026-07-03). Consumption drops to 0 with
   `is_stockout_period = TRUE`. Inventory lots show 0 quantity.

4. **Supplier shortage** — PharmaCorp cannot supply Amoxicillin 500mg
   from day 50 to day 65 (2026-06-06 to 2026-06-21). Recorded in
   `supplier_shortage_events` with realistic notice text and LLM summary.

5. **Delivery failure** — An internal transfer of Atorvastatin from
   North Distribution Hub to Westside Clinic failed after 3 AMR retry
   attempts (navigation failure). Full task state log from `requested`
   through `failed`.

## Running the Seed

```bash
# First run (or re-seed after reset)
psql -h $DB_HOST -U $DB_USER -d medication_platform -f data/synthetic/seed.sql

# With Docker Compose
docker compose exec db psql -U postgres -d medication_platform -f /docker-entrypoint-initdb.d/seed.sql
```

The script is **idempotent** — safe to run multiple times. It uses:
- `ON CONFLICT DO NOTHING` for all INSERT statements
- `IF NOT EXISTS` checks for DDL changes (adding `is_synthetic` columns)

## Resetting to Baseline

To remove all synthetic data and start fresh:

```bash
# Remove synthetic data
psql -h $DB_HOST -U $DB_USER -d medication_platform -f data/synthetic/reset.sql

# Re-seed
psql -h $DB_HOST -U $DB_USER -d medication_platform -f data/synthetic/seed.sql
```

The reset script deletes all rows where `is_synthetic = TRUE`, respecting
foreign key constraints (children deleted before parents).

## Schema Additions

The seed script adds an `is_synthetic BOOLEAN NOT NULL DEFAULT FALSE`
column to these tables (idempotent, only if not already present):

- `locations`
- `medications`
- `inventory_lots`
- `inventory_levels`
- `consumption_history`
- `suppliers`
- `supplier_medications`
- `supplier_shortage_events`
- `detection_events`
- `orchestrator_workflows`
- `recommendations`
- `tasks`
- `task_state_log`

Existing non-synthetic data defaults to `FALSE` and is unaffected.
