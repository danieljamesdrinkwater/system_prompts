---
tags:
  - parts
  - shopping
last_updated:
---

# Parts Shopping List

## Urgently Needed

## Low Stock

```dataview
TABLE quantity_in_stock as "In Stock", reorder_level as "Reorder At", unit_cost as "Unit Cost", supplier
FROM "Parts"
WHERE quantity_in_stock <= reorder_level
SORT name
```

## Regular Stock

## Notes
