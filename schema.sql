CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =========================================================
-- USERS
-- =========================================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    login VARCHAR(100) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- =========================================================
-- MATERIALS
-- =========================================================

CREATE TABLE IF NOT EXISTS materials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(100),
    unit VARCHAR(50) NOT NULL DEFAULT 't',
    default_price NUMERIC(18, 2) NOT NULL DEFAULT 0,
    supplier VARCHAR(255),
    fraction VARCHAR(100),
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_materials_name ON materials(name);

CREATE TABLE IF NOT EXISTS material_price_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    material_id UUID NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    price NUMERIC(18, 2) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'RUB',
    valid_from DATE NOT NULL,
    valid_to DATE,
    comment TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_material_price_history_material_id
    ON material_price_history(material_id);

CREATE INDEX IF NOT EXISTS idx_material_price_history_valid_from
    ON material_price_history(valid_from);

-- =========================================================
-- PROCESSES
-- =========================================================

CREATE TABLE IF NOT EXISTS processes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(100),
    default_cost NUMERIC(18, 2) NOT NULL DEFAULT 0,
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_processes_name ON processes(name);

CREATE TABLE IF NOT EXISTS process_cost_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_id UUID NOT NULL REFERENCES processes(id) ON DELETE CASCADE,
    cost NUMERIC(18, 2) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'RUB',
    valid_from DATE NOT NULL,
    valid_to DATE,
    comment TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_process_cost_history_process_id
    ON process_cost_history(process_id);

CREATE INDEX IF NOT EXISTS idx_process_cost_history_valid_from
    ON process_cost_history(valid_from);

-- =========================================================
-- RECIPES
-- =========================================================

CREATE TABLE IF NOT EXISTS recipes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(100),
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_recipes_name ON recipes(name);

CREATE TABLE IF NOT EXISTS recipe_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipe_id UUID NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    version_name VARCHAR(255),
    comment TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(recipe_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_recipe_versions_recipe_id
    ON recipe_versions(recipe_id);

CREATE TABLE IF NOT EXISTS recipe_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipe_version_id UUID NOT NULL REFERENCES recipe_versions(id) ON DELETE CASCADE,
    material_id UUID NOT NULL REFERENCES materials(id) ON DELETE RESTRICT,
    process_id UUID REFERENCES processes(id) ON DELETE SET NULL,
    quantity NUMERIC(18, 6) NOT NULL,
    loss_coefficient NUMERIC(18, 6) NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    comment TEXT
);

CREATE TABLE IF NOT EXISTS recipe_item_processes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipe_item_id UUID NOT NULL REFERENCES recipe_items(id) ON DELETE CASCADE,
    process_id UUID NOT NULL REFERENCES processes(id) ON DELETE RESTRICT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    loss_coefficient NUMERIC(18,6) NOT NULL DEFAULT 1,
    comment TEXT
);

ALTER TABLE recipe_item_processes
ADD COLUMN IF NOT EXISTS operation_id UUID
REFERENCES operations(id);


CREATE INDEX IF NOT EXISTS idx_recipe_item_processes_recipe_item_id
    ON recipe_item_processes(recipe_item_id);

CREATE INDEX IF NOT EXISTS idx_recipe_item_processes_process_id
    ON recipe_item_processes(process_id);

CREATE INDEX IF NOT EXISTS idx_recipe_item_processes_operation_id
ON recipe_item_processes(operation_id);


CREATE INDEX IF NOT EXISTS idx_recipe_items_recipe_version_id
    ON recipe_items(recipe_version_id);

CREATE INDEX IF NOT EXISTS idx_recipe_items_material_id
    ON recipe_items(material_id);
-- =========================================================
-- CUSTOMERS
-- =========================================================

CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(100),
    country VARCHAR(100),
    region VARCHAR(100),
    city VARCHAR(100),
    address TEXT,
    default_payment_delay_days INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_customers_name ON customers(name);

-- =========================================================
-- TRANSPORT
-- =========================================================

CREATE TABLE IF NOT EXISTS transport_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) NOT NULL UNIQUE,
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS transport_schemes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transport_type_id UUID NOT NULL REFERENCES transport_types(id),
    name VARCHAR(255) NOT NULL,
    capacity_tons NUMERIC(18,3),
    is_standard BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transport_schemes_transport_type_id
ON transport_schemes(transport_type_id);

CREATE TABLE IF NOT EXISTS transport_extra_cost_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) NOT NULL UNIQUE,
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS transport_rate_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id),
    transport_scheme_id UUID NOT NULL REFERENCES transport_schemes(id),
    price NUMERIC(18,2) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'RUB',
    price_per VARCHAR(50) NOT NULL DEFAULT 'trip',
    valid_from DATE NOT NULL,
    valid_to DATE,
    includes_loading BOOLEAN DEFAULT FALSE,
    includes_unloading BOOLEAN DEFAULT FALSE,
    includes_packaging BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transport_rate_history_customer
