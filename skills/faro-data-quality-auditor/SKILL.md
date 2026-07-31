---
name: faro-data-quality-auditor
description: Audit Faro data, validation rules, anomaly detection, provenance, and reproducibility. Use when reviewing datasets, quality findings, metrics, or regression risk.
metadata:
  version: "0.1.0"
  project: faro
---

# Faro Data Quality Auditor

## Objective

Evaluate whether input data and generated results are reliable, traceable, and
reproducible without silently correcting source records.

## Audit coverage

Schema, types, required fields, uniqueness, duplicates, missing values, dates, ranges,
referential integrity, transformations, provenance, false positives, false negatives,
and reproducibility.

## Workflow

1. Read applicable contracts, expected anomalies, rules, and tests.
2. Run the smallest relevant validation commands.
3. Compare detected findings with machine-readable ground truth.
4. Inspect provenance for representative records and every critical finding.
5. Separate implementation defects, contract gaps, and dataset defects.
6. Do not edit data or code unless the user explicitly requests remediation.

## Finding format

- ID
- Severity
- Component
- Description
- Reproducible evidence
- Impact
- Recommendation
- Status

Report actual precision/recall only when the denominator and executed evidence are
available. Never infer that unexecuted tests pass.
