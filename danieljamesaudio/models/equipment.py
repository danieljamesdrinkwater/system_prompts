from .database import query_db, execute_db, get_db


def get_all_equipment(status=None, category_id=None, search=None):
    """Get all equipment with optional filters."""
    query = '''
        SELECT e.*, c.name as category_name,
               (SELECT file_path FROM equipment_photos WHERE equipment_id = e.id AND is_primary = 1 LIMIT 1) as primary_photo
        FROM equipment e
        LEFT JOIN categories c ON e.category_id = c.id
        WHERE 1=1
    '''
    args = []

    if status:
        query += ' AND e.status = ?'
        args.append(status)
    if category_id:
        query += ' AND e.category_id = ?'
        args.append(category_id)
    if search:
        query += ' AND (e.make LIKE ? OR e.model LIKE ? OR e.serial_number LIKE ?)'
        term = f'%{search}%'
        args.extend([term, term, term])

    query += ' ORDER BY e.make, e.model'
    return query_db(query, args)


def get_equipment_by_id(equipment_id):
    """Get a single equipment item with its category."""
    return query_db(
        '''SELECT e.*, c.name as category_name
           FROM equipment e
           LEFT JOIN categories c ON e.category_id = c.id
           WHERE e.id = ?''',
        (equipment_id,),
        one=True
    )


def get_equipment_photos(equipment_id):
    """Get all photos for an equipment item."""
    return query_db(
        'SELECT * FROM equipment_photos WHERE equipment_id = ? ORDER BY is_primary DESC, id',
        (equipment_id,)
    )


def create_equipment(make, model, serial_number=None, category_id=None,
                     subcategory=None, purchase_date=None, purchase_price=None,
                     current_value=None, condition='good', status='available',
                     location='warehouse', day_rate=None, week_rate=None, notes=None):
    """Insert a new equipment item."""
    return execute_db(
        '''INSERT INTO equipment
           (make, model, serial_number, category_id, subcategory, purchase_date,
            purchase_price, current_value, condition, status, location,
            day_rate, week_rate, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (make, model, serial_number, category_id, subcategory, purchase_date,
         purchase_price, current_value, condition, status, location,
         day_rate, week_rate, notes)
    )


def update_equipment(equipment_id, **kwargs):
    """Update an equipment item. Pass only the fields to update."""
    allowed_fields = {
        'make', 'model', 'serial_number', 'category_id', 'subcategory',
        'purchase_date', 'purchase_price', 'current_value', 'condition',
        'status', 'location', 'day_rate', 'week_rate', 'notes'
    }
    fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
    if not fields:
        return

    set_clause = ', '.join(f'{k} = ?' for k in fields)
    values = list(fields.values())
    values.append(equipment_id)

    execute_db(
        f'UPDATE equipment SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        values
    )


def delete_equipment(equipment_id):
    """Delete an equipment item."""
    execute_db('DELETE FROM equipment WHERE id = ?', (equipment_id,))


def add_equipment_photo(equipment_id, file_path, is_primary=False, caption=None):
    """Add a photo to an equipment item."""
    if is_primary:
        execute_db(
            'UPDATE equipment_photos SET is_primary = 0 WHERE equipment_id = ?',
            (equipment_id,)
        )
    return execute_db(
        'INSERT INTO equipment_photos (equipment_id, file_path, is_primary, caption) VALUES (?, ?, ?, ?)',
        (equipment_id, file_path, 1 if is_primary else 0, caption)
    )


def get_categories():
    """Get all equipment categories."""
    return query_db('SELECT * FROM categories ORDER BY name')


def get_equipment_stats():
    """Get equipment counts by status and total value."""
    stats = {}
    rows = query_db(
        'SELECT status, COUNT(*) as count, COALESCE(SUM(current_value), 0) as total_value FROM equipment GROUP BY status'
    )
    for row in rows:
        stats[row['status']] = {'count': row['count'], 'total_value': row['total_value']}

    total = query_db(
        'SELECT COUNT(*) as count, COALESCE(SUM(current_value), 0) as total_value FROM equipment',
        one=True
    )
    stats['total'] = {'count': total['count'], 'total_value': total['total_value']}

    return stats


def get_insurance_valuation():
    """Get insurance valuation report data grouped by category."""
    return query_db('''
        SELECT c.name as category_name,
               COUNT(e.id) as item_count,
               COALESCE(SUM(e.current_value), 0) as total_value,
               COALESCE(SUM(e.purchase_price), 0) as total_purchase_price
        FROM equipment e
        LEFT JOIN categories c ON e.category_id = c.id
        WHERE e.status != 'retired'
        GROUP BY c.name
        ORDER BY total_value DESC
    ''')
