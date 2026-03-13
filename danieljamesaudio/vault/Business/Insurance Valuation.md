---
tags:
  - business
  - insurance
last_updated:
total_value: 0
total_items: 0
---

# Insurance Valuation Report

> Auto-generated from equipment database. Run vault sync to update.

## Summary
- **Total Items**: 0
- **Total Insured Value**: £0.00

## By Category

| Category | Items | Value |
|----------|-------|-------|
| | | |

## Equipment List

```dataview
TABLE make, model, current_value as "Value", condition, status
FROM "Equipment"
WHERE status != "retired"
SORT current_value DESC
```
