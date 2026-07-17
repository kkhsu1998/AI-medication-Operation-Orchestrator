-- =============================================================================
-- Synthetic Data Seed Script
-- =============================================================================
-- Deterministic Random Seed: 42
-- This script plants synthetic data for demonstration and testing.
-- It is IDEMPOTENT: safe to run multiple times (uses ON CONFLICT DO NOTHING).
-- Contains NO patient data.
-- All synthetic records are labeled with is_synthetic = TRUE.
--
-- Planted patterns:
--   1. Weekly seasonality (higher consumption Mon-Fri, lower Sat-Sun)
--   2. Demand surge event (days 60-67, Lisinopril at Downtown Pharmacy)
--   3. Confirmed stockout period (days 70-77, Metformin at Westside Clinic)
--   4. Supplier shortage event (PharmaCorp, Amoxicillin, days 50-65)
--   5. Delivery failure history (failed task for Atorvastatin transfer)
--
-- Reset instructions: Run the companion reset script (reset.sql) first,
-- then re-run this script to restore baseline synthetic data.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Step 0: Add is_synthetic column to relevant tables (idempotent DDL)
-- ---------------------------------------------------------------------------

DO $$
BEGIN
    -- locations
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'locations' AND column_name = 'is_synthetic') THEN
        ALTER TABLE locations ADD COLUMN is_synthetic BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
    -- medications
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'medications' AND column_name = 'is_synthetic') THEN
        ALTER TABLE medications ADD COLUMN is_synthetic BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
    -- inventory_lots
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'inventory_lots' AND column_name = 'is_synthetic') THEN
        ALTER TABLE inventory_lots ADD COLUMN is_synthetic BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
    -- inventory_levels
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'inventory_levels' AND column_name = 'is_synthetic') THEN
        ALTER TABLE inventory_levels ADD COLUMN is_synthetic BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
    -- consumption_history
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'consumption_history' AND column_name = 'is_synthetic') THEN
        ALTER TABLE consumption_history ADD COLUMN is_synthetic BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
    -- suppliers
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'suppliers' AND column_name = 'is_synthetic') THEN
        ALTER TABLE suppliers ADD COLUMN is_synthetic BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
    -- supplier_medications
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'supplier_medications' AND column_name = 'is_synthetic') THEN
        ALTER TABLE supplier_medications ADD COLUMN is_synthetic BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
    -- supplier_shortage_events
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'supplier_shortage_events' AND column_name = 'is_synthetic') THEN
        ALTER TABLE supplier_shortage_events ADD COLUMN is_synthetic BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
    -- tasks
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'tasks' AND column_name = 'is_synthetic') THEN
        ALTER TABLE tasks ADD COLUMN is_synthetic BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
    -- task_state_log
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'task_state_log' AND column_name = 'is_synthetic') THEN
        ALTER TABLE task_state_log ADD COLUMN is_synthetic BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- Step 1: Locations (5 locations)
-- ---------------------------------------------------------------------------
-- Using deterministic UUIDs derived from seed 42 for reproducibility.

INSERT INTO locations (location_id, name, location_type, is_active, is_synthetic)
VALUES
    ('a0000000-0000-4000-a000-000000000001', 'Downtown Pharmacy',     'pharmacy',   TRUE, TRUE),
    ('a0000000-0000-4000-a000-000000000002', 'Westside Clinic',       'pharmacy',   TRUE, TRUE),
    ('a0000000-0000-4000-a000-000000000003', 'Central Hospital Ward', 'ward',       TRUE, TRUE),
    ('a0000000-0000-4000-a000-000000000004', 'North Distribution Hub','warehouse',  TRUE, TRUE),
    ('a0000000-0000-4000-a000-000000000005', 'East Campus Pharmacy',  'pharmacy',   TRUE, TRUE)
ON CONFLICT (name) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Step 2: Medications (10 medications)
-- ---------------------------------------------------------------------------

