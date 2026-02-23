CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.dim_vehicles` (
    vin STRING NOT NULL,
    make STRING,
    model STRING,
    year INT64,
    trim STRING,
    current_status STRING,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.fact_sales` (
    transaction_id STRING NOT NULL,
    vin STRING NOT NULL,
    customer_id STRING,
    sale_price FLOAT64,
    sale_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS `autohaus-infrastructure.autohaus_cil.fact_service` (
    service_id STRING NOT NULL,
    vin STRING NOT NULL,
    mechanic_id STRING,
    service_date DATE,
    drive_file_id STRING,
    notes STRING,
    cost FLOAT64,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE VIEW `autohaus-infrastructure.autohaus_cil.vw_vehicle_digital_twin` AS
SELECT 
    v.vin,
    v.make,
    v.model,
    v.year,
    v.trim,
    v.current_status,
    COALESCE(s.sale_price, 0.0) as last_sale_price,
    s.sale_date as last_sale_date,
    s.customer_id as current_owner_id,
    sv.last_service_date,
    sv.total_service_cost,
    sv.service_count
FROM `autohaus-infrastructure.autohaus_cil.dim_vehicles` v
LEFT JOIN `autohaus-infrastructure.autohaus_cil.fact_sales` s ON v.vin = s.vin
LEFT JOIN (
    SELECT vin, MAX(service_date) as last_service_date, SUM(cost) as total_service_cost, COUNT(service_id) as service_count 
    FROM `autohaus-infrastructure.autohaus_cil.fact_service` 
    GROUP BY vin
) sv ON v.vin = sv.vin;
