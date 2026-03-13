import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-this-in-production')
    DATABASE = os.environ.get('DATABASE', os.path.join(BASE_DIR, 'danieljamesaudio.db'))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    PHOTO_FOLDER = os.path.join(BASE_DIR, 'uploads', 'photos')
    MANUAL_FOLDER = os.path.join(BASE_DIR, 'uploads', 'manuals')
    VAULT_FOLDER = os.path.join(BASE_DIR, 'vault')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ALLOWED_MANUAL_EXTENSIONS = {'pdf'}