INSERT INTO medications (medication_id, ndc, name, generic_name, unit_of_measure, is_active, is_synthetic)
VALUES
    ('b0000000-0000-4000-b000-000000000001', '00071-0155-23', 'Lisinopril 10mg',    'lisinopril',       'tablet',  TRUE, TRUE),
    ('b0000000-0000-4000-b000-000000000002', '00093-7146-01', 'Metformin 500mg',    'metformin',        'tablet',  TRUE, TRUE),
    ('b0000000-0000-4000-b000-000000000003', '00093-2264-01', 'Amoxicillin 500mg',  'amoxicillin',      'capsule', TRUE, TRUE),
    ('b0000000-0000-4000-b000-000000000004', '00071-0156-23', 'Atorvastatin 20mg',  'atorvastatin',     'tablet',  TRUE, TRUE),
    ('b0000000-0000-4000-b000-000000000005', '00591-0405-01', 'Omeprazole 20mg',    'omeprazole',       'capsule', TRUE, TRUE),
    ('b0000000-0000-4000-b000-000000000006', '00093-0058-01', 'Amlodipine 5mg',     'amlodipine',       'tablet',  TRUE, TRUE),
    ('b0000000-0000-4000-b000-000000000007', '00378-1800-01', 'Levothyroxine 50mcg','levothyroxine',    'tablet',  TRUE, TRUE),
    ('b0000000-0000-4000-b000-000000000008', '65862-0586-01', 'Albuterol HFA',      'albuterol sulfate','inhaler', TRUE, TRUE),
    ('b0000000-0000-4000-b000-000000000009', '00093-3147-01', 'Gabapentin 300mg',   'gabapentin',       'capsule', TRUE, TRUE),
    ('b0000000-0000-4000-b000-000000000010', '00591-2234-01', 'Hydrochlorothiazide 25mg','hydrochlorothiazide','tablet', TRUE, TRUE)
ON CONFLICT (ndc) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Step 3: Suppliers (3 suppliers)
-- ---------------------------------------------------------------------------

INSERT INTO suppliers (supplier_id, name, lead_time_days, is_active, is_synthetic)
VALUES
    ('c0000000-0000-4000-c000-000000000001', 'PharmaCorp Distribution',  3, TRUE, TRUE),
    ('c0000000-0000-4000-c000-000000000002', 'MedLine Wholesale',        5, TRUE, TRUE),
    ('c0000000-0000-4000-c000-000000000003', 'National Drug Supply',     7, TRUE, TRUE)
ON CONFLICT (name) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Step 4: Supplier-Medication relationships
-- ---------------------------------------------------------------------------

INSERT INTO supplier_medications (supplier_id, medication_id, unit_cost, is_preferred, is_synthetic)
VALUES
    -- PharmaCorp supplies 6 medications (preferred for most)
    ('c0000000-0000-4000-c000-000000000001', 'b0000000-0000-4000-b000-000000000001', 0.1500, TRUE,  TRUE),
    ('c0000000-0000-4000-c000-000000000001', 'b0000000-0000-4000-b000-000000000002', 0.0800, TRUE,  TRUE),
    ('c0000000-0000-4000-c000-000000000001', 'b0000000-0000-4000-b000-000000000003', 0.4500, TRUE,  TRUE),
    ('c0000000-0000-4000-c000-000000000001', 'b0000000-0000-4000-b000-000000000004', 0.2200, TRUE,  TRUE),
    ('c0000000-0000-4000-c000-000000000001', 'b0000000-0000-4000-b000-000000000005', 0.3000, TRUE,  TRUE),
    ('c0000000-0000-4000-c000-000000000001', 'b0000000-0000-4000-b000-000000000006', 0.1200, TRUE,  TRUE),
    -- MedLine supplies 5 medications
    ('c0000000-0000-4000-c000-000000000002', 'b0000000-0000-4000-b000-000000000003', 0.5000, FALSE, TRUE),
    ('c0000000-0000-4000-c000-000000000002', 'b0000000-0000-4000-b000-000000000007', 0.2800, TRUE,  TRUE),
    ('c0000000-0000-4000-c000-000000000002', 'b0000000-0000-4000-b000-000000000008', 8.5000, TRUE,  TRUE),
    ('c0000000-0000-4000-c000-000000000002', 'b0000000-0000-4000-b000-000000000009', 0.1800, TRUE,  TRUE),
    ('c0000000-0000-4000-c000-000000000002', 'b0000000-0000-4000-b000-000000000010', 0.0600, TRUE,  TRUE),
    -- National Drug Supply as backup for high-volume meds
    ('c0000000-0000-4000-c000-000000000003', 'b0000000-0000-4000-b000-000000000001', 0.1700, FALSE, TRUE),
    ('c0000000-0000-4000-c000-000000000003', 'b0000000-0000-4000-b000-000000000002', 0.0900, FALSE, TRUE),
    ('c0000000-0000-4000-c000-000000000003', 'b0000000-0000-4000-b000-000000000004', 0.2500, FALSE, TRUE)
