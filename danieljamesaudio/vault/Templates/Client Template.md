---
client_name:
email:
phone:
address:
tags:
  - client
---

# {{client_name}}

## Contact
- **Email**: {{email}}
- **Phone**: {{phone}}
- **Address**: {{address}}

## Booking History
```dataview
TABLE start_date, end_date, status, total_price
FROM "Clients"
WHERE contains(client, this.file.name)
SORT start_date DESC
```

## Notes
