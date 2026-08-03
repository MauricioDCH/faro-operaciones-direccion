"""SQLite schema for Faro's local operational store."""

SCHEMA_VERSION = "1.0.0"

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