ON CONFLICT (supplier_id, medication_id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Step 5: Inventory Lots (multiple lots per medication per location)
-- ---------------------------------------------------------------------------
-- Each location gets 2-3 lots per medication with staggered expiration dates.
-- Lot quantities represent current on-hand after 90 days of consumption.

INSERT INTO inventory_lots (lot_id, medication_id, location_id, lot_number, quantity, expiration_date, received_at, is_synthetic)
VALUES
    -- Downtown Pharmacy - Lisinopril (demand surge target, lower stock)
    ('d0000000-0000-4000-d000-000000000001', 'b0000000-0000-4000-b000-000000000001', 'a0000000-0000-4000-a000-000000000001', 'LOT-LIS-001', 120.00, '2027-03-15', '2026-04-01', TRUE),
    ('d0000000-0000-4000-d000-000000000002', 'b0000000-0000-4000-b000-000000000001', 'a0000000-0000-4000-a000-000000000001', 'LOT-LIS-002',  80.00, '2027-06-30', '2026-05-15', TRUE),
    -- Downtown Pharmacy - Metformin
    ('d0000000-0000-4000-d000-000000000003', 'b0000000-0000-4000-b000-000000000002', 'a0000000-0000-4000-a000-000000000001', 'LOT-MET-001', 200.00, '2027-04-20', '2026-04-10', TRUE),
    ('d0000000-0000-4000-d000-000000000004', 'b0000000-0000-4000-b000-000000000002', 'a0000000-0000-4000-a000-000000000001', 'LOT-MET-002', 150.00, '2027-08-15', '2026-06-01', TRUE),
    -- Downtown Pharmacy - Amoxicillin (supplier shortage target)
    ('d0000000-0000-4000-d000-000000000005', 'b0000000-0000-4000-b000-000000000003', 'a0000000-0000-4000-a000-000000000001', 'LOT-AMX-001',  50.00, '2026-12-31', '2026-04-20', TRUE),
    -- Westside Clinic - Metformin (stockout target, depleted)
    ('d0000000-0000-4000-d000-000000000006', 'b0000000-0000-4000-b000-000000000002', 'a0000000-0000-4000-a000-000000000002', 'LOT-MET-003',   0.00, '2027-02-28', '2026-04-05', TRUE),
    ('d0000000-0000-4000-d000-000000000007', 'b0000000-0000-4000-b000-000000000002', 'a0000000-0000-4000-a000-000000000002', 'LOT-MET-004',   0.00, '2027-05-10', '2026-05-20', TRUE),
    -- Westside Clinic - Atorvastatin (delivery failure target)
    ('d0000000-0000-4000-d000-000000000008', 'b0000000-0000-4000-b000-000000000004', 'a0000000-0000-4000-a000-000000000002', 'LOT-ATV-001', 180.00, '2027-07-01', '2026-04-15', TRUE),
    ('d0000000-0000-4000-d000-000000000009', 'b0000000-0000-4000-b000-000000000004', 'a0000000-0000-4000-a000-000000000002', 'LOT-ATV-002',  60.00, '2027-09-30', '2026-06-10', TRUE),
    -- Central Hospital Ward - high volume, multiple lots
    ('d0000000-0000-4000-d000-000000000010', 'b0000000-0000-4000-b000-000000000001', 'a0000000-0000-4000-a000-000000000003', 'LOT-LIS-003', 300.00, '2027-05-01', '2026-04-01', TRUE),
    ('d0000000-0000-4000-d000-000000000011', 'b0000000-0000-4000-b000-000000000005', 'a0000000-0000-4000-a000-000000000003', 'LOT-OMP-001', 100.00, '2027-03-20', '2026-04-10', TRUE),
    ('d0000000-0000-4000-d000-000000000012', 'b0000000-0000-4000-b000-000000000006', 'a0000000-0000-4000-a000-000000000003', 'LOT-AML-001', 250.00, '2027-08-15', '2026-05-01', TRUE),
    -- North Distribution Hub - large warehouse stock
    ('d0000000-0000-4000-d000-000000000013', 'b0000000-0000-4000-b000-000000000001', 'a0000000-0000-4000-a000-000000000004', 'LOT-LIS-004', 500.00, '2027-06-01', '2026-04-01', TRUE),
    ('d0000000-0000-4000-d000-000000000014', 'b0000000-0000-4000-b000-000000000002', 'a0000000-0000-4000-a000-000000000004', 'LOT-MET-005', 800.00, '2027-07-15', '2026-04-01', TRUE),
    ('d0000000-0000-4000-d000-000000000015', 'b0000000-0000-4000-b000-000000000003', 'a0000000-0000-4000-a000-000000000004', 'LOT-AMX-002', 400.00, '2027-04-30', '2026-04-15', TRUE),
    ('d0000000-0000-4000-d000-000000000016', 'b0000000-0000-4000-b000-000000000004', 'a0000000-0000-4000-a000-000000000004', 'LOT-ATV-003', 600.00, '2027-09-01', '2026-05-01', TRUE),
    ('d0000000-0000-4000-d000-000000000017', 'b0000000-0000-4000-b000-000000000007', 'a0000000-0000-4000-a000-000000000004', 'LOT-LEV-001', 350.00, '2027-05-20', '2026-04-10', TRUE),
    ('d0000000-0000-4000-d000-000000000018', 'b0000000-0000-4000-b000-000000000008', 'a0000000-0000-4000-a000-000000000004', 'LOT-ALB-001', 200.00, '2027-11-30', '2026-06-01', TRUE),
    -- East Campus Pharmacy
    ('d0000000-0000-4000-d000-000000000019', 'b0000000-0000-4000-b000-000000000009', 'a0000000-0000-4000-a000-000000000005', 'LOT-GAB-001', 180.00, '2027-04-15', '2026-04-20', TRUE),
    ('d0000000-0000-4000-d000-000000000020', 'b0000000-0000-4000-b000-000000000010', 'a0000000-0000-4000-a000-000000000005', 'LOT-HCT-001', 220.00, '2027-06-30', '2026-05-01', TRUE),
    ('d0000000-0000-4000-d000-000000000021', 'b0000000-0000-4000-b000-000000000005', 'a0000000-0000-4000-a000-000000000005', 'LOT-OMP-002', 140.00, '2027-08-01', '2026-05-15', TRUE)
ON CONFLICT (medication_id, location_id, lot_number) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Step 6: Inventory Levels (aggregated on-hand per medication+location)
-- ---------------------------------------------------------------------------

INSERT INTO inventory_levels (inventory_level_id, medication_id, location_id, quantity_on_hand, is_synthetic)
VALUES
    -- Downtown Pharmacy
    ('e0000000-0000-4000-e000-000000000001', 'b0000000-0000-4000-b000-000000000001', 'a0000000-0000-4000-a000-000000000001', 200.00, TRUE),
    ('e0000000-0000-4000-e000-000000000002', 'b0000000-0000-4000-b000-000000000002', 'a0000000-0000-4000-a000-000000000001', 350.00, TRUE),
    ('e0000000-0000-4000-e000-000000000003', 'b0000000-0000-4000-b000-000000000003', 'a0000000-0000-4000-a000-000000000001',  50.00, TRUE),
    -- Westside Clinic
    ('e0000000-0000-4000-e000-000000000004', 'b0000000-0000-4000-b000-000000000002', 'a0000000-0000-4000-a000-000000000002',   0.00, TRUE),
    ('e0000000-0000-4000-e000-000000000005', 'b0000000-0000-4000-b000-000000000004', 'a0000000-0000-4000-a000-000000000002', 240.00, TRUE),
    -- Central Hospital Ward
    ('e0000000-0000-4000-e000-000000000006', 'b0000000-0000-4000-b000-000000000001', 'a0000000-0000-4000-a000-000000000003', 300.00, TRUE),
    ('e0000000-0000-4000-e000-000000000007', 'b0000000-0000-4000-b000-000000000005', 'a0000000-0000-4000-a000-000000000003', 100.00, TRUE),
    ('e0000000-0000-4000-e000-000000000008', 'b0000000-0000-4000-b000-000000000006', 'a0000000-0000-4000-a000-000000000003', 250.00, TRUE),
    -- North Distribution Hub
    ('e0000000-0000-4000-e000-000000000009', 'b0000000-0000-4000-b000-000000000001', 'a0000000-0000-4000-a000-000000000004', 500.00, TRUE),
    ('e0000000-0000-4000-e000-000000000010', 'b0000000-0000-4000-b000-000000000002', 'a0000000-0000-4000-a000-000000000004', 800.00, TRUE),
    ('e0000000-0000-4000-e000-000000000011', 'b0000000-0000-4000-b000-000000000003', 'a0000000-0000-4000-a000-000000000004', 400.00, TRUE),
    ('e0000000-0000-4000-e000-000000000012', 'b0000000-0000-4000-b000-000000000004', 'a0000000-0000-4000-a000-000000000004', 600.00, TRUE),
    ('e0000000-0000-4000-e000-000000000013', 'b0000000-0000-4000-b000-000000000007', 'a0000000-0000-4000-a000-000000000004', 350.00, TRUE),
    ('e0000000-0000-4000-e000-000000000014', 'b0000000-0000-4000-b000-000000000008', 'a0000000-0000-4000-a000-000000000004', 200.00, TRUE),
    -- East Campus Pharmacy
    ('e0000000-0000-4000-e000-000000000015', 'b0000000-0000-4000-b000-000000000009', 'a0000000-0000-4000-a000-000000000005', 180.00, TRUE),
    ('e0000000-0000-4000-e000-000000000016', 'b0000000-0000-4000-b000-000000000010', 'a0000000-0000-4000-a000-000000000005', 220.00, TRUE),
    ('e0000000-0000-4000-e000-000000000017', 'b0000000-0000-4000-b000-000000000005', 'a0000000-0000-4000-a000-000000000005', 140.00, TRUE)
ON CONFLICT (medication_id, location_id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Step 7: Consumption History (90 days with planted patterns)
-- ---------------------------------------------------------------------------
-- Deterministic seed: 42
-- Uses setseed(0.42) for pg random() to be reproducible.
-- Base date: 90 days ago from a fixed reference (2026-04-18 = day 0).
--
-- Patterns planted:
--   - Weekly seasonality: weekday multiplier 1.0, weekend multiplier 0.6
--   - Demand surge: Lisinopril at Downtown Pharmacy, days 60-67 (3x normal)
--   - Stockout: Metformin at Westside Clinic, days 70-77 (quantity=0, is_stockout_period=TRUE)

-- Use a DO block with setseed for deterministic generation
DO $$
DECLARE
    base_date DATE := '2026-04-18';
    day_offset INTEGER;
    curr_date DATE;
    dow INTEGER;  -- day of week (0=Sun, 6=Sat)
    weekday_mult NUMERIC;
    base_qty NUMERIC;
    final_qty NUMERIC;
    -- Medication-location pairs and their base daily consumption
    -- Format: medication_id, location_id, base_daily_qty
BEGIN
    -- Set deterministic seed
    PERFORM setseed(0.42);

    FOR day_offset IN 0..89 LOOP
        curr_date := base_date + day_offset;
        dow := EXTRACT(DOW FROM curr_date)::INTEGER;  -- 0=Sun, 6=Sat

        -- Weekly seasonality multiplier
        IF dow IN (0, 6) THEN
            weekday_mult := 0.6;
        ELSE
            weekday_mult := 1.0;
        END IF;

        -- === Lisinopril at Downtown Pharmacy (base: 15/day) ===
        base_qty := 15.0;
        IF day_offset BETWEEN 60 AND 67 THEN
            -- DEMAND SURGE: 3x normal consumption
            final_qty := ROUND((base_qty * 3.0 * weekday_mult + (random() * 4 - 2))::NUMERIC, 2);
        ELSE
            final_qty := ROUND((base_qty * weekday_mult + (random() * 6 - 3))::NUMERIC, 2);
        END IF;
        IF final_qty < 0 THEN final_qty := 0; END IF;
        INSERT INTO consumption_history (medication_id, location_id, consumption_date, quantity, is_stockout_period, is_synthetic)
        VALUES ('b0000000-0000-4000-b000-000000000001', 'a0000000-0000-4000-a000-000000000001', curr_date, final_qty, FALSE, TRUE)
        ON CONFLICT (medication_id, location_id, consumption_date) DO NOTHING;

        -- === Metformin at Downtown Pharmacy (base: 20/day) ===
        base_qty := 20.0;
        final_qty := ROUND((base_qty * weekday_mult + (random() * 8 - 4))::NUMERIC, 2);
        IF final_qty < 0 THEN final_qty := 0; END IF;
        INSERT INTO consumption_history (medication_id, location_id, consumption_date, quantity, is_stockout_period, is_synthetic)
        VALUES ('b0000000-0000-4000-b000-000000000002', 'a0000000-0000-4000-a000-000000000001', curr_date, final_qty, FALSE, TRUE)
        ON CONFLICT (medication_id, location_id, consumption_date) DO NOTHING;

        -- === Amoxicillin at Downtown Pharmacy (base: 8/day) ===
        base_qty := 8.0;
        final_qty := ROUND((base_qty * weekday_mult + (random() * 4 - 2))::NUMERIC, 2);
        IF final_qty < 0 THEN final_qty := 0; END IF;
        INSERT INTO consumption_history (medication_id, location_id, consumption_date, quantity, is_stockout_period, is_synthetic)
        VALUES ('b0000000-0000-4000-b000-000000000003', 'a0000000-0000-4000-a000-000000000001', curr_date, final_qty, FALSE, TRUE)
        ON CONFLICT (medication_id, location_id, consumption_date) DO NOTHING;

        -- === Metformin at Westside Clinic (base: 18/day) — STOCKOUT days 70-77 ===
        base_qty := 18.0;
        IF day_offset BETWEEN 70 AND 77 THEN
            -- STOCKOUT PERIOD: zero consumption, flagged
            INSERT INTO consumption_history (medication_id, location_id, consumption_date, quantity, is_stockout_period, is_synthetic)
            VALUES ('b0000000-0000-4000-b000-000000000002', 'a0000000-0000-4000-a000-000000000002', curr_date, 0.00, TRUE, TRUE)
            ON CONFLICT (medication_id, location_id, consumption_date) DO NOTHING;
        ELSE
            final_qty := ROUND((base_qty * weekday_mult + (random() * 6 - 3))::NUMERIC, 2);
            IF final_qty < 0 THEN final_qty := 0; END IF;
            INSERT INTO consumption_history (medication_id, location_id, consumption_date, quantity, is_stockout_period, is_synthetic)
            VALUES ('b0000000-0000-4000-b000-000000000002', 'a0000000-0000-4000-a000-000000000002', curr_date, final_qty, FALSE, TRUE)
            ON CONFLICT (medication_id, location_id, consumption_date) DO NOTHING;
        END IF;

        -- === Atorvastatin at Westside Clinic (base: 12/day) ===
        base_qty := 12.0;
        final_qty := ROUND((base_qty * weekday_mult + (random() * 4 - 2))::NUMERIC, 2);
        IF final_qty < 0 THEN final_qty := 0; END IF;
        INSERT INTO consumption_history (medication_id, location_id, consumption_date, quantity, is_stockout_period, is_synthetic)
        VALUES ('b0000000-0000-4000-b000-000000000004', 'a0000000-0000-4000-a000-000000000002', curr_date, final_qty, FALSE, TRUE)
        ON CONFLICT (medication_id, location_id, consumption_date) DO NOTHING;

        -- === Lisinopril at Central Hospital Ward (base: 25/day) ===
        base_qty := 25.0;
        final_qty := ROUND((base_qty * weekday_mult + (random() * 8 - 4))::NUMERIC, 2);
        IF final_qty < 0 THEN final_qty := 0; END IF;
        INSERT INTO consumption_history (medication_id, location_id, consumption_date, quantity, is_stockout_period, is_synthetic)
        VALUES ('b0000000-0000-4000-b000-000000000001', 'a0000000-0000-4000-a000-000000000003', curr_date, final_qty, FALSE, TRUE)
        ON CONFLICT (medication_id, location_id, consumption_date) DO NOTHING;

        -- === Omeprazole at Central Hospital Ward (base: 10/day) ===
        base_qty := 10.0;
        final_qty := ROUND((base_qty * weekday_mult + (random() * 4 - 2))::NUMERIC, 2);
        IF final_qty < 0 THEN final_qty := 0; END IF;
        INSERT INTO consumption_history (medication_id, location_id, consumption_date, quantity, is_stockout_period, is_synthetic)
        VALUES ('b0000000-0000-4000-b000-000000000005', 'a0000000-0000-4000-a000-000000000003', curr_date, final_qty, FALSE, TRUE)
        ON CONFLICT (medication_id, location_id, consumption_date) DO NOTHING;

        -- === Amlodipine at Central Hospital Ward (base: 14/day) ===
        base_qty := 14.0;
        final_qty := ROUND((base_qty * weekday_mult + (random() * 4 - 2))::NUMERIC, 2);
        IF final_qty < 0 THEN final_qty := 0; END IF;
        INSERT INTO consumption_history (medication_id, location_id, consumption_date, quantity, is_stockout_period, is_synthetic)
        VALUES ('b0000000-0000-4000-b000-000000000006', 'a0000000-0000-4000-a000-000000000003', curr_date, final_qty, FALSE, TRUE)
        ON CONFLICT (medication_id, location_id, consumption_date) DO NOTHING;

        -- === Gabapentin at East Campus Pharmacy (base: 10/day) ===
        base_qty := 10.0;
        final_qty := ROUND((base_qty * weekday_mult + (random() * 4 - 2))::NUMERIC, 2);
        IF final_qty < 0 THEN final_qty := 0; END IF;
        INSERT INTO consumption_history (medication_id, location_id, consumption_date, quantity, is_stockout_period, is_synthetic)
        VALUES ('b0000000-0000-4000-b000-000000000009', 'a0000000-0000-4000-a000-000000000005', curr_date, final_qty, FALSE, TRUE)
        ON CONFLICT (medication_id, location_id, consumption_date) DO NOTHING;

        -- === Hydrochlorothiazide at East Campus Pharmacy (base: 12/day) ===
        base_qty := 12.0;
        final_qty := ROUND((base_qty * weekday_mult + (random() * 4 - 2))::NUMERIC, 2);
        IF final_qty < 0 THEN final_qty := 0; END IF;
        INSERT INTO consumption_history (medication_id, location_id, consumption_date, quantity, is_stockout_period, is_synthetic)
        VALUES ('b0000000-0000-4000-b000-000000000010', 'a0000000-0000-4000-a000-000000000005', curr_date, final_qty, FALSE, TRUE)
        ON CONFLICT (medication_id, location_id, consumption_date) DO NOTHING;

        -- === Omeprazole at East Campus Pharmacy (base: 7/day) ===
        base_qty := 7.0;
        final_qty := ROUND((base_qty * weekday_mult + (random() * 3 - 1.5))::NUMERIC, 2);
        IF final_qty < 0 THEN final_qty := 0; END IF;
        INSERT INTO consumption_history (medication_id, location_id, consumption_date, quantity, is_stockout_period, is_synthetic)
        VALUES ('b0000000-0000-4000-b000-000000000005', 'a0000000-0000-4000-a000-000000000005', curr_date, final_qty, FALSE, TRUE)
        ON CONFLICT (medication_id, location_id, consumption_date) DO NOTHING;

    END LOOP;
END
$$;

-- ---------------------------------------------------------------------------
-- Step 8: Supplier Shortage Event
-- ---------------------------------------------------------------------------
-- Pattern: PharmaCorp cannot supply Amoxicillin for 15 days (days 50-65).
-- This forces the system to consider alternate supplier (MedLine) or transfers.

INSERT INTO supplier_shortage_events (shortage_event_id, supplier_id, medication_id, started_at, resolved_at, notice_text, summary, is_synthetic)
VALUES (
    'f0000000-0000-4000-f000-000000000001',
    'c0000000-0000-4000-c000-000000000001',  -- PharmaCorp
    'b0000000-0000-4000-b000-000000000003',  -- Amoxicillin
    '2026-06-06 08:00:00+00',                -- day 50 from base_date
    '2026-06-21 16:00:00+00',                -- day 65 resolved
    'Due to a manufacturing quality hold at our primary facility, Amoxicillin 500mg capsules (NDC 00093-2264-01) will be unavailable for approximately 2-3 weeks. We are working to resolve the issue and will notify you when supply resumes. Alternative: contact MedLine Wholesale for interim supply.',
    'PharmaCorp: Amoxicillin 500mg unavailable ~2-3 weeks due to manufacturing quality hold. Suggests MedLine as interim source.',
    TRUE
)
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- Step 9: Delivery Failure History (Task with failed state)
-- ---------------------------------------------------------------------------
-- Pattern: An internal transfer of Atorvastatin from North Hub to Westside Clinic
-- was attempted but failed due to a logistics issue.
-- This requires a detection_event, workflow, recommendation, and task chain.

-- Add is_synthetic to remaining tables needed for the delivery failure chain
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'detection_events' AND column_name = 'is_synthetic') THEN
        ALTER TABLE detection_events ADD COLUMN is_synthetic BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'orchestrator_workflows' AND column_name = 'is_synthetic') THEN
        ALTER TABLE orchestrator_workflows ADD COLUMN is_synthetic BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'recommendations' AND column_name = 'is_synthetic') THEN
        ALTER TABLE recommendations ADD COLUMN is_synthetic BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
