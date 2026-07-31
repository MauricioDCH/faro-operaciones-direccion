---
name: faro-scope-guardian
description: Protect Faro's R4 MVP scope. Use when proposing, reviewing, prioritizing, or expanding a feature, integration, workflow, or architectural change.
metadata:
  version: "0.1.0"
  project: faro
---

# Faro Scope Guardian

## Objective

Prevent the MVP from becoming an ERP, CRM, accounting platform, electronic invoicing
system, bank integration, payment automation tool, or autonomous decision-maker.

## Inputs

- proposed capability or change;
- current requirement or acceptance criterion;
- approved MVP scope;
- estimated dependencies and effort.

## Workflow

1. Read `README.md`, `docs/product/requirements.md`, and `docs/product/mvp-scope.md`.
2. Check direct alignment with R4 operational consolidation, indicators, alerts, or decision support.
3. Identify new dependencies, data contracts, risks, and Demo Day value.
4. Classify the proposal as `MUST`, `SHOULD`, `COULD`, or `OUT`.
5. Recommend include, reduce, defer, or reject.
6. Require an ADR when the accepted change alters architecture or scope.

## Output

- Capability
- Classification
- Problem solved
- Alignment evidence
- Effort and dependencies
- Material risk
- Recommended decision

Do not implement the capability while running this review.