ON transport_rate_history(customer_id);

CREATE INDEX IF NOT EXISTS idx_transport_rate_history_scheme
ON transport_rate_history(transport_scheme_id);
-- =========================================================
-- CALCULATIONS
-- =========================================================

CREATE TABLE IF NOT EXISTS calculations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    calculation_number VARCHAR(100),
    name VARCHAR(255) NOT NULL,
    recipe_id UUID REFERENCES recipes(id) ON DELETE SET NULL,
    recipe_version_id UUID REFERENCES recipe_versions(id) ON DELETE SET NULL,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    company_name VARCHAR(255),
    calculation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    delivery_start_date DATE,
    delivery_end_date DATE,
    total_contract_volume NUMERIC(18,3) NOT NULL DEFAULT 0,
    inflation_percent NUMERIC(18,4) NOT NULL DEFAULT 0,
    cost_of_money_percent NUMERIC(18,4) NOT NULL DEFAULT 0,
    overhead_percent NUMERIC(18,4) NOT NULL DEFAULT 0,
    mixing_cost NUMERIC(18,2) NOT NULL DEFAULT 0,
    packaging_cost NUMERIC(18,2) NOT NULL DEFAULT 0,
    base_transport_cost NUMERIC(18,2) NOT NULL DEFAULT 0,
    notes TEXT,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_calculations_customer_id
ON calculations(customer_id);

CREATE INDEX IF NOT EXISTS idx_calculations_recipe_version_id
ON calculations(recipe_version_id);

CREATE INDEX IF NOT EXISTS idx_calculations_calculation_date
ON calculations(calculation_date);

CREATE TABLE IF NOT EXISTS calculation_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    calculation_id UUID NOT NULL REFERENCES calculations(id) ON DELETE CASCADE,
    material_id UUID REFERENCES materials(id) ON DELETE SET NULL,
    material_name_snapshot VARCHAR(255) NOT NULL,
    process_id UUID REFERENCES processes(id) ON DELETE SET NULL,
    process_name_snapshot VARCHAR(255),
    quantity NUMERIC(18,6) NOT NULL,
    loss_coefficient NUMERIC(18,6) NOT NULL DEFAULT 1,
    material_price_snapshot NUMERIC(18,2) NOT NULL DEFAULT 0,
    process_cost_snapshot NUMERIC(18,2) NOT NULL DEFAULT 0,
    calculated_component_cost NUMERIC(18,2) NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_calculation_items_calculation_id
ON calculation_items(calculation_id);

CREATE TABLE IF NOT EXISTS delivery_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    calculation_id UUID NOT NULL REFERENCES calculations(id) ON DELETE CASCADE,
    batch_number INTEGER NOT NULL DEFAULT 1,
    delivery_date DATE NOT NULL,
    volume_tons NUMERIC(18,3) NOT NULL,
    transport_scheme_id UUID REFERENCES transport_schemes(id) ON DELETE SET NULL,
    transport_rate_snapshot NUMERIC(18,2) NOT NULL DEFAULT 0,
    payment_delay_days INTEGER NOT NULL DEFAULT 0,
    money_days INTEGER NOT NULL DEFAULT 0,
    money_cost_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    comment TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_delivery_batches_calculation_id
ON delivery_batches(calculation_id);

CREATE TABLE IF NOT EXISTS delivery_batch_extra_costs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    delivery_batch_id UUID NOT NULL REFERENCES delivery_batches(id) ON DELETE CASCADE,
    transport_extra_cost_type_id UUID REFERENCES transport_extra_cost_types(id) ON DELETE SET NULL,
    amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    comment TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_delivery_batch_extra_costs_batch_id
ON delivery_batch_extra_costs(delivery_batch_id);

CREATE TABLE IF NOT EXISTS calculation_extra_costs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    calculation_id UUID NOT NULL REFERENCES calculations(id) ON DELETE CASCADE,
    transport_extra_cost_type_id UUID REFERENCES transport_extra_cost_types(id) ON DELETE SET NULL,
    amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    comment TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_calculation_extra_costs_calculation_id
ON calculation_extra_costs(calculation_id);

