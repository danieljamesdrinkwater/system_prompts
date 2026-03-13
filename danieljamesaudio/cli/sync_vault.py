#!/usr/bin/env python3
"""
Sync the SQLite database to the Obsidian vault.

Generates/updates equipment markdown files, insurance valuation,
and other vault documents from the database.

Usage:
    python cli/sync_vault.py [--db-path PATH] [--vault-path PATH]
"""

import os
import sys
import re
import argparse
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.database import get_standalone_db

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(BASE_DIR, 'danieljamesaudio.db')
DEFAULT_VAULT = os.path.join(BASE_DIR, 'vault')

CATEGORY_FOLDERS = {
    'PA Systems': 'PA Systems',
    'Backline': 'Backline',
    'Mixing & Recording': 'Mixing & Recording',
    'Cabling & Accessories': 'Cabling & Accessories',
}


def sanitise_filename(name):
    """Make a string safe for use as a filename."""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = name.strip('. ')
    return name


def generate_equipment_note(row):
    """Generate markdown content for an equipment item."""
    serial = row['serial_number'] or ''
    category = row['category_name'] or 'Uncategorised'
    subcategory = row['subcategory'] or ''

    # Status tag mapping
    status_tags = {
        'available': 'available',
        'on_hire': 'on-hire',
        'in_repair': 'needs-repair',
        'retired': 'retired',
    }
    status_tag = status_tags.get(row['status'], row['status'])

    return f"""---
make: "{row['make']}"
model: "{row['model']}"
serial_number: "{serial}"
category: "{category}"
subcategory: "{subcategory}"
status: {row['status']}
condition: {row['condition']}
purchase_date: {row['purchase_date'] or ''}
purchase_price: {row['purchase_price'] or 0}
current_value: {row['current_value'] or 0}
day_rate: {row['day_rate'] or 0}
week_rate: {row['week_rate'] or 0}
location: "{row['location'] or 'warehouse'}"
tags:
  - equipment
  - {status_tag}
db_id: {row['id']}
last_synced: {date.today().isoformat()}
---

# {row['make']} {row['model']}

## Details
- **Serial Number**: {serial or 'N/A'}
- **Category**: {category}{(' > ' + subcategory) if subcategory else ''}
- **Location**: {row['location'] or 'warehouse'}
- **Condition**: {row['condition'].title()}
- **Status**: {row['status'].replace('_', ' ').title()}

## Financials
| | |
|---|---|
| Purchase Date | {row['purchase_date'] or 'N/A'} |
| Purchase Price | £{row['purchase_price']:.2f if row['purchase_price'] else '0.00'} |
| Current Value | £{row['current_value']:.2f if row['current_value'] else '0.00'} |
| Day Rate | £{row['day_rate']:.2f if row['day_rate'] else '0.00'} |
| Week Rate | £{row['week_rate']:.2f if row['week_rate'] else '0.00'} |

## Manuals
{_get_manual_links(row)}

## Notes
{row['notes'] or ''}
"""


def _get_manual_links(row):
    """Placeholder for manual links - will be populated when manuals are added."""
    return '*No manuals linked yet.*'


def sync_equipment(db, vault_path):
    """Sync all equipment items to vault markdown files."""
    rows = db.execute('''
        SELECT e.*, c.name as category_name
        FROM equipment e
        LEFT JOIN categories c ON e.category_id = c.id
        ORDER BY c.name, e.make, e.model
    ''').fetchall()

    equipment_dir = os.path.join(vault_path, 'Equipment')
    synced = 0

    for row in rows:
        category_name = row['category_name'] or 'Uncategorised'
        folder_name = CATEGORY_FOLDERS.get(category_name, category_name)
        folder_path = os.path.join(equipment_dir, folder_name)
        os.makedirs(folder_path, exist_ok=True)

        # Filename: Make-Model-SNserial.md
        serial_suffix = f'-SN{row["serial_number"]}' if row['serial_number'] else ''
        filename = sanitise_filename(f'{row["make"]}-{row["model"]}{serial_suffix}.md')
        filepath = os.path.join(folder_path, filename)

        content = generate_equipment_note(row)

        # Check if file exists and has user-added content below the auto-generated section
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                existing = f.read()
            # Preserve any content the user added after "## Notes" section
            # by checking if there's custom content beyond what we generate
            if '<!-- USER NOTES BELOW -->' in existing:
                user_section = existing.split('<!-- USER NOTES BELOW -->')[1]
                content = content.rstrip() + '\n\n<!-- USER NOTES BELOW -->' + user_section

        with open(filepath, 'w') as f:
            f.write(content)
        synced += 1

    print(f"  Synced {synced} equipment notes")
    return synced


