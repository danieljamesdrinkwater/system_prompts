from flask import Blueprint, render_template
from flask_login import login_required

from models.equipment import get_equipment_stats, get_all_equipment

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    stats = get_equipment_stats()
    needs_attention = get_all_equipment(status='in_repair')
    return render_template('dashboard.html', stats=stats, needs_attention=needs_attention)
