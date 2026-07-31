---
name: faro-demo-reviewer
description: Review Faro's Demo Day workflow for business clarity, implemented evidence, reproducibility, timing, and fallback readiness. Use before rehearsals, releases, or presentations.
metadata:
  version: "0.1.0"
  project: faro
---

# Faro Demo Reviewer

## Objective

Verify that the demonstration communicates measurable business value and does not rely
on unsupported or unverifiable claims.

## Workflow

1. Read the current scope, requirements, validation plan, and demo script.
2. Confirm the problem and target user are clear within two minutes.
3. Verify that inputs, processing, outputs, and provenance are visible.
4. Check each demonstrated calculation against deterministic evidence.
5. Label every capability as implemented, simulated, planned, or out of scope.
6. Time the complete script and identify removable steps.
7. Verify a local fallback for external integrations or AI-provider failure.
8. List blocking findings before cosmetic recommendations.

## Review questions

- Is the problem immediately understandable?
- Does every alert expose evidence?
- Are calculations reproducible?
- Does AI add value beyond deterministic processing?
- Are simulated and implemented functions clearly separated?
- Is the demo within the available time?
- Can the core story continue if an integration fails?
