#!/usr/bin/env python3
"""
CLI database helper for DanielJamesAudio.
Used by Claude Code to query and update the database directly from chat.

Usage:
    python cli/db_helper.py add-equipment --make "Yamaha" --model "MG16" ...
    python cli/db_helper.py list-equipment [--status available] [--category "PA Systems"]
    python cli/db_helper.py get-equipment <id>
    python cli/db_helper.py update-equipment <id> --field value ...
    python cli/db_helper.py search <query>
    python cli/db_helper.py stats
    python cli/db_helper.py valuation
    python cli/db_helper.py add-defect <equipment_id> --description "..."
    python cli/db_helper.py list-defects [--status open]
"""

import argparse
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.database import get_standalone_db


def get_db():
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'danieljamesaudio.db')
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}. Run the Flask app first to initialise it.")
        sys.exit(1)
    return get_standalone_db(db_path)


def dict_from_row(row):
    return {k: row[k] for k in row.keys()} if row else None


def add_equipment(args):
    db = get_db()
    # Resolve category ID from name if provided
    category_id = None
    if args.category:
        row = db.execute('SELECT id FROM categories WHERE name LIKE ?', (f'%{args.category}%',)).fetchone()
        if row:
            category_id = row['id']
        else:
            print(f"Warning: Category '{args.category}' not found. Available categories:")
            for cat in db.execute('SELECT name FROM categories ORDER BY name').fetchall():
                print(f"  - {cat['name']}")

    cursor = db.execute(
        '''INSERT INTO equipment (make, model, serial_number, category_id, subcategory,
           purchase_date, purchase_price, current_value, condition, status, location,
           day_rate, week_rate, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (args.make, args.model, args.serial_number, category_id, args.subcategory,
         args.purchase_date, args.purchase_price, args.current_value,
         args.condition or 'good', args.status or 'available',
         args.location or 'warehouse', args.day_rate, args.week_rate, args.notes)
    )
    db.commit()
    equipment_id = cursor.lastrowid
    print(f"Added equipment #{equipment_id}: {args.make} {args.model}")
    return equipment_id


def list_equipment(args):
    db = get_db()
    query = '''SELECT e.*, c.name as category_name FROM equipment e
               LEFT JOIN categories c ON e.category_id = c.id WHERE 1=1'''
    params = []

    if args.status:
        query += ' AND e.status = ?'
        params.append(args.status)
    if args.category:
        query += ' AND c.name LIKE ?'
        params.append(f'%{args.category}%')

    query += ' ORDER BY e.make, e.model'
    rows = db.execute(query, params).fetchall()

    if args.json:
        print(json.dumps([dict_from_row(r) for r in rows], indent=2, default=str))
    else:
        if not rows:
            print("No equipment found.")
            return
        print(f"{'ID':>4} | {'Make':<15} | {'Model':<20} | {'Status':<12} | {'Condition':<12} | {'Value':>10}")
        print("-" * 85)
        for r in rows:
            value = f"£{r['current_value']:.2f}" if r['current_value'] else '-'
            print(f"{r['id']:>4} | {r['make']:<15} | {r['model']:<20} | {r['status']:<12} | {r['condition']:<12} | {value:>10}")
        print(f"\n{len(rows)} items")


def get_equipment(args):
    db = get_db()
    row = db.execute(
        '''SELECT e.*, c.name as category_name FROM equipment e
           LEFT JOIN categories c ON e.category_id = c.id WHERE e.id = ?''',
        (args.id,)
    ).fetchone()
    if not row:
        print(f"Equipment #{args.id} not found.")
        return
    if args.json:
        print(json.dumps(dict_from_row(row), indent=2, default=str))
    else:
        d = dict_from_row(row)
        for k, v in d.items():
            if v is not None:
                print(f"  {k}: {v}")


def update_equipment(args):
    db = get_db()
    updates = {}
    for field in ['make', 'model', 'serial_number', 'subcategory', 'purchase_date',
                  'purchase_price', 'current_value', 'condition', 'status', 'location',
                  'day_rate', 'week_rate', 'notes']:
        val = getattr(args, field, None)
        if val is not None:
            updates[field] = val

    if args.category:
        row = db.execute('SELECT id FROM categories WHERE name LIKE ?', (f'%{args.category}%',)).fetchone()
        if row:
            updates['category_id'] = row['id']

    if not updates:
        print("No fields to update.")
        return

    set_clause = ', '.join(f'{k} = ?' for k in updates)
    values = list(updates.values()) + [args.id]
    db.execute(f'UPDATE equipment SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', values)
    db.commit()
    print(f"Equipment #{args.id} updated: {', '.join(updates.keys())}")


def search_equipment(args):
    db = get_db()
    term = f'%{args.query}%'
    rows = db.execute(
        '''SELECT e.*, c.name as category_name FROM equipment e
           LEFT JOIN categories c ON e.category_id = c.id
           WHERE e.make LIKE ? OR e.model LIKE ? OR e.serial_number LIKE ? OR e.notes LIKE ?
           ORDER BY e.make, e.model''',
        (term, term, term, term)
    ).fetchall()

    if not rows:
        print(f"No results for '{args.query}'.")
        return
    for r in rows:
        value = f"£{r['current_value']:.2f}" if r['current_value'] else '-'
        print(f"  #{r['id']} {r['make']} {r['model']} [{r['status']}] {value}")
    print(f"\n{len(rows)} results")


def stats(args):
    db = get_db()
    rows = db.execute(
        'SELECT status, COUNT(*) as count, COALESCE(SUM(current_value), 0) as value FROM equipment GROUP BY status'
    ).fetchall()
    total = db.execute('SELECT COUNT(*) as count, COALESCE(SUM(current_value), 0) as value FROM equipment').fetchone()

    print("Equipment Statistics")
    print("=" * 40)
    for r in rows:
        print(f"  {r['status']:<15} {r['count']:>4} items  £{r['value']:>10.2f}")
    print("-" * 40)
    print(f"  {'TOTAL':<15} {total['count']:>4} items  £{total['value']:>10.2f}")


def valuation(args):
    db = get_db()
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

    print("INSURANCE VALUATION REPORT")
    print("Daniel James Audio")
    print("=" * 60)
    print(f"{'Category':<25} {'Items':>6} {'Purchase':>12} {'Value':>12}")
    print("-" * 60)
    for r in rows:
        cat = r['category_name'] or 'Uncategorised'
        print(f"{cat:<25} {r['item_count']:>6} £{r['purchase_total']:>10.2f} £{r['total_value']:>10.2f}")
    print("-" * 60)
    print(f"{'TOTAL':<25} {total_items:>6} £{sum(r['purchase_total'] for r in rows):>10.2f} £{total_value:>10.2f}")
    print("=" * 60)
    print("Excludes retired equipment.")


def add_defect(args):
    db = get_db()
    # Verify equipment exists
    equip = db.execute('SELECT make, model FROM equipment WHERE id = ?', (args.equipment_id,)).fetchone()
    if not equip:
        print(f"Equipment #{args.equipment_id} not found.")
        return

    cursor = db.execute(
        'INSERT INTO defects (equipment_id, description, severity) VALUES (?, ?, ?)',
        (args.equipment_id, args.description, args.severity or 'medium')
    )
    db.commit()
    # Update equipment status to in_repair
    db.execute("UPDATE equipment SET status = 'in_repair', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
               (args.equipment_id,))
    db.commit()
    print(f"Defect #{cursor.lastrowid} logged for {equip['make']} {equip['model']}: {args.description}")
    print(f"Equipment status changed to 'in_repair'.")


def list_defects(args):
    db = get_db()
    query = '''SELECT d.*, e.make, e.model FROM defects d
               JOIN equipment e ON d.equipment_id = e.id WHERE 1=1'''
    params = []
    if args.status:
        query += ' AND d.status = ?'
        params.append(args.status)
    query += ' ORDER BY d.reported_date DESC'

    rows = db.execute(query, params).fetchall()
    if not rows:
        print("No defects found.")
        return
    for r in rows:
        print(f"  #{r['id']} [{r['severity']}] {r['make']} {r['model']}: {r['description']} ({r['status']})")
    print(f"\n{len(rows)} defects")


def main():
    parser = argparse.ArgumentParser(description='DanielJamesAudio CLI Database Helper')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # add-equipment
    add_p = subparsers.add_parser('add-equipment', help='Add new equipment')
    add_p.add_argument('--make', required=True)
    add_p.add_argument('--model', required=True)
    add_p.add_argument('--serial-number', dest='serial_number')
    add_p.add_argument('--category')
    add_p.add_argument('--subcategory')
    add_p.add_argument('--purchase-date', dest='purchase_date')
    add_p.add_argument('--purchase-price', dest='purchase_price', type=float)
    add_p.add_argument('--current-value', dest='current_value', type=float)
    add_p.add_argument('--condition', choices=['excellent', 'good', 'fair', 'poor', 'non-functional'])
    add_p.add_argument('--status', choices=['available', 'on_hire', 'in_repair', 'retired'])
    add_p.add_argument('--location')
    add_p.add_argument('--day-rate', dest='day_rate', type=float)
    add_p.add_argument('--week-rate', dest='week_rate', type=float)
    add_p.add_argument('--notes')
    add_p.set_defaults(func=add_equipment)

    # list-equipment
    list_p = subparsers.add_parser('list-equipment', help='List equipment')
    list_p.add_argument('--status')
    list_p.add_argument('--category')
    list_p.add_argument('--json', action='store_true')
    list_p.set_defaults(func=list_equipment)

    # get-equipment
    get_p = subparsers.add_parser('get-equipment', help='Get equipment details')
    get_p.add_argument('id', type=int)
    get_p.add_argument('--json', action='store_true')
    get_p.set_defaults(func=get_equipment)

    # update-equipment
    upd_p = subparsers.add_parser('update-equipment', help='Update equipment')
    upd_p.add_argument('id', type=int)
    upd_p.add_argument('--make')
    upd_p.add_argument('--model')
    upd_p.add_argument('--serial-number', dest='serial_number')
    upd_p.add_argument('--category')
    upd_p.add_argument('--subcategory')
    upd_p.add_argument('--purchase-date', dest='purchase_date')
    upd_p.add_argument('--purchase-price', dest='purchase_price', type=float)
    upd_p.add_argument('--current-value', dest='current_value', type=float)
    upd_p.add_argument('--condition')
    upd_p.add_argument('--status')
    upd_p.add_argument('--location')
    upd_p.add_argument('--day-rate', dest='day_rate', type=float)
    upd_p.add_argument('--week-rate', dest='week_rate', type=float)
    upd_p.add_argument('--notes')
    upd_p.set_defaults(func=update_equipment)

    # search
    search_p = subparsers.add_parser('search', help='Search equipment')
    search_p.add_argument('query')
    search_p.set_defaults(func=search_equipment)

    # stats
    stats_p = subparsers.add_parser('stats', help='Equipment statistics')
    stats_p.set_defaults(func=stats)

    # valuation
    val_p = subparsers.add_parser('valuation', help='Insurance valuation report')
    val_p.set_defaults(func=valuation)

    # add-defect
    def_p = subparsers.add_parser('add-defect', help='Log a defect')
    def_p.add_argument('equipment_id', type=int)
    def_p.add_argument('--description', required=True)
    def_p.add_argument('--severity', choices=['low', 'medium', 'high', 'critical'])
    def_p.set_defaults(func=add_defect)

    # list-defects
    ldef_p = subparsers.add_parser('list-defects', help='List defects')
    ldef_p.add_argument('--status', choices=['open', 'in_repair', 'resolved'])
    ldef_p.set_defaults(func=list_defects)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == '__main__':
    main()