END
$$;

-- Detection event for the delivery failure scenario
INSERT INTO detection_events (detection_event_id, detection_type, medication_id, location_id, detected_at, demand_signal_source, details, correlation_id, is_synthetic)
VALUES (
    'f1000000-0000-4000-f100-000000000001',
    'low_days_of_supply',
    'b0000000-0000-4000-b000-000000000004',  -- Atorvastatin
    'a0000000-0000-4000-a000-000000000002',  -- Westside Clinic
    '2026-06-20 10:00:00+00',
    'deterministic_baseline',
    '{"days_of_supply": 5, "threshold_days": 14, "daily_consumption_avg": 12.0}',
    'f1000000-0000-4000-f100-000000000099',
    TRUE
)
ON CONFLICT DO NOTHING;

-- Orchestrator workflow
INSERT INTO orchestrator_workflows (workflow_id, correlation_id, current_state, medication_id, location_id, detection_type, demand_signal_source, started_at, is_synthetic)
VALUES (
    'f2000000-0000-4000-f200-000000000001',
    'f1000000-0000-4000-f100-000000000099',
    'completed',
    'b0000000-0000-4000-b000-000000000004',
    'a0000000-0000-4000-a000-000000000002',
    'low_days_of_supply',
    'deterministic_baseline',
    '2026-06-20 10:00:00+00',
    TRUE
)
ON CONFLICT DO NOTHING;

