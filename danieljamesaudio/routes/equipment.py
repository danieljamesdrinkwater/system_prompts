import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required
from werkzeug.utils import secure_filename

from models.equipment import (
    get_all_equipment, get_equipment_by_id, get_equipment_photos,
    create_equipment, update_equipment, delete_equipment,
    add_equipment_photo, get_categories, get_insurance_valuation
)

equipment_bp = Blueprint('equipment', __name__, url_prefix='/equipment')


def allowed_image(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_IMAGE_EXTENSIONS']


def save_photo(file):
    """Save an uploaded photo and return the relative path."""
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f'{uuid.uuid4().hex}.{ext}'
    filepath = os.path.join(current_app.config['PHOTO_FOLDER'], filename)
    file.save(filepath)
    return f'photos/{filename}'


@equipment_bp.route('/')
@login_required
def list():
    status = request.args.get('status')
    category_id = request.args.get('category_id', type=int)
    search = request.args.get('search', '').strip()

    items = get_all_equipment(status=status, category_id=category_id, search=search or None)
    categories = get_categories()

    return render_template('equipment/list.html',
                           items=items, categories=categories,
                           current_status=status, current_category=category_id,
                           search=search)


@equipment_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    categories = get_categories()

    if request.method == 'POST':
        make = request.form.get('make', '').strip()
        model = request.form.get('model', '').strip()

        if not make or not model:
            flash('Make and model are required.', 'danger')
            return render_template('equipment/add.html', categories=categories)

        equipment_id = create_equipment(
            make=make,
            model=model,
            serial_number=request.form.get('serial_number', '').strip() or None,
            category_id=request.form.get('category_id', type=int),
            subcategory=request.form.get('subcategory', '').strip() or None,
            purchase_date=request.form.get('purchase_date') or None,
            purchase_price=request.form.get('purchase_price', type=float),
            current_value=request.form.get('current_value', type=float),
            condition=request.form.get('condition', 'good'),
            status=request.form.get('status', 'available'),
            location=request.form.get('location', '').strip() or 'warehouse',
            day_rate=request.form.get('day_rate', type=float),
            week_rate=request.form.get('week_rate', type=float),
            notes=request.form.get('notes', '').strip() or None,
        )

        # Handle photo upload
        photo = request.files.get('photo')
        if photo and photo.filename and allowed_image(photo.filename):
            path = save_photo(photo)
            add_equipment_photo(equipment_id, path, is_primary=True)

        flash(f'{make} {model} added successfully.', 'success')
        return redirect(url_for('equipment.detail', equipment_id=equipment_id))

    return render_template('equipment/add.html', categories=categories)


@equipment_bp.route('/<int:equipment_id>')
@login_required
def detail(equipment_id):
    item = get_equipment_by_id(equipment_id)
    if not item:
        flash('Equipment not found.', 'danger')
        return redirect(url_for('equipment.list'))

    photos = get_equipment_photos(equipment_id)
    return render_template('equipment/detail.html', item=item, photos=photos)


@equipment_bp.route('/<int:equipment_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(equipment_id):
    item = get_equipment_by_id(equipment_id)
    if not item:
        flash('Equipment not found.', 'danger')
        return redirect(url_for('equipment.list'))

    categories = get_categories()

    if request.method == 'POST':
        update_equipment(
            equipment_id,
            make=request.form.get('make', '').strip(),
            model=request.form.get('model', '').strip(),
            serial_number=request.form.get('serial_number', '').strip() or None,
            category_id=request.form.get('category_id', type=int),
            subcategory=request.form.get('subcategory', '').strip() or None,
            purchase_date=request.form.get('purchase_date') or None,
            purchase_price=request.form.get('purchase_price', type=float),
            current_value=request.form.get('current_value', type=float),
            condition=request.form.get('condition', 'good'),
            status=request.form.get('status', 'available'),
            location=request.form.get('location', '').strip() or 'warehouse',
            day_rate=request.form.get('day_rate', type=float),
            week_rate=request.form.get('week_rate', type=float),
            notes=request.form.get('notes', '').strip() or None,
        )

        # Handle new photo upload
        photo = request.files.get('photo')
        if photo and photo.filename and allowed_image(photo.filename):
            path = save_photo(photo)
            add_equipment_photo(equipment_id, path, is_primary=True)

        flash('Equipment updated.', 'success')
        return redirect(url_for('equipment.detail', equipment_id=equipment_id))

    return render_template('equipment/edit.html', item=item, categories=categories)


@equipment_bp.route('/<int:equipment_id>/delete', methods=['POST'])
@login_required
def remove(equipment_id):
    item = get_equipment_by_id(equipment_id)
    if not item:
        flash('Equipment not found.', 'danger')
        return redirect(url_for('equipment.list'))

    delete_equipment(equipment_id)
    flash(f'{item["make"]} {item["model"]} deleted.', 'success')
    return redirect(url_for('equipment.list'))


@equipment_bp.route('/valuation')
@login_required
def valuation():
    data = get_insurance_valuation()
    total_value = sum(row['total_value'] for row in data)
    total_items = sum(row['item_count'] for row in data)
    return render_template('equipment/valuation.html',
                           data=data, total_value=total_value, total_items=total_items)


@equipment_bp.route('/identify', methods=['POST'])
@login_required
def identify():
    """Claude-powered equipment identification from photo."""
    photo = request.files.get('photo')
    if not photo or not photo.filename:
        return jsonify({'success': False, 'error': 'No photo provided'}), 400

    if not allowed_image(photo.filename):
        return jsonify({'success': False, 'error': 'Invalid image format'}), 400

    try:
        from services.claude_service import identify_equipment_from_photo
        import io
        photo_bytes = photo.read()
        result = identify_equipment_from_photo(photo_bytes, photo.content_type)
        photo.seek(0)  # Reset for potential re-read
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
