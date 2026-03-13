import sqlite3
import os

from flask import g, current_app


def get_db():
    """Get a database connection for the current request."""
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
    return g.db


def close_db(e=None):
    """Close the database connection at the end of a request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(app):
    """Initialise the database from schema.sql if it doesn't exist."""
    db_path = app.config['DATABASE']
    if not os.path.exists(db_path):
        with app.app_context():
            db = sqlite3.connect(db_path)
            schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schema.sql')
            with open(schema_path, 'r') as f:
                db.executescript(f.read())
            db.close()
            print(f'Database initialised at {db_path}')


def query_db(query, args=(), one=False):
    """Execute a query and return results."""
    db = get_db()
    cur = db.execute(query, args)
    rv = cur.fetchall()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    """Execute an insert/update/delete and return the lastrowid."""
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    return cur.lastrowid


# Standalone connection for CLI scripts (no Flask context)
def get_standalone_db(db_path=None):
    """Get a database connection outside of Flask context (for CLI scripts)."""
    if db_path is None:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'danieljamesaudio.db')
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    return conn
