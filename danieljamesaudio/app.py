import os
from flask import Flask
from werkzeug.security import generate_password_hash

from config import Config
from models.database import close_db, init_db, get_db


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure upload directories exist
    os.makedirs(app.config['PHOTO_FOLDER'], exist_ok=True)
    os.makedirs(app.config['MANUAL_FOLDER'], exist_ok=True)

    # Initialise database
    init_db(app)

    # Register teardown
    app.teardown_appcontext(close_db)

    # Set up Flask-Login
    from flask_login import LoginManager
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        from models.database import query_db
        row = query_db('SELECT * FROM users WHERE id = ?', (int(user_id),), one=True)
        if row:
            from flask_login import UserMixin
            user = UserMixin()
            user.id = row['id']
            user.username = row['username']
            user.display_name = row['display_name']
            user.role = row['role']
            return user
        return None

    # Create default owner account if no users exist
    with app.app_context():
        db = get_db()
        user_count = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        if user_count == 0:
            db.execute(
                'INSERT INTO users (username, password_hash, display_name, role) VALUES (?, ?, ?, ?)',
                ('daniel', generate_password_hash('changeme'), 'Daniel James', 'owner')
            )
            db.commit()
            print('Default user created: daniel / changeme (change this password!)')

    # Register blueprints
    from routes.auth import auth_bp
    from routes.equipment import equipment_bp
    from routes.dashboard import dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(equipment_bp)
    app.register_blueprint(dashboard_bp)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