-- Recommendation
INSERT INTO recommendations (recommendation_id, workflow_id, correlation_id, version, demand_signal_source, recommended_option, score, scoring_weights, evidence, scoring_breakdown, rejected_options, feasibility_result, input_snapshot, is_synthetic)
VALUES (
    'f3000000-0000-4000-f300-000000000001',
    'f2000000-0000-4000-f200-000000000001',
    'f1000000-0000-4000-f100-000000000099',
    1,
    'deterministic_baseline',
    'internal_transfer',
    0.8500,
    '{"availability": 0.4, "lead_time": 0.3, "cost": 0.2, "waste_reduction": 0.1}',
    '{"source_quantity": 600, "destination_days_of_supply": 5}',
    '{"availability": 0.95, "lead_time": 0.90, "cost": 0.70, "waste_reduction": 0.60}',
    '[{"option": "procurement", "reason": "lead_time_too_long", "score": 0.65}]',
    '{"feasible": true, "source_has_sufficient_stock": true}',
    '{"medication": "Atorvastatin 20mg", "destination": "Westside Clinic", "quantity_needed": 120}',
    TRUE
)
ON CONFLICT DO NOTHING;

-- Task: internal transfer that FAILED
INSERT INTO tasks (task_id, correlation_id, recommendation_id, recommendation_version, task_type, current_state, medication_id, source_location_id, destination_location_id, quantity, assigned_to, description, is_synthetic)
VALUES (
    'f4000000-0000-4000-f400-000000000001',
    'f1000000-0000-4000-f100-000000000099',
    'f3000000-0000-4000-f300-000000000001',
    1,
    'internal_transfer',
    'failed',
    'b0000000-0000-4000-b000-000000000004',  -- Atorvastatin
    'a0000000-0000-4000-a000-000000000004',  -- North Distribution Hub (source)
    'a0000000-0000-4000-a000-000000000002',  -- Westside Clinic (destination)
    120.00,
    'robot-amr-03',
    'Transfer 120 tablets of Atorvastatin 20mg from North Distribution Hub to Westside Clinic to replenish low stock (5 days of supply remaining).',
    TRUE
)
ON CONFLICT (correlation_id, recommendation_version) DO NOTHING;

