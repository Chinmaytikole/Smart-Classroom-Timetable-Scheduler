# config.py - Enhanced version
import os
from datetime import timedelta

class Config:
    # Basic Flask config
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-in-production'
    
    # Database config
    DATABASE_PATH = os.environ.get('DATABASE_PATH') or 'timetable.db'
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload config
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or 'uploads'
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH') or 16 * 1024 * 1024)  # 16MB
    
    # Session config
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Genetic algorithm config
    GA_POPULATION_SIZE = int(os.environ.get('GA_POPULATION_SIZE') or 100)
    GA_GENERATIONS = int(os.environ.get('GA_GENERATIONS') or 500)
    GA_MUTATION_RATE = float(os.environ.get('GA_MUTATION_RATE') or 0.1)
    GA_CROSSOVER_RATE = float(os.environ.get('GA_CROSSOVER_RATE') or 0.8)
    GA_ELITE_SIZE = int(os.environ.get('GA_ELITE_SIZE') or 5)
    
    # Notification config
    NOTIFICATION_RETENTION_DAYS = int(os.environ.get('NOTIFICATION_RETENTION_DAYS') or 30)
    
    # Backup config
    BACKUP_RETENTION_DAYS = int(os.environ.get('BACKUP_RETENTION_DAYS') or 7)
    AUTO_BACKUP = os.environ.get('AUTO_BACKUP') or 'True'
    
    # Logging config
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    LOG_FILE = os.environ.get('LOG_FILE') or 'app.log'
    LOG_MAX_BYTES = int(os.environ.get('LOG_MAX_BYTES') or 10 * 1024 * 1024)  # 10MB
    LOG_BACKUP_COUNT = int(os.environ.get('LOG_BACKUP_COUNT') or 5)
    
    # Email config (for future notifications)
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') or 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # Performance config
    CACHE_TYPE = os.environ.get('CACHE_TYPE') or 'simple'
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get('CACHE_DEFAULT_TIMEOUT') or 300)
    
    # Security config
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE') or 'False'
    SESSION_COOKIE_HTTPONLY = os.environ.get('SESSION_COOKIE_HTTPONLY') or 'True'
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE') or 'Lax'

class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    TEMPLATES_AUTO_RELOAD = True

class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    LOG_LEVEL = 'WARNING'

class TestingConfig(Config):
    TESTING = True
    DATABASE_PATH = ':memory:'
    WTF_CSRF_ENABLED = False

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}