CREATE TABLE IF NOT EXISTS calculation_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    calculation_id UUID NOT NULL UNIQUE REFERENCES calculations(id) ON DELETE CASCADE,
    production_cost_total NUMERIC(18,2) NOT NULL DEFAULT 0,
    production_cost_per_ton NUMERIC(18,2) NOT NULL DEFAULT 0,
    transport_cost_total NUMERIC(18,2) NOT NULL DEFAULT 0,
    extra_logistics_cost_total NUMERIC(18,2) NOT NULL DEFAULT 0,
    money_cost_total NUMERIC(18,2) NOT NULL DEFAULT 0,
    overhead_cost_total NUMERIC(18,2) NOT NULL DEFAULT 0,
    final_cost_total NUMERIC(18,2) NOT NULL DEFAULT 0,
    final_cost_per_ton NUMERIC(18,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
-- =========================================================
-- UPDATED_AT TRIGGERS
-- =========================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_materials_updated_at ON materials;
CREATE TRIGGER trg_materials_updated_at
BEFORE UPDATE ON materials
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_processes_updated_at ON processes;
CREATE TRIGGER trg_processes_updated_at
BEFORE UPDATE ON processes
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_recipes_updated_at ON recipes;
CREATE TRIGGER trg_recipes_updated_at
BEFORE UPDATE ON recipes
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_customers_updated_at ON customers;
CREATE TRIGGER trg_customers_updated_at
BEFORE UPDATE ON customers
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_transport_schemes_updated_at ON transport_schemes;
CREATE TRIGGER trg_transport_schemes_updated_at
BEFORE UPDATE ON transport_schemes
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_calculations_updated_at ON calculations;
CREATE TRIGGER trg_calculations_updated_at
BEFORE UPDATE ON calculations
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
CREATE TABLE IF NOT EXISTS packaging_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(100),
    capacity_value NUMERIC(18,3),
    capacity_unit VARCHAR(50),
    cost_per_ton NUMERIC(18,2) NOT NULL DEFAULT 0,
    package_price NUMERIC(18,2) NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE packaging_types
ADD COLUMN IF NOT EXISTS package_price NUMERIC(18,2) NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_packaging_types_name
    ON packaging_types(name);

DROP TRIGGER IF EXISTS trg_packaging_types_updated_at ON packaging_types;
CREATE TRIGGER trg_packaging_types_updated_at
BEFORE UPDATE ON packaging_types
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
CREATE TABLE IF NOT EXISTS saved_calculations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipe_id UUID REFERENCES recipes(id) ON DELETE SET NULL,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    customer_name_snapshot VARCHAR(255),
    recipe_version_id UUID REFERENCES recipe_versions(id) ON DELETE SET NULL,
    recipe_name_snapshot VARCHAR(255) NOT NULL,
    version_number_snapshot INTEGER,
    version_name_snapshot VARCHAR(255),
    overhead_percent NUMERIC(18,4) NOT NULL DEFAULT 20,
    mixing_cost_per_ton NUMERIC(18,2) NOT NULL DEFAULT 0,
    packaging_type_id UUID REFERENCES packaging_types(id) ON DELETE SET NULL,
    packaging_name_snapshot VARCHAR(255),
    packaging_capacity_value_snapshot NUMERIC(18,3),
    packaging_capacity_unit_snapshot VARCHAR(50),
    packaging_cost_per_ton_snapshot NUMERIC(18,2) NOT NULL DEFAULT 0,
    package_price_snapshot NUMERIC(18,2) NOT NULL DEFAULT 0,
    
    transport_scheme_id UUID REFERENCES transport_schemes(id) ON DELETE SET NULL,
    transport_scheme_name_snapshot VARCHAR(255),
    transport_rate_snapshot NUMERIC(18,2) NOT NULL DEFAULT 0,
    transport_rate_price_per_snapshot VARCHAR(50),
    transport_capacity_tons_snapshot NUMERIC(18,3),
    transport_units_count NUMERIC(18,6) NOT NULL DEFAULT 0,
    transport_cost_per_ton NUMERIC(18,2) NOT NULL DEFAULT 0,
    transport_cost_total NUMERIC(18,2) NOT NULL DEFAULT 0,


    finance_days INTEGER NOT NULL DEFAULT 0,
    finance_rate NUMERIC(18,4) NOT NULL DEFAULT 0,
    finance_cost NUMERIC(18,2) NOT NULL DEFAULT 0,     


    direct_cost NUMERIC(18,2) NOT NULL DEFAULT 0,
    mixing_cost_total NUMERIC(18,2) NOT NULL DEFAULT 0,
    packaging_work_cost_total NUMERIC(18,2) NOT NULL DEFAULT 0,
    packaging_material_cost_total NUMERIC(18,2) NOT NULL DEFAULT 0,
    overhead_cost NUMERIC(18,2) NOT NULL DEFAULT 0,
 

    total_cost NUMERIC(18,2) NOT NULL DEFAULT 0,
    total_final_quantity NUMERIC(18,6) NOT NULL DEFAULT 0,
    package_count NUMERIC(18,6) NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE saved_calculations
ADD COLUMN IF NOT EXISTS transport_scheme_id UUID REFERENCES transport_schemes(id) ON DELETE SET NULL;

ALTER TABLE saved_calculations
ADD COLUMN IF NOT EXISTS transport_scheme_name_snapshot VARCHAR(255);

ALTER TABLE saved_calculations
ADD COLUMN IF NOT EXISTS transport_rate_snapshot NUMERIC(18,2) NOT NULL DEFAULT 0;

ALTER TABLE saved_calculations
ADD COLUMN IF NOT EXISTS transport_rate_price_per_snapshot VARCHAR(50);

ALTER TABLE saved_calculations
ADD COLUMN IF NOT EXISTS transport_capacity_tons_snapshot NUMERIC(18,3);

ALTER TABLE saved_calculations
ADD COLUMN IF NOT EXISTS transport_units_count NUMERIC(18,6) NOT NULL DEFAULT 0;

ALTER TABLE saved_calculations
ADD COLUMN IF NOT EXISTS transport_cost_per_ton NUMERIC(18,2) NOT NULL DEFAULT 0;

ALTER TABLE saved_calculations
ADD COLUMN IF NOT EXISTS transport_cost_total NUMERIC(18,2) NOT NULL DEFAULT 0;

ALTER TABLE saved_calculations
ADD COLUMN IF NOT EXISTS customer_id UUID REFERENCES customers(id) ON DELETE SET NULL;

ALTER TABLE saved_calculations
ADD COLUMN IF NOT EXISTS customer_name_snapshot VARCHAR(255);

ALTER TABLE saved_calculations
ADD COLUMN IF NOT EXISTS finance_days INTEGER NOT NULL DEFAULT 0;

ALTER TABLE saved_calculations
ADD COLUMN IF NOT EXISTS finance_rate NUMERIC(18,4) NOT NULL DEFAULT 0;

ALTER TABLE saved_calculations
ADD COLUMN IF NOT EXISTS finance_cost NUMERIC(18,2) NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS saved_calculation_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    saved_calculation_id UUID NOT NULL REFERENCES saved_calculations(id) ON DELETE CASCADE,
    material_name_snapshot VARCHAR(255) NOT NULL,
    base_quantity NUMERIC(18,6) NOT NULL,
    total_loss NUMERIC(18,6) NOT NULL DEFAULT 1,
    final_quantity NUMERIC(18,6) NOT NULL DEFAULT 0,
    material_price_snapshot NUMERIC(18,2) NOT NULL DEFAULT 0,
    material_cost NUMERIC(18,2) NOT NULL DEFAULT 0,
    total_process_cost NUMERIC(18,2) NOT NULL DEFAULT 0,
    process_cost NUMERIC(18,2) NOT NULL DEFAULT 0,
    total_cost NUMERIC(18,2) NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_saved_calculations_created_at
    ON saved_calculations(created_at);

CREATE INDEX IF NOT EXISTS idx_saved_calculation_items_calc_id
    ON saved_calculation_items(saved_calculation_id);

CREATE TABLE IF NOT EXISTS operations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(100),
    operation_group VARCHAR(50) NOT NULL DEFAULT 'process',
    unit VARCHAR(50) NOT NULL DEFAULT 'ton',
    default_loss_coefficient NUMERIC(18,6) NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE operations
ADD COLUMN IF NOT EXISTS default_loss_coefficient NUMERIC(18,6) NOT NULL DEFAULT 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_operations_code
    ON operations(code)
    WHERE code IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_operations_name
    ON operations(name);

CREATE INDEX IF NOT EXISTS idx_operations_group
    ON operations(operation_group);

CREATE TABLE IF NOT EXISTS operation_cost_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operation_id UUID NOT NULL REFERENCES operations(id) ON DELETE CASCADE,
    cost NUMERIC(18,2) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'RUB',
    valid_from DATE NOT NULL,
    valid_to DATE,
    comment TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_operation_cost_history_operation_id
    ON operation_cost_history(operation_id);

CREATE INDEX IF NOT EXISTS idx_operation_cost_history_valid_from
    ON operation_cost_history(valid_from);

CREATE TABLE IF NOT EXISTS recipe_version_operations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipe_version_id UUID NOT NULL REFERENCES recipe_versions(id) ON DELETE CASCADE,
    operation_id UUID NOT NULL REFERENCES operations(id) ON DELETE RESTRICT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    comment TEXT
);

CREATE INDEX IF NOT EXISTS idx_recipe_version_operations_recipe_version_id
    ON recipe_version_operations(recipe_version_id);

CREATE INDEX IF NOT EXISTS idx_recipe_version_operations_operation_id
    ON recipe_version_operations(operation_id);

DROP TRIGGER IF EXISTS trg_operations_updated_at ON operations;
CREATE TRIGGER trg_operations_updated_at
BEFORE UPDATE ON operations
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

ALTER TABLE processes
ADD COLUMN IF NOT EXISTS operation_id UUID
REFERENCES operations(id);

CREATE INDEX IF NOT EXISTS idx_processes_operation_id
ON processes(operation_id);