-- Task state log showing the failure progression
INSERT INTO task_state_log (log_id, task_id, from_state, to_state, actor, reason, transitioned_at, is_synthetic)
VALUES
    ('f5000000-0000-4000-f500-000000000001', 'f4000000-0000-4000-f400-000000000001', NULL, 'requested', 'orchestrator', NULL, '2026-06-20 10:30:00+00', TRUE),
    ('f5000000-0000-4000-f500-000000000002', 'f4000000-0000-4000-f400-000000000001', 'requested', 'assigned', 'task_manager', NULL, '2026-06-20 10:35:00+00', TRUE),
    ('f5000000-0000-4000-f500-000000000003', 'f4000000-0000-4000-f400-000000000001', 'assigned', 'accepted', 'robot-amr-03', NULL, '2026-06-20 10:40:00+00', TRUE),
    ('f5000000-0000-4000-f500-000000000004', 'f4000000-0000-4000-f400-000000000001', 'accepted', 'in_progress', 'robot-amr-03', NULL, '2026-06-20 10:45:00+00', TRUE),
    ('f5000000-0000-4000-f500-000000000005', 'f4000000-0000-4000-f400-000000000001', 'in_progress', 'failed', 'delivery_adapter', 'AMR navigation failure: path blocked in corridor B-7. Retry limit exceeded (3 attempts).', '2026-06-20 11:15:00+00', TRUE)
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- Step 10: Configuration defaults (operational thresholds)
-- ---------------------------------------------------------------------------

