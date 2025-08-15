import os
from datetime import timedelta

class Config:
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'

    # MySQL configuration
    MYSQL_HOST = 'localhost'
    MYSQL_USER = 'root'  # Replace with your MySQL username
    MYSQL_PASSWORD = 'Chandana'  # Replace with your MySQL password
    MYSQL_DB = 'exam_portal'
    MYSQL_CURSORCLASS = 'DictCursor'  # Important: Makes cursor return dictionaries

    # File upload configuration
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload

    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)