def sync_insurance_valuation(db, vault_path):
    """Update the insurance valuation report in the vault."""
    rows = db.execute('''
        SELECT c.name as category_name,
               COUNT(e.id) as item_count,
               COALESCE(SUM(e.current_value), 0) as total_value,
               COALESCE(SUM(e.purchase_price), 0) as purchase_total
        FROM equipment e
        LEFT JOIN categories c ON e.category_id = c.id
        WHERE e.status != 'retired'
        GROUP BY c.name
        ORDER BY total_value DESC
    ''').fetchall()

    total_value = sum(r['total_value'] for r in rows)
    total_items = sum(r['item_count'] for r in rows)

    # Build category table
    cat_rows = ''
    for r in rows:
        cat = r['category_name'] or 'Uncategorised'
        cat_rows += f'| {cat} | {r["item_count"]} | £{r["total_value"]:.2f} |\n'

    content = f"""---
tags:
  - business
  - insurance
last_updated: {date.today().isoformat()}
total_value: {total_value:.2f}
total_items: {total_items}
---

# Insurance Valuation Report

> Auto-generated from equipment database on {date.today().strftime('%d %B %Y')}.

## Summary
- **Total Items**: {total_items}
- **Total Insured Value**: £{total_value:,.2f}

## By Category

| Category | Items | Value |
|----------|-------|-------|
{cat_rows}
| **Total** | **{total_items}** | **£{total_value:,.2f}** |

## Equipment List

```dataview
TABLE make, model, current_value as "Value", condition, status
FROM "Equipment"
WHERE status != "retired"
SORT current_value DESC
```
"""

    filepath = os.path.join(vault_path, 'Business', 'Insurance Valuation.md')
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"  Updated insurance valuation: {total_items} items, £{total_value:,.2f}")


def sync_defects_to_repairs(db, vault_path):
    """Sync open defects/repairs to vault repair notes."""
    rows = db.execute('''
        SELECT d.*, e.make, e.model,
               r.diagnosis, r.repair_type, r.repair_steps, r.status as repair_status
        FROM defects d
        JOIN equipment e ON d.equipment_id = e.id
        LEFT JOIN repairs r ON r.defect_id = d.id
        WHERE d.status != 'resolved'
        ORDER BY d.reported_date DESC
    ''').fetchall()

    repairs_dir = os.path.join(vault_path, 'Repairs')
    os.makedirs(repairs_dir, exist_ok=True)
    synced = 0

    for r in rows:
        filename = sanitise_filename(
            f'{r["reported_date"]}-{r["make"]}-{r["model"]}-{r["description"][:40]}.md'
        )
        filepath = os.path.join(repairs_dir, filename)

        repair_status = r['repair_status'] or 'pending'
        status_tag = 'needs-repair' if repair_status != 'completed' else 'repaired'

        content = f"""---
equipment: "[[{r['make']}-{r['model']}]]"
fault: "{r['description']}"
severity: {r['severity']}
repair_type: {r['repair_type'] or 'tbd'}
status: {repair_status}
diagnosed_date: {r['reported_date']}
tags:
  - repair
  - {status_tag}
db_id: {r['id']}
---

# Repair: {r['make']} {r['model']} - {r['description']}

## Diagnosis
{r['diagnosis'] or '*Not yet diagnosed. Ask Claude for help with triage.*'}

## Status
**{repair_status.replace('_', ' ').title()}** | Severity: **{r['severity'].title()}**
"""

        if not os.path.exists(filepath):
            with open(filepath, 'w') as f:
                f.write(content)
            synced += 1

    print(f"  Synced {synced} new repair notes")


def main():
    parser = argparse.ArgumentParser(description='Sync DanielJamesAudio DB to Obsidian vault')
    parser.add_argument('--db-path', default=DEFAULT_DB, help='Path to SQLite database')
    parser.add_argument('--vault-path', default=DEFAULT_VAULT, help='Path to Obsidian vault')
    args = parser.parse_args()

    if not os.path.exists(args.db_path):
        print(f"Database not found: {args.db_path}")
        print("Run the Flask app first to initialise the database.")
        sys.exit(1)

    db = get_standalone_db(args.db_path)

    print(f"Syncing database to vault...")
    print(f"  DB: {args.db_path}")
    print(f"  Vault: {args.vault_path}")
    print()

    sync_equipment(db, args.vault_path)
    sync_insurance_valuation(db, args.vault_path)
    sync_defects_to_repairs(db, args.vault_path)

    db.close()
    print(f"\nVault sync complete.")


if __name__ == '__main__':
    main()
