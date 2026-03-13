---
tags:
  - business
  - pricing
last_updated:
---

# Hire Pricing

> Auto-generated from equipment database. Run vault sync to update.

## Individual Equipment Rates

```dataview
TABLE make, model, day_rate as "Day Rate", week_rate as "Week Rate", category
FROM "Equipment"
WHERE day_rate > 0
SORT category, make, model
```

## Packages

*Packages will be listed here once created.*

## Pricing Notes
- Day rate = single calendar day
- Week rate = 7 calendar days (typically 3-4x day rate)
- Deposit may be required for high-value items
- Delivery available (charges apply based on distance)
