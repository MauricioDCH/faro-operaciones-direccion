"""SQLite schema for Faro's local operational store."""

SCHEMA_VERSION = "1.1.0"

DDL = r"""
PRAGMA foreign_keys = ON;

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE source_file (
    source_file_id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    contract_id TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    seed INTEGER,
    file_hash TEXT NOT NULL UNIQUE,
    ingested_at TEXT NOT NULL,
    record_status TEXT NOT NULL,
    media_type_declared TEXT,
    media_type_detected TEXT,
    detected_format TEXT,
    format_version TEXT,
    ingestion_adapter TEXT,
    file_size_bytes INTEGER,
    format_metadata_json TEXT NOT NULL
);

CREATE TABLE source_location (
    source_location_id TEXT PRIMARY KEY,
    source_file_id TEXT NOT NULL REFERENCES source_file(source_file_id),
    locator_type TEXT NOT NULL,
    sheet TEXT,
    row_number INTEGER,
    column_name TEXT,
    cell_reference TEXT,
    page_number INTEGER,
    record_number INTEGER,
    line_number INTEGER,
    json_pointer TEXT,
    xml_xpath TEXT,
    text_excerpt TEXT,
    raw_value TEXT,
    evidence_json TEXT NOT NULL
);

CREATE TABLE record_observation (
    observation_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    record_id TEXT NOT NULL,
    source_file_id TEXT NOT NULL REFERENCES source_file(source_file_id),
    source_location_id TEXT REFERENCES source_location(source_location_id),
    source_format TEXT NOT NULL,
    source_priority INTEGER NOT NULL,
    record_status TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX idx_observation_entity ON record_observation(entity_type, record_id);

CREATE TABLE product (
    product_id TEXT PRIMARY KEY,
    sku TEXT NOT NULL,
    product_name TEXT NOT NULL,
    product_name_raw TEXT,
    category TEXT NOT NULL,
    unit TEXT NOT NULL,
    unit_cost_cop TEXT NOT NULL,
    sale_price_cop TEXT NOT NULL,
    active INTEGER NOT NULL,
    record_status TEXT NOT NULL,
    source_file_id TEXT NOT NULL REFERENCES source_file(source_file_id),
    source_location_id TEXT REFERENCES source_location(source_location_id)
);

CREATE TABLE customer (
    customer_id TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    customer_type TEXT NOT NULL,
    tax_id TEXT,
    city TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    active INTEGER NOT NULL,
    record_status TEXT NOT NULL,
    source_file_id TEXT NOT NULL REFERENCES source_file(source_file_id),
    source_location_id TEXT REFERENCES source_location(source_location_id)
);

CREATE TABLE supplier (
    supplier_id TEXT PRIMARY KEY,
    supplier_name TEXT NOT NULL,
    supplier_name_raw TEXT,
    tax_id TEXT,
    city TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    active INTEGER NOT NULL,
    record_status TEXT NOT NULL,
    source_file_id TEXT NOT NULL REFERENCES source_file(source_file_id),
    source_location_id TEXT REFERENCES source_location(source_location_id)
);

CREATE TABLE sale_line (
    sale_line_id TEXT PRIMARY KEY,
    sale_id TEXT NOT NULL,
    sale_date TEXT NOT NULL,
    customer_id TEXT NOT NULL REFERENCES customer(customer_id),
    product_id TEXT NOT NULL REFERENCES product(product_id),
    quantity TEXT NOT NULL,
    unit_price_cop TEXT NOT NULL,
    discount_cop TEXT NOT NULL,
    line_total_cop TEXT NOT NULL,
    channel TEXT NOT NULL,
    record_status TEXT NOT NULL,
    source_file_id TEXT NOT NULL REFERENCES source_file(source_file_id),
    source_location_id TEXT REFERENCES source_location(source_location_id)
);

CREATE TABLE inventory_snapshot (
    snapshot_date TEXT NOT NULL,
    product_id TEXT NOT NULL REFERENCES product(product_id),
    stock_on_hand TEXT NOT NULL,
    committed_quantity TEXT NOT NULL,
    available_quantity TEXT NOT NULL,
    reorder_point TEXT NOT NULL,
    record_status TEXT NOT NULL,
    source_file_id TEXT NOT NULL REFERENCES source_file(source_file_id),
    source_location_id TEXT REFERENCES source_location(source_location_id),
    PRIMARY KEY(snapshot_date, product_id)
);

CREATE TABLE purchase_order_line (
    order_line_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    order_date TEXT NOT NULL,
    supplier_id TEXT NOT NULL REFERENCES supplier(supplier_id),
    product_id TEXT NOT NULL REFERENCES product(product_id),
    ordered_quantity TEXT NOT NULL,
    expected_unit_cost_cop TEXT NOT NULL,
    expected_delivery_date TEXT,
    status TEXT NOT NULL,
    source_message_id TEXT,
    notes TEXT,
    record_status TEXT NOT NULL,
    source_file_id TEXT NOT NULL REFERENCES source_file(source_file_id),
    source_location_id TEXT REFERENCES source_location(source_location_id)
);

CREATE TABLE document (
    document_id TEXT PRIMARY KEY,
    source_file_id TEXT NOT NULL REFERENCES source_file(source_file_id),
    document_type TEXT NOT NULL,
    page_count INTEGER NOT NULL,
    classification_method TEXT NOT NULL,
    classification_confidence REAL,
    processing_status TEXT NOT NULL,
    record_status TEXT NOT NULL,
    ubl_version TEXT,
    root_document_type TEXT,
    source_location_id TEXT REFERENCES source_location(source_location_id)
);

CREATE TABLE document_page (
    document_page_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES document(document_id),
    page_number INTEGER NOT NULL,
    extraction_method TEXT NOT NULL,
    native_text_length INTEGER NOT NULL,
    render_dpi INTEGER,
    ocr_engine TEXT,
    ocr_engine_version TEXT,
    ocr_language TEXT,
    ocr_confidence REAL,
    page_text TEXT NOT NULL,
    processing_status TEXT NOT NULL,
    error_code TEXT,
    error_message TEXT,
    record_status TEXT NOT NULL,
    source_file_id TEXT NOT NULL REFERENCES source_file(source_file_id),
    source_location_id TEXT REFERENCES source_location(source_location_id)
);

CREATE TABLE invoice (
    invoice_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES document(document_id),
    invoice_number TEXT,
    supplier_name_raw TEXT,
    supplier_id TEXT,
    issue_date TEXT,
    related_order_id TEXT,
    currency TEXT,
    subtotal_cop TEXT,
    tax_cop TEXT,
    total_cop TEXT,
    record_status TEXT NOT NULL,
    source_file_id TEXT NOT NULL REFERENCES source_file(source_file_id),
    source_location_id TEXT REFERENCES source_location(source_location_id)
);

CREATE TABLE invoice_line (
    invoice_line_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES invoice(invoice_id),
    product_name_raw TEXT NOT NULL,
    product_id TEXT,
    quantity TEXT NOT NULL,
    unit_price_cop TEXT NOT NULL,
    line_total_cop TEXT NOT NULL,
    record_status TEXT NOT NULL,
    source_file_id TEXT NOT NULL REFERENCES source_file(source_file_id),
    source_location_id TEXT REFERENCES source_location(source_location_id)
);

CREATE TABLE quotation (
    quotation_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES document(document_id),
    quotation_number TEXT,
    supplier_name_raw TEXT,
    supplier_id TEXT,
    issue_date TEXT,
    valid_until TEXT,
    currency TEXT,
    subtotal_cop TEXT,
    tax_cop TEXT,
    total_cop TEXT,
    record_status TEXT NOT NULL,
    source_file_id TEXT NOT NULL REFERENCES source_file(source_file_id),
    source_location_id TEXT REFERENCES source_location(source_location_id)
);

CREATE TABLE quotation_line (
    quotation_line_id TEXT PRIMARY KEY,
    quotation_id TEXT NOT NULL REFERENCES quotation(quotation_id),
    product_name_raw TEXT NOT NULL,
    product_id TEXT,
    quantity TEXT NOT NULL,
    unit_price_cop TEXT NOT NULL,
    line_total_cop TEXT NOT NULL,
    record_status TEXT NOT NULL,
    source_file_id TEXT NOT NULL REFERENCES source_file(source_file_id),
    source_location_id TEXT REFERENCES source_location(source_location_id)
);

CREATE TABLE extraction_result (
    extraction_id TEXT PRIMARY KEY,
    source_location_id TEXT REFERENCES source_location(source_location_id),
    document_page_id TEXT,
    target_entity TEXT NOT NULL,
    target_field TEXT NOT NULL,
    raw_value TEXT,
    proposed_value TEXT,
    method TEXT NOT NULL,
    page_number INTEGER,
    text_excerpt TEXT,
    confidence REAL,
    review_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    ocr_engine TEXT,
    ocr_engine_version TEXT,
    ocr_confidence REAL
);

CREATE TABLE quality_finding (
    finding_id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    code TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    source_location_id TEXT REFERENCES source_location(source_location_id),
    entity_type TEXT,
    record_id TEXT,
    field TEXT,
    observed_value TEXT,
    expected_value TEXT
);

CREATE TABLE transformation_event (
    transformation_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    record_id TEXT NOT NULL,
    source_location_id TEXT REFERENCES source_location(source_location_id),
    rule_id TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    output_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);


CREATE TABLE indicator_run (
    run_id TEXT PRIMARY KEY,
    preset_id TEXT NOT NULL,
    preset_label TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    database_logical_hash TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    calculated_at TEXT NOT NULL,
    result_count INTEGER NOT NULL
);

CREATE TABLE indicator_result (
    indicator_result_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES indicator_run(run_id) ON DELETE CASCADE,
    preset_id TEXT NOT NULL,
    indicator_id TEXT NOT NULL,
    indicator_name TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT,
    dimension TEXT,
    dimension_value TEXT,
    numeric_value TEXT,
    unit TEXT NOT NULL,
    formula_version TEXT NOT NULL,
    source_record_ids_json TEXT NOT NULL,
    source_location_ids_json TEXT NOT NULL,
    details_json TEXT NOT NULL
);
CREATE INDEX idx_indicator_result_run ON indicator_result(run_id, indicator_id);

CREATE TABLE alert_run (
    run_id TEXT PRIMARY KEY,
    preset_id TEXT NOT NULL,
    preset_label TEXT NOT NULL,
    alert_config_hash TEXT NOT NULL,
    indicator_run_id TEXT NOT NULL REFERENCES indicator_run(run_id),
    indicator_preset_id TEXT NOT NULL,
    database_logical_hash TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    evaluation_count INTEGER NOT NULL,
    alert_count INTEGER NOT NULL
);

CREATE TABLE alert_evaluation (
    evaluation_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES alert_run(run_id) ON DELETE CASCADE,
    preset_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    aggregation TEXT NOT NULL,
    status TEXT NOT NULL,
    observed_value TEXT,
    operator TEXT NOT NULL,
    threshold_value TEXT NOT NULL,
    unit TEXT NOT NULL,
    severity TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT,
    dimension TEXT,
    dimension_value TEXT,
    indicator_result_ids_json TEXT NOT NULL,
    finding_ids_json TEXT NOT NULL,
    source_record_ids_json TEXT NOT NULL,
    source_location_ids_json TEXT NOT NULL,
    reason TEXT,
    details_json TEXT NOT NULL
);
CREATE INDEX idx_alert_evaluation_run ON alert_evaluation(run_id, status, severity);

CREATE TABLE alert (
    alert_id TEXT PRIMARY KEY,
    evaluation_id TEXT NOT NULL REFERENCES alert_evaluation(evaluation_id) ON DELETE CASCADE,
    run_id TEXT NOT NULL REFERENCES alert_run(run_id) ON DELETE CASCADE,
    preset_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    observed_value TEXT NOT NULL,
    operator TEXT NOT NULL,
    threshold_value TEXT NOT NULL,
    unit TEXT NOT NULL,
    indicator_result_ids_json TEXT NOT NULL,
    finding_ids_json TEXT NOT NULL,
    related_record_ids_json TEXT NOT NULL,
    source_location_ids_json TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    review_status TEXT NOT NULL,
    delivery_status TEXT NOT NULL,
    cooldown_minutes INTEGER NOT NULL
);
CREATE INDEX idx_alert_run ON alert(run_id, severity, review_status);

CREATE VIEW v_entity_counts AS
SELECT 'product' AS entity_type, COUNT(*) AS record_count FROM product
UNION ALL SELECT 'customer', COUNT(*) FROM customer
UNION ALL SELECT 'supplier', COUNT(*) FROM supplier
UNION ALL SELECT 'sale_line', COUNT(*) FROM sale_line
UNION ALL SELECT 'inventory_snapshot', COUNT(*) FROM inventory_snapshot
UNION ALL SELECT 'purchase_order_line', COUNT(*) FROM purchase_order_line
UNION ALL SELECT 'document', COUNT(*) FROM document
UNION ALL SELECT 'document_page', COUNT(*) FROM document_page
UNION ALL SELECT 'invoice', COUNT(*) FROM invoice
UNION ALL SELECT 'invoice_line', COUNT(*) FROM invoice_line
UNION ALL SELECT 'quotation', COUNT(*) FROM quotation
UNION ALL SELECT 'quotation_line', COUNT(*) FROM quotation_line;
"""
