---
name: faro-synthetic-data-designer
description: Design deterministic, related synthetic operational datasets and machine-readable anomaly ground truth for Faro. Use for data generation, fixtures, anomalies, or demo scenarios.
metadata:
  version: "0.1.0"
  project: faro
---

# Faro Synthetic Data Designer

## Objective

Produce realistic, internally consistent, fully synthetic, and reproducible datasets for
the selected commercial/distribution scenario.

## Required domains

Products, customers, suppliers, sales, inventory, orders, invoices, messages, and
known anomalies.

## Workflow

1. Read the current data contracts and dictionary; stop if required contracts conflict.
2. Use the configured fixed seed.
3. Generate clean relational records before injecting anomalies.
4. Seed only approved anomalies with stable IDs.
5. Write raw sources without overwriting prior generated runs unless explicitly approved.
6. Generate `data/expected/expected_anomalies.json` with type, record, source, rule, and expected severity.
7. Validate referential integrity outside intentionally anomalous cases.
8. Add or update deterministic tests.

## Minimum anomaly catalog

Duplicates, missing values, inconsistent names, invalid dates, negative quantities,
unmatched products, order/invoice differences, low inventory, and abnormal sales decline.

## Output

Report seed, files created, record counts, anomaly counts, validation commands, and
remaining assumptions. Never use real company or personal data.