INSERT INTO config (key, value, description, updated_by)
VALUES
    ('safety_stock_days', '7', 'Minimum days of supply before triggering low-stock detection', 'synthetic_seed'),
    ('low_dos_threshold_days', '14', 'Days of supply threshold for low_days_of_supply detection', 'synthetic_seed'),
    ('forecast_confidence_threshold', '0.7', 'Minimum confidence score to use ML forecast', 'synthetic_seed'),
    ('scoring_weight_availability', '0.4', 'Weight for availability dimension in option scoring', 'synthetic_seed'),
    ('scoring_weight_lead_time', '0.3', 'Weight for lead time dimension in option scoring', 'synthetic_seed'),
    ('scoring_weight_cost', '0.2', 'Weight for cost dimension in option scoring', 'synthetic_seed'),
    ('scoring_weight_waste_reduction', '0.1', 'Weight for waste reduction dimension in option scoring', 'synthetic_seed')
ON CONFLICT (key) DO NOTHING;

-- ---------------------------------------------------------------------------
-- End of Synthetic Data Seed
-- ---------------------------------------------------------------------------
-- Summary:
--   5 locations, 10 medications, 3 suppliers, 21 inventory lots
--   ~900 consumption_history rows (10 med-location pairs × 90 days)
--   1 supplier shortage event (PharmaCorp/Amoxicillin, days 50-65)
--   1 delivery failure (Atorvastatin transfer, AMR navigation failure)
--   Weekly seasonality embedded in all consumption data
--   Demand surge: Lisinopril at Downtown Pharmacy, days 60-67
--   Stockout: Metformin at Westside Clinic, days 70-77
-- ---------------------------------------------------------------------------
