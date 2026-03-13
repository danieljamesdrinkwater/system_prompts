---
make:
model:
serial_number:
category:
subcategory:
status: available
condition: good
purchase_date:
purchase_price:
current_value:
day_rate:
week_rate:
location: warehouse
tags:
  - equipment
  - available
db_id:
---

# {{make}} {{model}}

## Details
- **Serial Number**: {{serial_number}}
- **Category**: {{category}} > {{subcategory}}
- **Location**: {{location}}

## Financials
| | |
|---|---|
| Purchase Price | £{{purchase_price}} |
| Current Value | £{{current_value}} |
| Day Rate | £{{day_rate}} |
| Week Rate | £{{week_rate}} |

## Manuals
-

## Notes

## Defect History
```dataview
TABLE severity, status, reported_date
FROM "Repairs"
WHERE contains(equipment, this.file.name)
SORT reported_date DESC
```
