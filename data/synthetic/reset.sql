-- =============================================================================
-- Synthetic Data Reset Script
-- =============================================================================
-- Removes ALL synthetic data (is_synthetic = TRUE) from the database.
-- Run this before re-running seed.sql to reset to baseline.
-- Safe to run multiple times (idempotent).
--
-- Order respects foreign key constraints (delete children first).
-- =============================================================================

-- Task state log (references tasks)
DELETE FROM task_state_log WHERE is_synthetic = TRUE;

-- Tasks (references recommendations)
DELETE FROM tasks WHERE is_synthetic = TRUE;

-- Recommendations (references orchestrator_workflows)
DELETE FROM recommendations WHERE is_synthetic = TRUE;

-- Orchestrator workflows (references detection_events)
DELETE FROM orchestrator_workflows WHERE is_synthetic = TRUE;

-- Detection events
DELETE FROM detection_events WHERE is_synthetic = TRUE;

-- Supplier shortage events
DELETE FROM supplier_shortage_events WHERE is_synthetic = TRUE;

-- Supplier-medication relationships
DELETE FROM supplier_medications WHERE is_synthetic = TRUE;

-- Suppliers
DELETE FROM suppliers WHERE is_synthetic = TRUE;

-- Consumption history
DELETE FROM consumption_history WHERE is_synthetic = TRUE;

-- Inventory levels
DELETE FROM inventory_levels WHERE is_synthetic = TRUE;

-- Inventory lots
DELETE FROM inventory_lots WHERE is_synthetic = TRUE;

-- Medications
DELETE FROM medications WHERE is_synthetic = TRUE;

-- Locations
DELETE FROM locations WHERE is_synthetic = TRUE;

-- Config entries added by the seed
DELETE FROM config WHERE updated_by = 'synthetic_seed';

-- =============================================================================
-- Reset complete. Run seed.sql to re-populate synthetic data.
-- =============================================================================
