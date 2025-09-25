# app.py - Complete Timetable Management System

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, make_response
from functools import wraps
import sqlite3
import os
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import json
from datetime import datetime, timedelta
import random
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, date
from routes.timetable import timetable_bp
from routes.events import events_bp
from routes.exams import exams_bp   
from routes.notifications import notifications_bp   
from routes.users import users_bp  # Import the users blueprint
from routes.attendance import attendance_bp  # Import the attendance blueprint
from routes.faculty_events import faculty_events_bp
app = Flask(__name__)

# App configuration
app.secret_key = 'your_secret_key_here_change_in_production'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

app.register_blueprint(events_bp)
app.register_blueprint(exams_bp)
app.register_blueprint(timetable_bp)    
app.register_blueprint(notifications_bp)
app.register_blueprint(users_bp)  # Register the users blueprint
app.register_blueprint(attendance_bp)  # Register the attendance blueprint
app.register_blueprint(faculty_events_bp)

# Configure logging
logging.basicConfig(level=logging.INFO)
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)

# Context Processor for notifications
@app.context_processor
def inject_notifications():
    if 'user_id' in session:
        conn = sqlite3.connect('timetable.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM notifications WHERE user_id = ? AND is_read = 0', (session['user_id'],))
        notification_count = cursor.fetchone()['count']
        conn.close()
        return {'notification_count': notification_count}
    return {'notification_count': 0}

# Custom Jinja2 filters
def time_ago_filter(dt):
    if not isinstance(dt, datetime):
        try:
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return "N/A"
            
    now = datetime.now()
    delta = now - dt

    if delta < timedelta(minutes=1):
        return "just now"
    elif delta < timedelta(hours=1):
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif delta < timedelta(days=1):
        hours = int(delta.total_seconds() / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif delta < timedelta(weeks=1):
        days = delta.days
        return f"{days} day{'s' if days != 1 else ''} ago"
    else:
        return dt.strftime("%B %d, %Y")

def format_datetime_filter(dt):
    if not isinstance(dt, datetime):
        try:
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return "N/A"
            
    return dt.strftime("%Y-%m-%d %I:%M %p")

def format_date_filter(dt, format_string='%Y-%m-%d'):
    if not isinstance(dt, datetime):
        try:
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            try:
                dt = datetime.strptime(dt, "%Y-%m-%d")
            except (ValueError, TypeError):
                return "N/A"
                
    return dt.strftime(format_string)

# Register the filters
app.jinja_env.filters['format_datetime'] = format_datetime_filter
app.jinja_env.filters['time_ago'] = time_ago_filter
app.jinja_env.filters['format_date'] = format_date_filter

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, make_response
from functools import wraps
import sqlite3
import os
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import json
from datetime import datetime, timedelta
import random
import logging
from logging.handlers import RotatingFileHandler
import base64
import io
from PIL import Image
import requests
import qrcode
import secrets

# Face++ API Configuration
FACE_API_KEY = 'olmKEZahA4G_5Ps1VWwGnlbWVjpfYhJT'
FACE_API_SECRET = 'o0Nek-Qs2pp2wX9WLRiNy9rjiVYe_wlr'  # Using same as key for demo


app.secret_key = 'your_secret_key_here_change_in_production'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Configure logging
logging.basicConfig(level=logging.INFO)
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)

# Face++ API Function
def verify_face_api(image_data):
    """Face++ API for facial detection and verification"""
    try:
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        
        files = {'image_file': ('face.jpg', image_bytes, 'image/jpeg')}
        data = {
            'api_key': 'olmKEZahA4G_5Ps1VWwGnlbWVjpfYhJT',
            'api_secret': 'o0Nek-Qs2pp2wX9WLRiNy9rjiVYe_wlr',
            'return_attributes': 'facequality,eyestatus'
        }
        
        response = requests.post(
            'https://api-us.faceplusplus.com/facepp/v3/detect', 
            files=files, 
            data=data,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            faces = result.get('faces', [])
            
            if len(faces) == 1:
                face = faces[0]
                attributes = face.get('attributes', {})
                
                face_quality = attributes.get('facequality', {}).get('value', 0)
                blur_threshold = attributes.get('facequality', {}).get('threshold', 50.0)
                
                if face_quality >= blur_threshold:
                    eye_status = attributes.get('eyestatus', {})
                    left_eye = eye_status.get('left_eye', {}).get('status', '')
                    right_eye = eye_status.get('right_eye', {}).get('status', '')
                    
                    if left_eye != 'close' and right_eye != 'close':
                        return True, 1, 85.0
                    else:
                        return False, 1, 30.0
                else:
                    return False, 1, 20.0
            else:
                return False, len(faces), 0.0
            
        else:
            return False, 0, 0.0
            
    except Exception as e:
        print(f"Face++ API Error: {e}")
        return False, 0, 0.0

# Context Processor for notifications
@app.context_processor
def inject_notifications():
    if 'user_id' in session:
        conn = sqlite3.connect('timetable.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM notifications WHERE user_id = ? AND is_read = 0', (session['user_id'],))
        notification_count = cursor.fetchone()['count']
        conn.close()
        return {'notification_count': notification_count}
    return {'notification_count': 0}

# Custom Jinja2 filters
def time_ago_filter(dt):
    if not isinstance(dt, datetime):
        try:
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return "N/A"
            
    now = datetime.now()
    delta = now - dt

    if delta < timedelta(minutes=1):
        return "just now"
    elif delta < timedelta(hours=1):
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif delta < timedelta(days=1):
        hours = int(delta.total_seconds() / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif delta < timedelta(weeks=1):
        days = delta.days
        return f"{days} day{'s' if days != 1 else ''} ago"
    else:
        return dt.strftime("%B %d, %Y")

def format_datetime_filter(dt):
    if not isinstance(dt, datetime):
        try:
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return "N/A"
            
    return dt.strftime("%Y-%m-%d %I:%M %p")

def format_date_filter(dt, format_string='%Y-%m-%d'):
    if not isinstance(dt, datetime):
        try:
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            try:
                dt = datetime.strptime(dt, "%Y-%m-%d")
            except (ValueError, TypeError):
                return "N/A"
                
    return dt.strftime(format_string)

# Register the filters
app.jinja_env.filters['format_datetime'] = format_datetime_filter
app.jinja_env.filters['time_ago'] = time_ago_filter
app.jinja_env.filters['format_date'] = format_date_filter

# Database initialization
def init_db():
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()

    # Signup requests table (for pending approvals)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signup_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            student_id TEXT UNIQUE NOT NULL,
            batch_id INTEGER,
            roll_number INTEGER,
            password TEXT NOT NULL,
            status TEXT DEFAULT 'PENDING',
            requested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            approved_at DATETIME,
            approved_by INTEGER,
            FOREIGN KEY (batch_id) REFERENCES batches (id),
            FOREIGN KEY (approved_by) REFERENCES users (id)
        )
    ''')
    
    # Create tables
     # Update users table to include employee_id as foreign key
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT,
            role TEXT DEFAULT 'coordinator',
            department_id INTEGER,
            employee_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments (id),
            FOREIGN KEY (employee_id) REFERENCES faculty (employee_id)
        )
    ''')
    
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

       # Facial recognition logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS face_verification_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            qr_session_id INTEGER,
            face_count INTEGER,
            confidence_score REAL,
            api_response TEXT,
            is_successful BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (qr_session_id) REFERENCES qr_sessions (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            department_id INTEGER,
            subject_type TEXT DEFAULT 'THEORY',
            classes_per_week INTEGER DEFAULT 3,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS faculty (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            employee_id TEXT UNIQUE NOT NULL,
            department_id INTEGER,
            max_hours_per_day INTEGER DEFAULT 8,
            preferred_times TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS classrooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            capacity INTEGER,
            type TEXT DEFAULT 'CLASSROOM',
            department_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department_id INTEGER,
            semester INTEGER,
            strength INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS timetables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department_id INTEGER,
            semester INTEGER,
            fitness_score REAL,
            generated_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments (id),
            FOREIGN KEY (generated_by) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS timetable_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timetable_id INTEGER,
            batch_id INTEGER,
            day TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            subject_id INTEGER,
            faculty_id INTEGER,
            classroom_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (timetable_id) REFERENCES timetables (id),
            FOREIGN KEY (batch_id) REFERENCES batches (id),
            FOREIGN KEY (subject_id) REFERENCES subjects (id),
            FOREIGN KEY (faculty_id) REFERENCES faculty (id),
            FOREIGN KEY (classroom_id) REFERENCES classrooms (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS faculty_subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            faculty_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (faculty_id) REFERENCES faculty (id),
            FOREIGN KEY (subject_id) REFERENCES subjects (id),
            UNIQUE(faculty_id, subject_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS faculty_leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            faculty_id INTEGER NOT NULL,
            avg_leaves_per_month REAL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (faculty_id) REFERENCES faculty (id),
            UNIQUE(faculty_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fixed_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timetable_id INTEGER,
            batch_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            subject_id INTEGER NOT NULL,
            faculty_id INTEGER,
            classroom_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (timetable_id) REFERENCES timetables (id),
            FOREIGN KEY (batch_id) REFERENCES batches (id),
            FOREIGN KEY (subject_id) REFERENCES subjects (id),
            FOREIGN KEY (faculty_id) REFERENCES faculty (id),
            FOREIGN KEY (classroom_id) REFERENCES classrooms (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department_id INTEGER,
            semester INTEGER,
            subject_id INTEGER,
            exam_date DATE NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            classroom_id INTEGER,
            created_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments (id),
            FOREIGN KEY (subject_id) REFERENCES subjects (id),
            FOREIGN KEY (classroom_id) REFERENCES classrooms (id),
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
    ''')
    
    # cursor.execute('''
    #     CREATE TABLE IF NOT EXISTS events (
    #         id INTEGER PRIMARY KEY AUTOINCREMENT,
    #         title TEXT NOT NULL,
    #         description TEXT,
    #         event_date DATE NOT NULL,
    #         start_time TIME NOT NULL,
    #         end_time TIME NOT NULL,
    #         location TEXT,
    #         created_by INTEGER,
    #         created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    #         FOREIGN KEY (created_by) REFERENCES users (id)
    #     )
    # ''')
    # In your init_db() function, add this table creation:
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            event_type TEXT DEFAULT 'event',  -- event, exam, holiday, deadline
            event_date DATE NOT NULL,
            start_time TIME,
            end_time TIME,
            location TEXT,
            priority TEXT DEFAULT 'medium',   -- high, medium, low
            created_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timetable_slot_id INTEGER,
            faculty_id INTEGER,
            batch_id INTEGER,
            date DATE NOT NULL,
            status TEXT DEFAULT 'PRESENT',
            notes TEXT,
            recorded_by INTEGER,
            recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (timetable_slot_id) REFERENCES timetable_slots (id),
            FOREIGN KEY (faculty_id) REFERENCES faculty (id),
            FOREIGN KEY (batch_id) REFERENCES batches (id),
            FOREIGN KEY (recorded_by) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            type TEXT DEFAULT 'info',
            is_read BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            table_name TEXT NOT NULL,
            record_id INTEGER,
            changes TEXT,
            ip_address TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    # Add these to your init_db() function after existing tables

    # Students table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            batch_id INTEGER,
            roll_number INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (batch_id) REFERENCES batches (id)
        )
    ''')

    # Student login credentials
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
    ''')

    # Marks/grades table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            subject_id INTEGER,
            exam_type TEXT NOT NULL,
            marks_obtained REAL,
            total_marks REAL,
            percentage REAL,
            exam_date DATE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (subject_id) REFERENCES subjects (id)
        )
    ''')
    
    # Student attendance (more specific)
    # cursor.execute('''
    #     CREATE TABLE IF NOT EXISTS student_attendance (
    #         id INTEGER PRIMARY KEY AUTOINCREMENT,
    #         student_id TEXT NOT NULL,
    #         timetable_slot_id INTEGER,
    #         date DATE NOT NULL,
    #         status TEXT DEFAULT 'PRESENT',
    #         recorded_by INTEGER,
    #         recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    #         FOREIGN KEY (student_id) REFERENCES students (student_id),
    #         FOREIGN KEY (timetable_slot_id) REFERENCES timetable_slots (id),
    #         FOREIGN KEY (recorded_by) REFERENCES users (id)
    #     )
    # ''')
    # In your init_db() function, update the student_attendance table creation:
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            timetable_slot_id INTEGER,
            date DATE NOT NULL,
            status TEXT DEFAULT 'PENDING',  
            attendance_time TIME,  
            recorded_by INTEGER,
            recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            qr_session_id INTEGER,
            face_verification_data TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (timetable_slot_id) REFERENCES timetable_slots (id),
            FOREIGN KEY (recorded_by) REFERENCES users (id),
            FOREIGN KEY (qr_session_id) REFERENCES qr_sessions (id)
        )
    ''')
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS teacher_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    teacher_id INTEGER NOT NULL,
    is_attending BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (teacher_id) REFERENCES faculty(id) ON DELETE CASCADE,  -- Changed from teachers to faculty
    UNIQUE(event_id, teacher_id)
);
        ''')
        # Create default admin user if not exists
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if cursor.fetchone()[0] == 0:
            hashed_password = generate_password_hash('admin123')
            cursor.execute(
                "INSERT INTO users (username, password, full_name, role) VALUES (?, ?, ?, ?)",
                ('admin', hashed_password, 'Administrator', 'admin')
            )
        
        # Create default department if none exists
    cursor.execute("SELECT COUNT(*) FROM departments")
    if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO departments (name, code) VALUES (?, ?)",
                ('Computer Science', 'CSE')
            )
        
    conn.commit()
    conn.close()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin required decorator - ADD THIS
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Custom Jinja2 filters
def month_abbr_filter(month_num):
    """Convert month number to abbreviated month name"""
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    try:
        return months[int(month_num) - 1]
    except (ValueError, IndexError):
        return 'N/A'

def time_ago_filter(dt):
    if not isinstance(dt, datetime):
        try:
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return "N/A"
            
    now = datetime.now()
    delta = now - dt

    if delta < timedelta(minutes=1):
        return "just now"
    elif delta < timedelta(hours=1):
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif delta < timedelta(days=1):
        hours = int(delta.total_seconds() / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif delta < timedelta(weeks=1):
        days = delta.days
        return f"{days} day{'s' if days != 1 else ''} ago"
    else:
        return dt.strftime("%B %d, %Y")

def format_datetime_filter(dt):
    if not isinstance(dt, datetime):
        try:
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return "N/A"
            
    return dt.strftime("%Y-%m-%d %I:%M %p")

def format_date_filter(dt, format_string='%Y-%m-%d'):
    if not isinstance(dt, datetime):
        try:
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            try:
                dt = datetime.strptime(dt, "%Y-%m-%d")
            except (ValueError, TypeError):
                return "N/A"
                
    return dt.strftime(format_string)

# Register the filters
app.jinja_env.filters['format_datetime'] = format_datetime_filter
app.jinja_env.filters['time_ago'] = time_ago_filter
app.jinja_env.filters['format_date'] = format_date_filter
app.jinja_env.filters['month_abbr'] = month_abbr_filter  # Add this line

# Faculty required decorator
def faculty_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'teacher_id' not in session:
            flash('Faculty access required.', 'error')
            return redirect(url_for('teacher_login'))
        return f(*args, **kwargs)
    return decorated_function

# Student required decorator
def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'student_id' not in session:
            flash('Student access required.', 'error')
            return redirect(url_for('student_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/student/signup', methods=['GET', 'POST'])
def student_signup():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        student_id = request.form['student_id']
        batch_id = request.form['batch_id']
        roll_number = request.form['roll_number']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # Validate passwords match
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('login'))
        
        # Validate password strength
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return redirect(url_for('login'))
        
        conn = sqlite3.connect('timetable.db')
        cursor = conn.cursor()
        
        try:
            # Check if student ID already exists
            cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (student_id,))
            if cursor.fetchone()[0] > 0:
                flash('Student ID already exists.', 'error')
                return redirect(url_for('login'))
            
            # Check if email already exists
            cursor.execute('SELECT COUNT(*) FROM students WHERE email = ?', (email,))
            if cursor.fetchone()[0] > 0:
                flash('Email already exists.', 'error')
                return redirect(url_for('login'))
            
            # Check if roll number already exists in the same batch
            cursor.execute('SELECT COUNT(*) FROM students WHERE batch_id = ? AND roll_number = ?', (batch_id, roll_number))
            if cursor.fetchone()[0] > 0:
                flash('Roll number already exists in this batch.', 'error')
                return redirect(url_for('login'))
            
            # Hash password
            hashed_password = generate_password_hash(password)
            
            # Create signup request
            cursor.execute('''
                INSERT INTO signup_requests (full_name, email, student_id, batch_id, roll_number, password, status)
                VALUES (?, ?, ?, ?, ?, ?, 'PENDING')
            ''', (full_name, email, student_id, batch_id, roll_number, hashed_password))
            
            conn.commit()
            flash('Signup request submitted successfully! Please wait for admin approval.', 'success')
            
        except sqlite3.IntegrityError as e:
            flash('Error creating account. Please try again.', 'error')
        finally:
            conn.close()
        
        return redirect(url_for('login'))
    
    return redirect(url_for('login'))
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Get batches for signup form
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM batches ORDER BY name')
    batches = cursor.fetchall()
    conn.close()
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        login_type = request.form.get('login_type', 'admin')
        
        # Handle different login types
        if login_type == 'admin':
            conn = sqlite3.connect('timetable.db')
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            conn.close()
            
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['full_name'] = user['full_name']
                session['role'] = user['role']
                
                log_audit('LOGIN', 'users', user['id'])
                flash('Admin login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid admin credentials.', 'error')
        
        elif login_type == 'teacher':
            # Redirect to teacher login handler
            return redirect(url_for('teacher_login'))
        
        elif login_type == 'student':
            # Redirect to student login handler
            return redirect(url_for('student_login'))
    
    return render_template('login.html', batches=batches)

@app.route('/admin/signup-requests')
@admin_required
def signup_requests():
    """Show pending student signup requests"""
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT sr.*, b.name as batch_name, d.name as department_name
        FROM signup_requests sr
        LEFT JOIN batches b ON sr.batch_id = b.id
        LEFT JOIN departments d ON b.department_id = d.id
        WHERE sr.status = 'PENDING'
        ORDER BY sr.requested_at DESC
    ''')
    requests = cursor.fetchall()
    
    conn.close()
    
    return render_template('signup_requests.html', requests=requests)

@app.route('/admin/approve-signup/<int:request_id>')
@admin_required
def approve_signup(request_id):
    """Approve a student signup request"""
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        # Get the signup request
        cursor.execute('SELECT * FROM signup_requests WHERE id = ?', (request_id,))
        request_data = cursor.fetchone()
        
        if not request_data:
            flash('Signup request not found.', 'error')
            return redirect(url_for('signup_requests'))
        
        # Create student record
        cursor.execute('''
            INSERT INTO students (student_id, name, email, batch_id, roll_number)
            VALUES (?, ?, ?, ?, ?)
        ''', (request_data[3], request_data[1], request_data[2], request_data[4], request_data[5]))
        
        # Create student credentials
        cursor.execute('''
            INSERT INTO student_credentials (student_id, password)
            VALUES (?, ?)
        ''', (request_data[3], request_data[6]))
        
        # Update request status
        cursor.execute('''
            UPDATE signup_requests 
            SET status = 'APPROVED', approved_at = datetime('now'), approved_by = ?
            WHERE id = ?
        ''', (session['user_id'], request_id))
        
        conn.commit()
        flash('Student signup approved successfully!', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Error approving signup: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('signup_requests'))

@app.route('/admin/reject-signup/<int:request_id>')
@admin_required
def reject_signup(request_id):
    """Reject a student signup request"""
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE signup_requests 
            SET status = 'REJECTED', approved_at = datetime('now'), approved_by = ?
            WHERE id = ?
        ''', (session['user_id'], request_id))
        
        conn.commit()
        flash('Student signup rejected.', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Error rejecting signup: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('signup_requests'))

@app.route('/teacher/logout')
def teacher_logout():
    """Logout for faculty users"""
    if 'teacher_id' in session:
        # Log the logout action if you have audit logging for teachers
        teacher_id = session.get('teacher_id')
        teacher_name = session.get('teacher_name')
        flash(f'Goodbye, {teacher_name}!', 'info')
    
    session.clear()
    flash('Teacher logout successful.', 'info')
    return redirect(url_for('login'))

@app.route('/student/logout')
def student_logout():
    """Logout for student users"""
    if 'student_id' in session:
        # Log the logout action if you have audit logging for students
        student_id = session.get('student_id')
        student_name = session.get('student_name')
        flash(f'Goodbye, {student_name}!', 'info')
    
    session.clear()
    flash('Student logout successful.', 'info')
    return redirect(url_for('login'))

@app.route('/teacher/login', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('timetable.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if it's a valid user with faculty role
        cursor.execute('''
            SELECT u.*, f.name as faculty_name, f.employee_id, d.name as department_name 
            FROM users u
            LEFT JOIN faculty f ON u.employee_id = f.employee_id
            LEFT JOIN departments d ON u.department_id = d.id 
            WHERE u.username = ? AND u.role = 'faculty'
        ''', (username,))
        user = cursor.fetchone()
        
        if user:
            # Check password using proper hashing
            if check_password_hash(user['password'], password):
                session['teacher_id'] = user['id']
                session['teacher_name'] = user['faculty_name'] or user['full_name']
                session['username'] = user['username']
                session['employee_id'] = user['employee_id']
                session['department_name'] = user['department_name']
                session['role'] = 'faculty'  # Set role for authorization
                
                flash('Teacher login successful!', 'success')
                return redirect(url_for('teacher_dashboard'))
            else:
                flash('Invalid password.', 'error')
        else:
            flash('Invalid username or you are not registered as faculty.', 'error')
        
        conn.close()
    
    # Render teacher login page instead of redirecting to general login
    return render_template('teacher_login.html')  # You'll need to create this template

@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        student_id = request.form['student_id']
        password = request.form['password']
        
        conn = sqlite3.connect('timetable.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT sc.*, s.*, b.name as batch_name, d.name as department_name
            FROM student_credentials sc
            JOIN students s ON sc.student_id = s.student_id
            JOIN batches b ON s.batch_id = b.id
            JOIN departments d ON b.department_id = d.id
            WHERE sc.student_id = ?
        ''', (student_id,))
        student = cursor.fetchone()
        conn.close()
        
        if student and check_password_hash(student['password'], password):
            session['student_id'] = student['student_id']
            session['student_name'] = student['name']
            session['batch_id'] = student['batch_id']
            session['batch_name'] = student['batch_name']
            session['department_name'] = student['department_name']
            session['roll_number'] = student['roll_number']
            
            flash('Student login successful!', 'success')
            return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid student ID or password.', 'error')
            return redirect(url_for('login') + '#student')
    
    # For GET requests, redirect to main login with student tab
    return redirect(url_for('login') + '#student')  
@app.route('/teacher/dashboard')
@faculty_required
def teacher_dashboard():
    # Add teacher dashboard logic here
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get today's date and day
    today = datetime.now().date()
    today_day = datetime.now().strftime('%A')
    
    # Get teacher's today's schedule
    cursor.execute('''
        SELECT ts.*, b.name as batch_name, s.name as subject_name, 
               c.name as classroom_name, s.code as subject_code
        FROM timetable_slots ts
        LEFT JOIN batches b ON ts.batch_id = b.id
        LEFT JOIN subjects s ON ts.subject_id = s.id
        LEFT JOIN classrooms c ON ts.classroom_id = c.id
        WHERE ts.faculty_id = ? AND ts.day = ?
        ORDER BY ts.time_slot
    ''', (session['teacher_id'], today_day))
    todays_schedule = cursor.fetchall()
    
    # Get teacher's weekly class count
    cursor.execute('''
        SELECT COUNT(*) as weekly_classes
        FROM timetable_slots
        WHERE faculty_id = ?
    ''', (session['teacher_id'],))
    weekly_classes = cursor.fetchone()['weekly_classes']
    
    # Get subjects taught by this faculty
    cursor.execute('''
        SELECT COUNT(DISTINCT subject_id) as subjects_taught
        FROM timetable_slots
        WHERE faculty_id = ?
    ''', (session['teacher_id'],))
    subjects_taught = cursor.fetchone()['subjects_taught']
    
    # Get attendance stats (you'll need to implement this based on your schema)
    cursor.execute('''
        SELECT COUNT(*) as total_classes,
               SUM(CASE WHEN status = 'PRESENT' THEN 1 ELSE 0 END) as present_count,
               SUM(CASE WHEN status = 'ABSENT' THEN 1 ELSE 0 END) as absent_count
        FROM attendance
        WHERE faculty_id = ? AND date >= date('now', '-30 days')
    ''', (session['teacher_id'],))
    attendance_stats = cursor.fetchone()
    
    # Get upcoming events
    cursor.execute('''
        SELECT * FROM events 
        WHERE event_date >= date('now')
        ORDER BY event_date, start_time
        LIMIT 5
    ''')
    upcoming_events = cursor.fetchall()
    
    conn.close()
    
    stats = {
        'todays_classes': len(todays_schedule),
        'weekly_classes': weekly_classes,
        'subjects_taught': subjects_taught,
        'present_count': attendance_stats['present_count'] if attendance_stats else 0,
        'absent_count': attendance_stats['absent_count'] if attendance_stats else 0,
        'attendance_rate': round((attendance_stats['present_count'] / attendance_stats['total_classes'] * 100), 2) if attendance_stats and attendance_stats['total_classes'] > 0 else 0
    }
    
    return render_template('dashboard_faculty.html',
                         stats=stats,
                         todays_schedule=todays_schedule,
                         upcoming_events=upcoming_events,
                         today=today)


@app.route('/coordinator_login', methods=['POST'])
def coordinator_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        login_type = request.form.get('login_type', 'coordinator')
        
        try:
            # Query coordinator from database
            coordinator = Coordinator.query.filter_by(username=username).first()
            
            if coordinator:
                # Check if password matches
                if coordinator.password == password:  # In production, use password hashing
                    # Login successful - set session variables
                    session['coordinator_id'] = coordinator.id
                    session['username'] = coordinator.username
                    session['full_name'] = coordinator.full_name
                    session['user_type'] = 'coordinator'
                    session['logged_in'] = True
                    
                    flash(f'Welcome back, {coordinator.full_name}!', 'success')
                    return redirect(url_for('coordinator_dashboard'))
                else:
                    flash('Invalid password. Please try again.', 'error')
            else:
                flash('Coordinator not found. Please check your credentials.', 'error')
                
        except Exception as e:
            flash('Login error. Please try again.', 'error')
            print(f"Coordinator login error: {str(e)}")
        
        return redirect(url_for('login_page'))

# Coordinator Dashboard Route
@app.route('/coordinator_dashboard')
def coordinator_dashboard():
    if 'user_type' not in session or session['user_type'] != 'coordinator':
        flash('Please login as coordinator to access this page.', 'error')
        return redirect(url_for('login_page'))
    
    # You can add coordinator-specific data here
    coordinator_data = {
        'name': session.get('full_name', 'Coordinator'),
        'username': session.get('username', '')
    }
    
    return render_template('coordinator_dashboard.html', **coordinator_data)

# Coordinator Logout Route
@app.route('/coordinator_logout')
def coordinator_logout():
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('login_page'))

    
@app.route('/faculty/generate-qr/<int:timetable_slot_id>')
@faculty_required
def generate_qr(timetable_slot_id):
    """Generate QR code for a class session"""
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get timetable slot details
    cursor.execute('''
        SELECT ts.*, s.name as subject_name, b.name as batch_name, f.name as faculty_name
        FROM timetable_slots ts
        LEFT JOIN subjects s ON ts.subject_id = s.id
        LEFT JOIN batches b ON ts.batch_id = b.id
        LEFT JOIN faculty f ON ts.faculty_id = f.id
        WHERE ts.id = ?
    ''', (timetable_slot_id,))
    slot = cursor.fetchone()
    
    if not slot:
        flash('Timetable slot not found.', 'error')
        return redirect(url_for('teacher_dashboard'))
    
    # Generate unique QR code
    qr_code = secrets.token_urlsafe(32)
    
    # Set expiration time (15 minutes from now)
    expires_at = datetime.now() + timedelta(minutes=15)
    
    # Deactivate any existing QR codes for this slot
    cursor.execute('UPDATE qr_sessions SET is_active = 0 WHERE timetable_slot_id = ?', (timetable_slot_id,))
    
    # Create new QR session
    cursor.execute('''
        INSERT INTO qr_sessions (faculty_id, timetable_slot_id, qr_code, expires_at)
        VALUES (?, ?, ?, ?)
    ''', (session['teacher_id'], timetable_slot_id, qr_code, expires_at))
    
    conn.commit()
    conn.close()
    
    # Generate QR code image
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_code)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64 for displaying in HTML
    buffered = io.BytesIO()
    qr_img.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    return render_template('faculty_qr.html', 
                         slot=slot, 
                         qr_code=qr_code, 
                         qr_base64=qr_base64,
                         expires_at=expires_at)

@app.route('/student/scan-face')
@student_required
def student_scan_face():
    """QR + Face scanning interface for students"""
    return render_template('student_scan_face.html')
import cv2
import threading
import time
from flask import Response, jsonify
import base64
import numpy as np
import json
from pyzbar.pyzbar import decode

# Global variables for camera management
camera = None
camera_lock = threading.Lock()
is_camera_running = False
latest_qr_data = None

# QR detection optimization variables
frame_count = 0
skip_frames = 2  # Process every 2nd frame for QR detection
qr_detector = cv2.QRCodeDetector()  # OpenCV's faster QR detector

def generate_frames():
    """Generate camera frames for MJPEG streaming with QR detection"""
    global camera, is_camera_running, latest_qr_data, frame_count
    
    with camera_lock:
        if camera is None or not camera.isOpened():
            camera = cv2.VideoCapture(0)
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            camera.set(cv2.CAP_PROP_FPS, 15)
    
    is_camera_running = True
    
    while is_camera_running:
        success, frame = camera.read()
        if not success:
            break
        else:
            frame_count += 1
            
            # Only process QR detection on every Nth frame for speed
            if frame_count % skip_frames == 0:
                # Create smaller grayscale version for faster QR detection
                small_frame = cv2.resize(frame, (320, 240))
                gray_small = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
                
                # Try OpenCV's QR detector first (faster)
                try:
                    data, points, _ = qr_detector.detectAndDecode(gray_small)
                    if data:
                        try:
                            # Try to parse as JSON
                            parsed_data = json.loads(data)
                            latest_qr_data = parsed_data
                            
                            # Scale points back to original frame size for drawing
                            if points is not None:
                                points = points * 2  # Scale factor from 320->640
                                points = points.astype(int)
                                cv2.polylines(frame, [points], True, (0, 255, 0), 2)
                                cv2.putText(frame, "QR Detected", 
                                          (points[0][0], points[0][1] - 10),
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                        except json.JSONDecodeError:
                            # Valid QR but not JSON
                            if points is not None:
                                points = points * 2
                                points = points.astype(int)
                                cv2.polylines(frame, [points], True, (255, 0, 0), 2)
                                cv2.putText(frame, "Invalid QR", 
                                          (points[0][0], points[0][1] - 10),
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)
                except:
                    # Fallback to pyzbar if OpenCV fails
                    decoded_objects = decode(gray_small)
                    for obj in decoded_objects:
                        try:
                            qr_data = obj.data.decode('utf-8')
                            # Try to parse as JSON
                            parsed_data = json.loads(qr_data)
                            latest_qr_data = parsed_data
                            
                            # Scale coordinates back to original frame
                            (x, y, w, h) = obj.rect
                            x, y, w, h = x*2, y*2, w*2, h*2
                            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                            cv2.putText(frame, "QR Detected", (x, y-10),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            # If not valid JSON or can't decode, still show detection
                            (x, y, w, h) = obj.rect
                            x, y, w, h = x*2, y*2, w*2, h*2
                            cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
                            cv2.putText(frame, "Invalid QR", (x, y-10),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)
            
            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        time.sleep(0.01)  # Control frame rate

@app.route('/video_feed')
@student_required
def video_feed():
    """Video streaming route for student face verification"""
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start_camera')
@student_required
def start_camera():
    """Start the camera for streaming"""
    global camera, is_camera_running, latest_qr_data, frame_count
    
    # Reset QR data when starting camera
    latest_qr_data = None
    frame_count = 0
    
    with camera_lock:
        if camera is None or not camera.isOpened():
            camera = cv2.VideoCapture(0)
            if not camera.isOpened():
                return jsonify({'success': False, 'message': 'Cannot open camera'})
    
    is_camera_running = True
    return jsonify({'success': True, 'message': 'Camera started'})

@app.route('/stop_camera')
@student_required
def stop_camera():
    """Stop the camera and release resources"""
    global camera, is_camera_running, latest_qr_data
    
    is_camera_running = False
    latest_qr_data = None
    
    with camera_lock:
        if camera and camera.isOpened():
            camera.release()
        camera = None
    
    return jsonify({'success': True, 'message': 'Camera stopped'})

@app.route('/capture_frame', methods=['POST'])
@student_required
def capture_frame():
    """Capture QR data from the latest detected QR code"""
    global latest_qr_data
    print(latest_qr_data)
    
    if latest_qr_data:
        # Validate QR data structure for attendance
        if (isinstance(latest_qr_data, dict) and 
            latest_qr_data.get('type') == 'attendance' and 
            latest_qr_data.get('faculty_id') and 
            latest_qr_data.get('batch_id') and 
            latest_qr_data.get('subject_id')):
            
            # Check expiry if present
            if 'expiry' in latest_qr_data:
                if time.time() * 1000 > latest_qr_data['expiry']:  # Convert to milliseconds
                    return jsonify({
                        'success': True,
                        'qr_detected': True,
                        'qr_data': latest_qr_data,
                        'expired': True,
                        'message': 'QR code has expired'
                    })
            
            # Clear the detected QR data after successful capture
            temp_qr_data = latest_qr_data
            latest_qr_data = None
            
            return jsonify({
                'success': True, 
                'qr_detected': True,
                'qr_data': temp_qr_data,
                'expired': False,
                'message': 'QR code detected successfully'
            })
        else:
            return jsonify({
                'success': True,
                'qr_detected': True,
                'qr_data': latest_qr_data,
                'invalid_format': True,
                'message': 'Invalid QR code format for attendance'
            })
    else:
        return jsonify({
            'success': True,
            'qr_detected': False,
            'message': 'No QR code detected. Please show QR code to camera.'
        })

@app.route('/capture_face_verification', methods=['POST'])
@student_required
def capture_face_verification():
    """Capture face for verification and mark attendance"""
    global camera
    
    try:
        request_data = request.get_json()
        qr_data = request_data.get('qr_data')
        student_id = request_data.get('student_id')
        
        if not qr_data or not student_id:
            return jsonify({'success': False, 'message': 'Missing required data'})
        
        with camera_lock:
            if camera is None or not camera.isOpened():
                return jsonify({'success': False, 'message': 'Camera not available'})
            
            success, frame = camera.read()
            if not success:
                return jsonify({'success': False, 'message': 'Failed to capture frame'})
        
        # Here you would implement face verification logic
        # For now, we'll simulate a successful verification
        
        # Simulate face verification (replace with actual face recognition)
        face_verified = True  # This should be replaced with actual face verification
        confidence_score = 95.2  # This should come from face verification
        
        if face_verified:
            # Mark attendance in database
            # This is where you'd implement your database logic
            attendance_time = time.strftime('%Y-%m-%d %H:%M:%S')
            
            return jsonify({
                'success': True,
                'message': 'Face verified and attendance marked successfully!',
                'subject_name': qr_data.get('subject_id', 'Unknown Subject'),
                'batch_name': qr_data.get('batch_id', 'Unknown Batch'),
                'attendance_time': attendance_time,
                'confidence_score': confidence_score
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Face verification failed. Please try again.'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error during verification: {str(e)}'})

def decode_qr_code(frame):
    """Decode QR code from frame (legacy function, kept for compatibility)"""
    try:
        decoded_objects = decode(frame)
        for obj in decoded_objects:
            if obj.type == 'QRCODE':
                data = obj.data.decode('utf-8')
                try:
                    qr_data = json.loads(data)
                    return qr_data
                except json.JSONDecodeError:
                    return None
    except Exception as e:
        print(f"QR decoding error: {e}")
    
    return None
    
@app.route('/student/dashboard')
@student_required
def student_dashboard():
    """Enhanced student dashboard with schedule, attendance, and events"""
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    student_id = session['student_id']
    
    # Get current date and day
    current_date = datetime.now().strftime('%A, %B %d, %Y')
    today_day = datetime.now().strftime('%A')
    today_date = datetime.now().strftime('%Y-%m-%d')
    
    # Get student's attendance summary (overall)
    cursor.execute('''
        SELECT COUNT(*) as total_classes,
               SUM(CASE WHEN status = 'PRESENT' THEN 1 ELSE 0 END) as present_classes,
               ROUND(SUM(CASE WHEN status = 'PRESENT' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as attendance_percentage
        FROM student_attendance
        WHERE student_id = ?
    ''', (student_id,))
    attendance_summary = cursor.fetchone()
    
    # Get today's classes and attendance status - FIXED QUERY
    cursor.execute('''
        SELECT ts.id as slot_id, ts.time_slot, s.name as subject_name, s.code as subject_code,
               f.name as faculty_name, c.name as classroom_name,
               COALESCE(sa.status, 'PENDING') as status,
               sa.recorded_at as attendance_time  -- Use recorded_at instead of attendance_time
        FROM timetable_slots ts
        LEFT JOIN subjects s ON ts.subject_id = s.id
        LEFT JOIN faculty f ON ts.faculty_id = f.id
        LEFT JOIN classrooms c ON ts.classroom_id = c.id
        LEFT JOIN student_attendance sa ON ts.id = sa.timetable_slot_id 
            AND sa.student_id = ? AND sa.date = ?
        WHERE ts.batch_id = (SELECT batch_id FROM students WHERE student_id = ?)
        AND ts.day = ?
        ORDER BY ts.time_slot
    ''', (student_id, today_date, student_id, today_day))
    today_attendance = cursor.fetchall()
    
    # Get upcoming exams
    cursor.execute('''
        SELECT e.*, s.name as subject_name, c.name as classroom_name
        FROM exams e
        LEFT JOIN subjects s ON e.subject_id = s.id
        LEFT JOIN classrooms c ON e.classroom_id = c.id
        WHERE e.exam_date >= date('now')
        ORDER BY e.exam_date, e.start_time
        LIMIT 5
    ''')
    upcoming_exams = cursor.fetchall()
    
    # Get recent marks
    cursor.execute('''
        SELECT m.*, s.name as subject_name
        FROM marks m
        LEFT JOIN subjects s ON m.subject_id = s.id
        WHERE m.student_id = ?
        ORDER BY m.exam_date DESC
        LIMIT 5
    ''', (student_id,))
    recent_marks = cursor.fetchall()
    
    # Get tomorrow's timetable
    tomorrow_day = (datetime.now() + timedelta(days=1)).strftime('%A')
    cursor.execute('''
        SELECT ts.*, s.name as subject_name, f.name as faculty_name, 
               c.name as classroom_name, b.name as batch_name
        FROM timetable_slots ts
        LEFT JOIN batches b ON ts.batch_id = b.id
        LEFT JOIN subjects s ON ts.subject_id = s.id
        LEFT JOIN faculty f ON ts.faculty_id = f.id
        LEFT JOIN classrooms c ON ts.classroom_id = c.id
        WHERE b.id = (SELECT batch_id FROM students WHERE student_id = ?)
        AND ts.day = ?
        ORDER BY ts.time_slot
    ''', (student_id, tomorrow_day))
    tomorrow_timetable = cursor.fetchall()
    
    # Get upcoming events
    cursor.execute('''
        SELECT * FROM events 
        WHERE event_date >= date('now')
        ORDER BY event_date, start_time
        LIMIT 10
    ''')
    upcoming_events = cursor.fetchall()
    
    # If no events table exists or no events, create sample events for demonstration
    if not upcoming_events:
        upcoming_events = [
            {
                'title': 'College Fest',
                'type': 'event',
                'date': (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d'),
                'time': '10:00 AM',
                'location': 'College Ground',
                'description': 'Annual college cultural festival',
                'priority': 'high'
            },
            {
                'title': 'Project Submission',
                'type': 'deadline',
                'date': (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d'),
                'time': '5:00 PM',
                'location': 'CS Department',
                'description': 'Final project submission deadline',
                'priority': 'high'
            },
            {
                'title': 'Guest Lecture',
                'type': 'event',
                'date': (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'),
                'time': '2:00 PM',
                'location': 'Auditorium',
                'description': 'Guest lecture on AI and Machine Learning',
                'priority': 'medium'
            }
        ]
    
    # Get monthly attendance trend (last 7 days) - FIXED QUERY
    monthly_trend = []
    for i in range(7):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        day_name = (datetime.now() - timedelta(days=i)).strftime('%a')
        
        cursor.execute('''
            SELECT COUNT(*) as total_classes,
                   SUM(CASE WHEN status = 'PRESENT' THEN 1 ELSE 0 END) as present_classes,
                   CASE 
                       WHEN COUNT(*) > 0 THEN ROUND(SUM(CASE WHEN status = 'PRESENT' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2)
                       ELSE 0 
                   END as percentage
            FROM student_attendance
            WHERE student_id = ? AND date = ?
        ''', (student_id, date))
        
        trend_data = cursor.fetchone()
        if trend_data and trend_data['total_classes'] > 0:
            monthly_trend.append({
                'date': date,
                'day': day_name,
                'percentage': trend_data['percentage'] or 0
            })
        else:
            monthly_trend.append({
                'date': date,
                'day': day_name,
                'percentage': 0
            })
    
    # Reverse to show from oldest to newest
    monthly_trend.reverse()
    
    # Get pending tasks count
    cursor.execute('''
        SELECT COUNT(*) as pending_tasks
        FROM timetable_slots ts
        LEFT JOIN student_attendance sa ON ts.id = sa.timetable_slot_id 
            AND sa.student_id = ? AND sa.date = ?
        WHERE ts.batch_id = (SELECT batch_id FROM students WHERE student_id = ?)
        AND ts.day = ?
        AND (sa.status IS NULL OR sa.status = 'PENDING')
    ''', (student_id, today_date, student_id, today_day))
    
    pending_result = cursor.fetchone()
    pending_tasks = pending_result['pending_tasks'] if pending_result else 0
    
    conn.close()
    
    return render_template('student_dashboard.html',
                         attendance_summary=attendance_summary,
                         today_attendance=today_attendance,
                         upcoming_exams=upcoming_exams,
                         recent_marks=recent_marks,
                         tomorrow_timetable=tomorrow_timetable,
                         upcoming_events=upcoming_events,
                         current_date=current_date,
                         monthly_trend=monthly_trend,
                         pending_tasks=pending_tasks)

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Audit logging function
def log_audit(action, table_name, record_id=None, changes=None):
    if 'user_id' in session:
        conn = sqlite3.connect('timetable.db')
        cursor = conn.cursor()
        ip_address = request.remote_addr
        
        cursor.execute(
            "INSERT INTO audit_logs (user_id, action, table_name, record_id, changes, ip_address) VALUES (?, ?, ?, ?, ?, ?)",
            (session['user_id'], action, table_name, record_id, json.dumps(changes) if changes else None, ip_address)
        )
        conn.commit()
        conn.close()

# Notification function
def create_notification(user_id, title, message, type='info'):
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
        (user_id, title, message, type)
    )
    conn.commit()
    conn.close()
@app.route('/api/verify-qr-face', methods=['POST'])
@student_required
def verify_qr_face():
    """Verify QR code and perform face recognition"""
    data = request.get_json()
    qr_code = data.get('qr_code')
    image_data = data.get('image')
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Step 1: Verify QR code
    cursor.execute('''
        SELECT qs.*, ts.day, ts.time_slot, s.name as subject_name, f.name as faculty_name
        FROM qr_sessions qs
        LEFT JOIN timetable_slots ts ON qs.timetable_slot_id = ts.id
        LEFT JOIN subjects s ON ts.subject_id = s.id
        LEFT JOIN faculty f ON ts.faculty_id = f.id
        WHERE qs.qr_code = ? AND qs.is_active = 1 AND qs.expires_at > datetime('now')
    ''', (qr_code,))
    
    qr_session = cursor.fetchone()
    
    if not qr_session:
        return jsonify({'success': False, 'message': 'Invalid or expired QR code'})
    
    # Step 2: Check if already marked attendance
    cursor.execute('''
        SELECT COUNT(*) as count FROM student_attendance 
        WHERE student_id = ? AND timetable_slot_id = ? AND date = date('now')
    ''', (session['student_id'], qr_session['timetable_slot_id']))
    
    if cursor.fetchone()['count'] > 0:
        return jsonify({'success': False, 'message': 'Attendance already marked for this class'})
    
    # Step 3: Face verification using Face++ API
    face_verified, face_count, confidence = verify_face_api(image_data)
    
    # Log face verification attempt
    cursor.execute('''
        INSERT INTO face_verification_logs 
        (student_id, qr_session_id, face_count, confidence_score, is_successful, api_response)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (session['student_id'], qr_session['id'], face_count, confidence, face_verified, 
          json.dumps({'face_count': face_count, 'confidence': confidence})))
    
    if face_verified:
        # Step 4: Mark attendance
        cursor.execute('''
            INSERT INTO student_attendance (student_id, timetable_slot_id, qr_session_id, date, status, recorded_by)
            VALUES (?, ?, ?, date('now'), 'PRESENT', ?)
        ''', (session['student_id'], qr_session['timetable_slot_id'], qr_session['id'], qr_session['faculty_id']))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Attendance marked successfully! Face verification confidence: {confidence:.1f}%',
            'session_info': {
                'subject': qr_session['subject_name'],
                'faculty': qr_session['faculty_name'],
                'time_slot': qr_session['time_slot']
            }
        })
    else:
        conn.commit()
        conn.close()
        
        if face_count == 0:
            message = 'No face detected. Please ensure your face is clearly visible.'
        elif face_count > 1:
            message = f'Multiple faces detected ({face_count}). Please ensure only you are in the frame.'
        else:
            message = f'Face verification failed. Quality score: {confidence:.1f}%'
        
        return jsonify({
            'success': False,
            'message': message,
            'face_count': face_count,
            'confidence': confidence
        })

@app.route('/student/attendance')
@student_required
def student_attendance():
    """View student's attendance records"""
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT sa.*, ts.day, ts.time_slot, s.name as subject_name, 
               f.name as faculty_name, b.name as batch_name
        FROM student_attendance sa
        LEFT JOIN timetable_slots ts ON sa.timetable_slot_id = ts.id
        LEFT JOIN subjects s ON ts.subject_id = s.id
        LEFT JOIN faculty f ON ts.faculty_id = f.id
        LEFT JOIN batches b ON ts.batch_id = b.id
        WHERE sa.student_id = ?
        ORDER BY sa.date DESC, sa.recorded_at DESC
    ''', (session['student_id'],))
    
    attendance_records = cursor.fetchall()
    conn.close()
    
    return render_template('student_attendance.html', attendance_records=attendance_records)

@app.route('/faculty/attendance-records')
@faculty_required
def faculty_attendance_records():
    """View attendance records for faculty's classes"""
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT sa.*, s.name as student_name, st.student_id, ts.day, ts.time_slot, 
               sub.name as subject_name, b.name as batch_name
        FROM student_attendance sa
        LEFT JOIN students st ON sa.student_id = st.student_id
        LEFT JOIN timetable_slots ts ON sa.timetable_slot_id = ts.id
        LEFT JOIN subjects sub ON ts.subject_id = sub.id
        LEFT JOIN batches b ON ts.batch_id = b.id
        LEFT JOIN faculty f ON ts.faculty_id = f.id
        WHERE f.id = ?
        ORDER BY sa.date DESC, ts.time_slot
    ''', (session['teacher_id'],))
    
    attendance_records = cursor.fetchall()
    conn.close()
    
    return render_template('faculty_attendance_records.html', attendance_records=attendance_records)

# Genetic Algorithm Implementation
class EnhancedGeneticTimetable:
    def __init__(self, department_id, semester, population_size=50, mutation_rate=0.1, generations=100):
        self.department_id = department_id
        self.semester = semester
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.generations = generations
        
        # Load data from database
        self.load_data()
        
        # Define time slots and days
        self.days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        self.time_slots = ['9:00-10:00', '10:00-11:00', '11:00-12:00', '12:00-1:00', 
                           '2:00-3:00', '3:00-4:00', '4:00-5:00']
    
    def load_data(self):
        conn = sqlite3.connect('timetable.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Load batches
        cursor.execute('SELECT * FROM batches WHERE department_id = ? AND semester = ?', 
                      (self.department_id, self.semester))
        self.batches = cursor.fetchall()
        
        # Load subjects
        cursor.execute('SELECT * FROM subjects WHERE department_id = ?', (self.department_id,))
        self.subjects = cursor.fetchall()
        
        # Load faculty
        cursor.execute('SELECT * FROM faculty WHERE department_id = ?', (self.department_id,))
        self.faculty = cursor.fetchall()
        
        # Load faculty subjects
        cursor.execute('SELECT * FROM faculty_subjects')
        self.faculty_subjects = cursor.fetchall()
        
        # Load classrooms
        cursor.execute('SELECT * FROM classrooms WHERE department_id = ?', (self.department_id,))
        self.classrooms = cursor.fetchall()
        
        conn.close()
    
    def create_chromosome(self):
        """Create a random timetable (chromosome)"""
        chromosome = {}
        
        for batch in self.batches:
            batch_id = batch['id']
            chromosome[batch_id] = {}
            
            for day in self.days:
                chromosome[batch_id][day] = {}
                
                for time_slot in self.time_slots:
                    # Randomly select a subject, faculty, and classroom
                    subject = random.choice(self.subjects)
                    faculty = self.get_available_faculty(subject['id'])
                    classroom = random.choice(self.classrooms)
                    
                    chromosome[batch_id][day][time_slot] = {
                        'subject_id': subject['id'],
                        'faculty_id': faculty['id'] if faculty else None,
                        'classroom_id': classroom['id']
                    }
        
        return chromosome
    
    def get_available_faculty(self, subject_id):
        """Get faculty who can teach the given subject"""
        available_faculty = []
        for fs in self.faculty_subjects:
            if fs['subject_id'] == subject_id:
                for f in self.faculty:
                    if f['id'] == fs['faculty_id']:
                        available_faculty.append(f)
        
        return random.choice(available_faculty) if available_faculty else None
    
    def calculate_fitness(self, chromosome):
        """Calculate fitness score for a timetable"""
        fitness = 100  # Start with a perfect score
        
        # Check for faculty clashes
        faculty_schedule = {}
        for batch_id, days in chromosome.items():
            for day, time_slots in days.items():
                for time_slot, slot_data in time_slots.items():
                    faculty_id = slot_data['faculty_id']
                    if faculty_id:
                        key = (faculty_id, day, time_slot)
                        if key in faculty_schedule:
                            fitness -= 10  # Penalize faculty clashes
                        else:
                            faculty_schedule[key] = True
        
        # Check for classroom clashes
        classroom_schedule = {}
        for batch_id, days in chromosome.items():
            for day, time_slots in days.items():
                for time_slot, slot_data in time_slots.items():
                    classroom_id = slot_data['classroom_id']
                    key = (classroom_id, day, time_slot)
                    if key in classroom_schedule:
                        fitness -= 10  # Penalize classroom clashes
                    else:
                        classroom_schedule[key] = True
        
        # Check if subjects meet their required classes per week
        for batch_id, days in chromosome.items():
            subject_count = {}
            for day, time_slots in days.items():
                for time_slot, slot_data in time_slots.items():
                    subject_id = slot_data['subject_id']
                    subject_count[subject_id] = subject_count.get(subject_id, 0) + 1
            
            for subject_id, count in subject_count.items():
                # Find the subject to get required classes
                subject = next((s for s in self.subjects if s['id'] == subject_id), None)
                if subject and count != subject['classes_per_week']:
                    fitness -= 5  # Penalize for not meeting required classes
        
        return max(fitness, 0)  # Ensure fitness is not negative
    
    def crossover(self, parent1, parent2):
        """Perform crossover between two parents to create a child"""
        child = {}
        
        for batch_id in parent1:
            child[batch_id] = {}
            
            for day in parent1[batch_id]:
                child[batch_id][day] = {}
                
                for time_slot in parent1[batch_id][day]:
                    # Randomly select gene from either parent
                    if random.random() < 0.5:
                        child[batch_id][day][time_slot] = parent1[batch_id][day][time_slot]
                    else:
                        child[batch_id][day][time_slot] = parent2[batch_id][day][time_slot]
        
        return child
    
    def mutate(self, chromosome):
        """Apply mutation to a chromosome"""
        for batch_id in chromosome:
            for day in chromosome[batch_id]:
                for time_slot in chromosome[batch_id][day]:
                    if random.random() < self.mutation_rate:
                        # Mutate this time slot
                        subject = random.choice(self.subjects)
                        faculty = self.get_available_faculty(subject['id'])
                        classroom = random.choice(self.classrooms)
                        
                        chromosome[batch_id][day][time_slot] = {
                            'subject_id': subject['id'],
                            'faculty_id': faculty['id'] if faculty else None,
                            'classroom_id': classroom['id']
                        }
        
        return chromosome
    
    def evolve(self):
        """Run the genetic algorithm to evolve a population"""
        population = [self.create_chromosome() for _ in range(self.population_size)]
        
        for generation in range(self.generations):
            # Calculate fitness for each chromosome
            fitness_scores = [self.calculate_fitness(chromosome) for chromosome in population]
            
            # Select parents based on fitness (tournament selection)
            parents = []
            for _ in range(self.population_size):
                tournament_size = 3
                tournament = random.sample(list(zip(population, fitness_scores)), tournament_size)
                winner = max(tournament, key=lambda x: x[1])[0]
                parents.append(winner)
            
            # Create new generation through crossover and mutation
            new_population = []
            for i in range(0, self.population_size, 2):
                parent1 = parents[i]
                parent2 = parents[i+1] if i+1 < len(parents) else parents[0]
                
                child1 = self.crossover(parent1, parent2)
                child2 = self.crossover(parent2, parent1)
                
                child1 = self.mutate(child1)
                child2 = self.mutate(child2)
                
                new_population.extend([child1, child2])
            
            population = new_population[:self.population_size]
        
        # Return the best chromosome
        fitness_scores = [self.calculate_fitness(chromosome) for chromosome in population]
        best_index = fitness_scores.index(max(fitness_scores))
        return population[best_index], fitness_scores[best_index]

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    if 'user_id' in session:
        log_audit('LOGOUT', 'users', session['user_id'])
    
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get statistics
    cursor.execute('SELECT COUNT(*) as count FROM departments')
    dept_count = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM subjects')
    sub_count = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM faculty')
    faculty_count = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM timetables')
    timetable_count = cursor.fetchone()['count']
    
    # Get classroom count
    cursor.execute('SELECT COUNT(*) as count FROM classrooms')
    classroom_count = cursor.fetchone()['count']
    
    # Get batch count
    cursor.execute('SELECT COUNT(*) as count FROM batches')
    batch_count = cursor.fetchone()['count']
    
    # Get exam count
    cursor.execute('SELECT COUNT(*) as count FROM exams')
    exam_count = cursor.fetchone()['count']
    
    # Get event count
    cursor.execute('SELECT COUNT(*) as count FROM events')
    event_count = cursor.fetchone()['count']
    
    # Get recent timetables
    cursor.execute('''
        SELECT t.*, d.name as department_name, u.username as generated_by_username
        FROM timetables t 
        LEFT JOIN departments d ON t.department_id = d.id 
        LEFT JOIN users u ON t.generated_by = u.id
        ORDER BY t.created_at DESC 
        LIMIT 5
    ''')
    recent_timetables = cursor.fetchall()
    
    # Get upcoming exams
    cursor.execute('''
        SELECT e.*, d.name as department_name, s.name as subject_name, c.name as classroom_name
        FROM exams e
        LEFT JOIN departments d ON e.department_id = d.id
        LEFT JOIN subjects s ON e.subject_id = s.id
        LEFT JOIN classrooms c ON e.classroom_id = c.id
        WHERE e.exam_date >= date('now')
        ORDER BY e.exam_date, e.start_time
        LIMIT 5
    ''')
    upcoming_exams = cursor.fetchall()
    
    # Get upcoming events
    cursor.execute('''
        SELECT e.*, u.username as created_by_username
        FROM events e
        LEFT JOIN users u ON e.created_by = u.id
        WHERE e.event_date >= date('now')
        ORDER BY e.event_date, e.start_time
        LIMIT 5
    ''')
    upcoming_events = cursor.fetchall()
    
    # Get unread notifications
    cursor.execute('''
        SELECT * FROM notifications 
        WHERE user_id = ? AND is_read = 0
        ORDER BY created_at DESC
        LIMIT 10
    ''', (session['user_id'],))
    notifications = cursor.fetchall()
    
    conn.close()
    
    stats = {
        'departments': dept_count,
        'subjects': sub_count,
        'faculty': faculty_count,
        'timetables': timetable_count,
        'classrooms': classroom_count,
        'batches': batch_count,
        'exams': exam_count,
        'events': event_count
    }
    
    return render_template('dashboard_admin.html', 
                          stats=stats, 
                          recent_timetables=recent_timetables,
                          upcoming_exams=upcoming_exams,
                          upcoming_events=upcoming_events,
                          notifications=notifications)

@app.route('/dashboard')
@login_required
def dashboard():
    # Check user role and redirect to appropriate dashboard
    if session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif 'teacher_id' in session:
        return redirect(url_for('teacher_dashboard'))
    elif 'student_id' in session:
        return redirect(url_for('student_dashboard'))
    else:
        flash('Please log in to access the dashboard.', 'error')
        return redirect(url_for('login'))

@app.route('/departments')
@login_required
def departments():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM departments ORDER BY name')
    departments = cursor.fetchall()
    
    conn.close()
    
    return render_template('departments.html', departments=departments)

@app.route('/department/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_department():
    if request.method == 'POST':
        name = request.form['name']
        code = request.form['code']
        
        conn = sqlite3.connect('timetable.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO departments (name, code) VALUES (?, ?)",
                (name, code)
            )
            conn.commit()
            
            # Log the action
            log_audit('INSERT', 'departments', cursor.lastrowid, {'name': name, 'code': code})
            
            flash('Department added successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('Department code already exists.', 'error')
        finally:
            conn.close()
        
        return redirect(url_for('departments'))
    
    return render_template('add_department.html')
@app.route('/faculty/schedule')
@faculty_required
def faculty_schedule():
    """Display faculty's weekly schedule"""
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get faculty's schedule for the week
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    
    weekly_schedule = {}
    for day in days:
        cursor.execute('''
            SELECT ts.*, b.name as batch_name, s.name as subject_name, 
                   s.code as subject_code, c.name as classroom_name,
                   d.name as department_name
            FROM timetable_slots ts
            LEFT JOIN batches b ON ts.batch_id = b.id
            LEFT JOIN subjects s ON ts.subject_id = s.id
            LEFT JOIN classrooms c ON ts.classroom_id = c.id
            LEFT JOIN departments d ON b.department_id = d.id
            WHERE ts.faculty_id = ? AND ts.day = ?
            ORDER BY ts.time_slot
        ''', (session['teacher_id'], day))
        
        weekly_schedule[day] = cursor.fetchall()
    
    # Get faculty information
    cursor.execute('SELECT * FROM faculty WHERE id = ?', (session['teacher_id'],))
    faculty = cursor.fetchone()
    
    conn.close()
    
    return render_template('faculty_schedule.html', 
                         weekly_schedule=weekly_schedule,
                         days=days,
                         faculty=faculty)
@app.route('/edit_department', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_department(id):
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM departments WHERE id = ?', (id,))
    department = cursor.fetchone()
    
    if request.method == 'POST':
        name = request.form['name']
        code = request.form['code']
        
        try:
            cursor.execute(
                "UPDATE departments SET name = ?, code = ? WHERE id = ?",
                (name, code, id)
            )
            conn.commit()
            
            # Log the action
            log_audit('UPDATE', 'departments', id, {'name': name, 'code': code})
            
            flash('Department updated successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('Department code already exists.', 'error')
        finally:
            conn.close()
        
        return redirect(url_for('departments'))
    
    conn.close()
    return render_template('edit_department.html', department=department)

@app.route('/download_template/<template_type>')
@admin_required
def download_template(template_type):
    """Download CSV templates for different data types"""
    templates = {
        'departments': 'code,name\nCSE,Computer Science Engineering\nECE,Electronics and Communication Engineering\n',
        'subjects': 'code,name,department_id,subject_type,classes_per_week\nMATH101,Mathematics 1,1,THEORY,4\nPHYS101,Physics 1,1,LAB,3\n',
        'faculty': 'employee_id,name,department_id,max_hours_per_day,preferred_times\nF001,John Smith,1,8,9:00-11:00;2:00-4:00\nF002,Jane Doe,1,6,10:00-12:00\n',
        'classrooms': 'name,capacity,type,department_id\nA-101,60,CLASSROOM,1\nL-201,30,LAB,1\n',
        'batches': 'name,department_id,semester,strength\nCSE-A,1,1,60\nCSE-B,1,1,55\n',
        'faculty_subjects': 'faculty_id,subject_id\n1,1\n1,2\n2,3\n',
        'faculty_leaves': 'faculty_id,avg_leaves_per_month\n1,2.5\n2,1.0\n',
        'fixed_slots': 'batch_id,day,time_slot,subject_id,faculty_id,classroom_id\n1,Monday,9:00-10:00,1,1,1\n1,Wednesday,10:00-11:00,2,2,2\n'
    }
    
    if template_type in templates:
        response = make_response(templates[template_type])
        response.headers["Content-Disposition"] = f"attachment; filename={template_type}_template.csv"
        response.headers["Content-type"] = "text/csv"
        return response
    else:
        flash('Template not found!', 'error')
        return redirect(url_for('upload_csv'))

# Add this helper function to validate CSV files
def validate_csv_columns(df, required_columns):
    """Validate that CSV has required columns"""
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
    return True

# Update the process_csv_data function with validation
def process_csv_data(df, data_type):
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    success_count = 0
    
    try:
        # Define required columns for each data type
        required_columns = {
            'departments': ['code', 'name'],
            'subjects': ['code', 'name'],
            'faculty': ['employee_id', 'name'],
            'classrooms': ['name', 'capacity'],
            'batches': ['name'],
            'faculty_subjects': ['faculty_id', 'subject_id'],
            'faculty_leaves': ['faculty_id', 'avg_leaves_per_month'],
            'fixed_slots': ['batch_id', 'day', 'time_slot', 'subject_id']
        }
        
        if data_type in required_columns:
            validate_csv_columns(df, required_columns[data_type])
        
        # ... rest of the processing code remains the same
        
    except ValueError as e:
        conn.rollback()
        raise e
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
        
    return success_count

@app.route('/delete_department')
@login_required
@admin_required
def delete_department(id):
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    # Check if department has associated records
    cursor.execute('SELECT COUNT(*) FROM subjects WHERE department_id = ?', (id,))
    subject_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM faculty WHERE department_id = ?', (id,))
    faculty_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM batches WHERE department_id = ?', (id,))
    batch_count = cursor.fetchone()[0]
    
    if subject_count > 0 or faculty_count > 0 or batch_count > 0:
        flash('Cannot delete department with associated records.', 'error')
    else:
        cursor.execute('DELETE FROM departments WHERE id = ?', (id,))
        conn.commit()
        
        # Log the action
        log_audit('DELETE', 'departments', id)
        
        flash('Department deleted successfully!', 'success')
    
    conn.close()
    return redirect(url_for('departments'))

@app.route('/subjects')
@login_required
def subjects():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT s.*, d.name as department_name 
        FROM subjects s 
        LEFT JOIN departments d ON s.department_id = d.id 
        ORDER BY s.name
    ''')
    subjects = cursor.fetchall()
    
    conn.close()
    
    return render_template('subjects.html', subjects=subjects)

@app.route('/subject/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_subject():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM departments ORDER BY name')
    departments = cursor.fetchall()
    
    if request.method == 'POST':
        name = request.form['name']
        code = request.form['code']
        department_id = request.form['department_id']
        subject_type = request.form['subject_type']
        classes_per_week = request.form['classes_per_week']
        
        try:
            cursor.execute(
                "INSERT INTO subjects (name, code, department_id, subject_type, classes_per_week) VALUES (?, ?, ?, ?, ?)",
                (name, code, department_id, subject_type, classes_per_week)
            )
            conn.commit()
            
            # Log the action
            log_audit('INSERT', 'subjects', cursor.lastrowid, {
                'name': name, 
                'code': code, 
                'department_id': department_id,
                'subject_type': subject_type,
                'classes_per_week': classes_per_week
            })
            
            flash('Subject added successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('Subject code already exists.', 'error')
        finally:
            conn.close()
        
        return redirect(url_for('subjects'))
    
    conn.close()
    return render_template('add_subject.html', departments=departments)

@app.route('/edit_subject', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_subject(id):
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM subjects WHERE id = ?', (id,))
    subject = cursor.fetchone()
    
    cursor.execute('SELECT * FROM departments ORDER BY name')
    departments = cursor.fetchall()
    
    if request.method == 'POST':
        name = request.form['name']
        code = request.form['code']
        department_id = request.form['department_id']
        subject_type = request.form['subject_type']
        classes_per_week = request.form['classes_per_week']
        
        try:
            cursor.execute(
                "UPDATE subjects SET name = ?, code = ?, department_id = ?, subject_type = ?, classes_per_week = ? WHERE id = ?",
                (name, code, department_id, subject_type, classes_per_week, id)
            )
            conn.commit()
            
            # Log the action
            log_audit('UPDATE', 'subjects', id, {
                'name': name, 
                'code': code, 
                'department_id': department_id,
                'subject_type': subject_type,
                'classes_per_week': classes_per_week
            })
            
            flash('Subject updated successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('Subject code already exists.', 'error')
        finally:
            conn.close()
        
        return redirect(url_for('subjects'))
    
    conn.close()
    return render_template('edit_subject.html', subject=subject, departments=departments)

@app.route('/delete_subject', methods=['POST'])
@admin_required
def delete_subject():
    subject_id = request.form['subject_id']
    
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT name FROM subjects WHERE id = ?', (subject_id,))
        subject_name = cursor.fetchone()[0]
        
        cursor.execute('DELETE FROM subjects WHERE id = ?', (subject_id,))
        conn.commit()
        flash(f'Subject "{subject_name}" deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting subject: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('subjects'))

def get_faculty_subjects(faculty_id):
    """Helper function to get subjects taught by a faculty member"""
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT s.code, s.name 
        FROM subjects s
        JOIN faculty_subjects fs ON s.id = fs.subject_id
        WHERE fs.faculty_id = ?
        ORDER BY s.code
    ''', (faculty_id,))
    
    subjects = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return subjects
@app.route('/faculty/<int:faculty_id>/subjects')
@login_required
def faculty_subjects(faculty_id):
    """Get subjects taught by a faculty member"""
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get faculty info
    cursor.execute('SELECT * FROM faculty WHERE id = ?', (faculty_id,))
    faculty = dict(cursor.fetchone())
    
    # Get subjects taught by this faculty
    cursor.execute('''
        SELECT s.* 
        FROM subjects s
        JOIN faculty_subjects fs ON s.id = fs.subject_id
        WHERE fs.faculty_id = ?
        ORDER BY s.name
    ''', (faculty_id,))
    faculty_subjects = [dict(row) for row in cursor.fetchall()]
    
    # Get all available subjects
    cursor.execute('SELECT * FROM subjects ORDER BY name')
    all_subjects = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('faculty_subjects.html', 
                         faculty=faculty,
                         faculty_subjects=faculty_subjects,
                         all_subjects=all_subjects)

@app.route('/update_faculty_leaves', methods=['POST'])
@admin_required
def update_faculty_leaves():
    faculty_id = request.form['faculty_id']
    avg_leaves = request.form['avg_leaves_per_month']
    
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        # Check if record exists
        cursor.execute('SELECT * FROM faculty_leaves WHERE faculty_id = ?', (faculty_id,))
        if cursor.fetchone():
            cursor.execute(
                'UPDATE faculty_leaves SET avg_leaves_per_month = ? WHERE faculty_id = ?',
                (avg_leaves, faculty_id)
            )
        else:
            cursor.execute(
                'INSERT INTO faculty_leaves (faculty_id, avg_leaves_per_month) VALUES (?, ?)',
                (faculty_id, avg_leaves)
            )
        
        conn.commit()
        flash('Faculty leaves updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating leaves: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('faculty'))
# Make the function available to templates
@app.context_processor
def utility_processor():
    return dict(get_faculty_subjects=get_faculty_subjects)

@app.route('/faculty')
@login_required
def faculty():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT f.*, d.name as department_name 
        FROM faculty f 
        LEFT JOIN departments d ON f.department_id = d.id 
        ORDER BY f.name
    ''')
    faculty = cursor.fetchall()
    
    conn.close()
    
    return render_template('faculty.html', faculty=faculty)

@app.route('/faculty/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_faculty():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM departments ORDER BY name')
    departments = cursor.fetchall()
    
    cursor.execute('SELECT * FROM subjects ORDER BY name')
    subjects = cursor.fetchall()
    
    if request.method == 'POST':
        name = request.form['name']
        employee_id = request.form['employee_id']
        department_id = request.form['department_id']
        max_hours_per_day = request.form['max_hours_per_day']
        preferred_times = request.form.get('preferred_times', '')
        
        selected_subjects = request.form.getlist('subjects')
        
        try:
            cursor.execute(
                "INSERT INTO faculty (name, employee_id, department_id, max_hours_per_day, preferred_times) VALUES (?, ?, ?, ?, ?)",
                (name, employee_id, department_id, max_hours_per_day, preferred_times)
            )
            
            faculty_id = cursor.lastrowid
            
            # Add faculty subjects
            for subject_id in selected_subjects:
                cursor.execute(
                    "INSERT INTO faculty_subjects (faculty_id, subject_id) VALUES (?, ?)",
                    (faculty_id, subject_id)
                )
            
            conn.commit()
            
            # Log the action
            log_audit('INSERT', 'faculty', faculty_id, {
                'name': name, 
                'employee_id': employee_id, 
                'department_id': department_id,
                'max_hours_per_day': max_hours_per_day,
                'preferred_times': preferred_times,
                'subjects': selected_subjects
            })
            
            flash('Faculty added successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('Employee ID already exists.', 'error')
        finally:
            conn.close()
        
        return redirect(url_for('faculty'))
    
    conn.close()
    return render_template('add_faculty.html', departments=departments, subjects=subjects)

@app.route('/edit_faculty', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_faculty(id):
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM faculty WHERE id = ?', (id,))
    faculty = cursor.fetchone()
    
    cursor.execute('SELECT * FROM departments ORDER BY name')
    departments = cursor.fetchall()
    
    cursor.execute('SELECT * FROM subjects ORDER BY name')
    subjects = cursor.fetchall()
    
    cursor.execute('SELECT subject_id FROM faculty_subjects WHERE faculty_id = ?', (id,))
    faculty_subjects = [row['subject_id'] for row in cursor.fetchall()]
    
    if request.method == 'POST':
        name = request.form['name']
        employee_id = request.form['employee_id']
        department_id = request.form['department_id']
        max_hours_per_day = request.form['max_hours_per_day']
        preferred_times = request.form.get('preferred_times', '')
        
        selected_subjects = request.form.getlist('subjects')
        
        try:
            cursor.execute(
                "UPDATE faculty SET name = ?, employee_id = ?, department_id = ?, max_hours_per_day = ?, preferred_times = ? WHERE id = ?",
                (name, employee_id, department_id, max_hours_per_day, preferred_times, id)
            )
            
            # Update faculty subjects
            cursor.execute('DELETE FROM faculty_subjects WHERE faculty_id = ?', (id,))
            for subject_id in selected_subjects:
                cursor.execute(
                    "INSERT INTO faculty_subjects (faculty_id, subject_id) VALUES (?, ?)",
                    (id, subject_id)
                )
            
            conn.commit()
            
            # Log the action
            log_audit('UPDATE', 'faculty', id, {
                'name': name, 
                'employee_id': employee_id, 
                'department_id': department_id,
                'max_hours_per_day': max_hours_per_day,
                'preferred_times': preferred_times,
                'subjects': selected_subjects
            })
            
            flash('Faculty updated successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('Employee ID already exists.', 'error')
        finally:
            conn.close()
        
        return redirect(url_for('faculty'))
    
    conn.close()
    return render_template('edit_faculty.html', faculty=faculty, departments=departments, subjects=subjects, faculty_subjects=faculty_subjects)

@app.route('/delete_faculty')
@login_required
@admin_required
def delete_faculty(id):
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    # Check if faculty has associated records
    cursor.execute('SELECT COUNT(*) FROM timetable_slots WHERE faculty_id = ?', (id,))
    timetable_slot_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM faculty_subjects WHERE faculty_id = ?', (id,))
    faculty_subject_count = cursor.fetchone()[0]
    
    if timetable_slot_count > 0 or faculty_subject_count > 0:
        flash('Cannot delete faculty with associated records.', 'error')
    else:
        cursor.execute('DELETE FROM faculty WHERE id = ?', (id,))
        conn.commit()
        
        # Log the action
        log_audit('DELETE', 'faculty', id)
        
        flash('Faculty deleted successfully!', 'success')
    
    conn.close()
    return redirect(url_for('faculty'))

@app.route('/classrooms')
@login_required
def classrooms():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT c.*, d.name as department_name 
        FROM classrooms c 
        LEFT JOIN departments d ON c.department_id = d.id 
        ORDER BY c.name
    ''')
    classrooms = cursor.fetchall()
    
    conn.close()
    
    return render_template('classrooms.html', classrooms=classrooms)

@app.route('/classroom/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_classroom():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM departments ORDER BY name')
    departments = cursor.fetchall()
    
    if request.method == 'POST':
        name = request.form['name']
        capacity = request.form['capacity']
        classroom_type = request.form['type']
        department_id = request.form['department_id']
        
        try:
            cursor.execute(
                "INSERT INTO classrooms (name, capacity, type, department_id) VALUES (?, ?, ?, ?)",
                (name, capacity, classroom_type, department_id)
            )
            conn.commit()
            
            # Log the action
            log_audit('INSERT', 'classrooms', cursor.lastrowid, {
                'name': name, 
                'capacity': capacity, 
                'type': classroom_type,
                'department_id': department_id
            })
            
            flash('Classroom added successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('Classroom name already exists.', 'error')
        finally:
            conn.close()
        
        return redirect(url_for('classrooms'))
    
    conn.close()
    return render_template('add_classroom.html', departments=departments)

@app.route('/edit_classroom', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_classroom(id):
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM classrooms WHERE id = ?', (id,))
    classroom = cursor.fetchone()
    
    cursor.execute('SELECT * FROM departments ORDER BY name')
    departments = cursor.fetchall()
    
    if request.method == 'POST':
        name = request.form['name']
        capacity = request.form['capacity']
        classroom_type = request.form['type']
        department_id = request.form['department_id']
        
        try:
            cursor.execute(
                "UPDATE classrooms SET name = ?, capacity = ?, type = ?, department_id = ? WHERE id = ?",
                (name, capacity, classroom_type, department_id, id)
            )
            conn.commit()
            
            # Log the action
            log_audit('UPDATE', 'classrooms', id, {
                'name': name, 
                'capacity': capacity, 
                'type': classroom_type,
                'department_id': department_id
            })
            
            flash('Classroom updated successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('Classroom name already exists.', 'error')
        finally:
            conn.close()
        
        return redirect(url_for('classrooms'))
    
    conn.close()
    return render_template('edit_classroom.html', classroom=classroom, departments=departments)

@app.route('/delete_classroom')
@login_required
@admin_required
def delete_classroom(id):
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    # Check if classroom has associated records
    cursor.execute('SELECT COUNT(*) FROM timetable_slots WHERE classroom_id = ?', (id,))
    timetable_slot_count = cursor.fetchone()[0]
    
    if timetable_slot_count > 0:
        flash('Cannot delete classroom with associated records.', 'error')
    else:
        cursor.execute('DELETE FROM classrooms WHERE id = ?', (id,))
        conn.commit()
        
        # Log the action
        log_audit('DELETE', 'classrooms', id)
        
        flash('Classroom deleted successfully!', 'success')
    
    conn.close()
    return redirect(url_for('classrooms'))

@app.route('/batches')
@login_required
def batches():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT b.*, d.name as department_name 
        FROM batches b 
        LEFT JOIN departments d ON b.department_id = d.id 
        ORDER BY b.semester, b.name
    ''')
    batches = cursor.fetchall()
    
    conn.close()
    
    return render_template('batches.html', batches=batches)

@app.route('/batch/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_batch():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM departments ORDER BY name')
    departments = cursor.fetchall()
    
    if request.method == 'POST':
        name = request.form['name']
        department_id = request.form['department_id']
        semester = request.form['semester']
        strength = request.form['strength']
        
        try:
            cursor.execute(
                "INSERT INTO batches (name, department_id, semester, strength) VALUES (?, ?, ?, ?)",
                (name, department_id, semester, strength)
            )
            conn.commit()
            
            # Log the action
            log_audit('INSERT', 'batches', cursor.lastrowid, {
                'name': name, 
                'department_id': department_id, 
                'semester': semester,
                'strength': strength
            })
            
            flash('Batch added successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('Batch name already exists for this department and semester.', 'error')
        finally:
            conn.close()
        
        return redirect(url_for('batches'))
    
    conn.close()
    return render_template('add_batch.html', departments=departments)

@app.route('/edit_batch', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_batch(id):
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM batches WHERE id = ?', (id,))
    batch = cursor.fetchone()
    
    cursor.execute('SELECT * FROM departments ORDER BY name')
    departments = cursor.fetchall()
    
    if request.method == 'POST':
        name = request.form['name']
        department_id = request.form['department_id']
        semester = request.form['semester']
        strength = request.form['strength']
        
        try:
            cursor.execute(
                "UPDATE batches SET name = ?, department_id = ?, semester = ?, strength = ? WHERE id = ?",
                (name, department_id, semester, strength, id)
            )
            conn.commit()
            
            # Log the action
            log_audit('UPDATE', 'batches', id, {
                'name': name, 
                'department_id': department_id, 
                'semester': semester,
                'strength': strength
            })
            
            flash('Batch updated successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('Batch name already exists for this department and semester.', 'error')
        finally:
            conn.close()
        
        return redirect(url_for('batches'))
    
    conn.close()
    return render_template('edit_batch.html', batch=batch, departments=departments)

@app.route('/delete_batch')
@login_required
@admin_required
def delete_batch(id):
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    # Check if batch has associated records
    cursor.execute('SELECT COUNT(*) FROM timetable_slots WHERE batch_id = ?', (id,))
    timetable_slot_count = cursor.fetchone()[0]
    
    if timetable_slot_count > 0:
        flash('Cannot delete batch with associated records.', 'error')
    else:
        cursor.execute('DELETE FROM batches WHERE id = ?', (id,))
        conn.commit()
        
        # Log the action
        log_audit('DELETE', 'batches', id)
        
        flash('Batch deleted successfully!', 'success')
    
    conn.close()
    return redirect(url_for('batches'))


@app.route('/exams')
@login_required
def exams():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT e.*, d.name as department_name, s.name as subject_name, 
               c.name as classroom_name, u.full_name as created_by_name
        FROM exams e
        LEFT JOIN departments d ON e.department_id = d.id
        LEFT JOIN subjects s ON e.subject_id = s.id
        LEFT JOIN classrooms c ON e.classroom_id = c.id
        LEFT JOIN users u ON e.created_by = u.id
        ORDER BY e.exam_date, e.start_time
    ''')
    exams = cursor.fetchall()
    
    conn.close()
    
    return render_template('exams.html', exams=exams)

@app.route('/exam/add', methods=['GET', 'POST'])
@login_required
def add_exam():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM departments ORDER BY name')
    departments = cursor.fetchall()
    
    cursor.execute('SELECT * FROM subjects ORDER BY name')
    subjects = cursor.fetchall()
    
    cursor.execute('SELECT * FROM classrooms ORDER BY name')
    classrooms = cursor.fetchall()
    
    if request.method == 'POST':
        name = request.form['name']
        department_id = request.form['department_id']
        semester = request.form['semester']
        subject_id = request.form['subject_id']
        exam_date = request.form['exam_date']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        classroom_id = request.form['classroom_id']
        
        try:
            cursor.execute(
                "INSERT INTO exams (name, department_id, semester, subject_id, exam_date, start_time, end_time, classroom_id, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (name, department_id, semester, subject_id, exam_date, start_time, end_time, classroom_id, session['user_id'])
            )
            conn.commit()
            
            # Log the action
            log_audit('INSERT', 'exams', cursor.lastrowid, {
                'name': name, 
                'department_id': department_id, 
                'semester': semester,
                'subject_id': subject_id,
                'exam_date': exam_date,
                'start_time': start_time,
                'end_time': end_time,
                'classroom_id': classroom_id
            })
            
            flash('Exam scheduled successfully!', 'success')
        except Exception as e:
            flash(f'Error scheduling exam: {str(e)}', 'error')
        finally:
            conn.close()
        
        return redirect(url_for('exams'))
    
    conn.close()
    return render_template('add_exam.html', departments=departments, subjects=subjects, classrooms=classrooms)

@app.route('/timetable/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_timetable(id):
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Fetch timetable details
    cursor.execute('SELECT * FROM timetables WHERE id = ?', (id,))
    timetable = cursor.fetchone()

    if not timetable:
        flash('Timetable not found.', 'error')
        conn.close()
        return redirect(url_for('timetables'))

    # Fetch all batches, subjects, faculty, and classrooms to populate dropdowns
    cursor.execute('SELECT * FROM batches WHERE department_id = ? AND semester = ?', (timetable['department_id'], timetable['semester']))
    batches = cursor.fetchall()

    cursor.execute('SELECT * FROM subjects WHERE department_id = ?', (timetable['department_id'],))
    subjects = cursor.fetchall()
    
    cursor.execute('SELECT * FROM faculty WHERE department_id = ?', (timetable['department_id'],))
    faculty = cursor.fetchall()

    cursor.execute('SELECT * FROM classrooms WHERE department_id = ?', (timetable['department_id'],))
    classrooms = cursor.fetchall()

    if request.method == 'POST':
        # Get data from the submitted form
        timetable_name = request.form['name']
        
        # Delete existing slots for this timetable
        cursor.execute('DELETE FROM timetable_slots WHERE timetable_id = ?', (id,))

        # Process the new slots from the form
        slots = json.loads(request.form.get('slots_json', '[]'))
        for slot in slots:
            cursor.execute(
                "INSERT INTO timetable_slots (timetable_id, batch_id, day, time_slot, subject_id, faculty_id, classroom_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (id, slot['batch_id'], slot['day'], slot['time_slot'], slot['subject_id'], slot['faculty_id'], slot['classroom_id'])
            )
        
        # Update the timetable's name
        cursor.execute('UPDATE timetables SET name = ? WHERE id = ?', (timetable_name, id))
        conn.commit()
        conn.close()
        
        flash('Timetable updated successfully!', 'success')
        return redirect(url_for('view_timetable', id=id))

    # For GET request, fetch existing timetable slots
    cursor.execute('''
        SELECT ts.*, b.name as batch_name, s.name as subject_name,
        f.name as faculty_name, c.name as classroom_name
        FROM timetable_slots ts
        LEFT JOIN batches b ON ts.batch_id = b.id
        LEFT JOIN subjects s ON ts.subject_id = s.id
        LEFT JOIN faculty f ON ts.faculty_id = f.id
        LEFT JOIN classrooms c ON ts.classroom_id = c.id
        WHERE ts.timetable_id = ?
        ORDER BY ts.batch_id, ts.day, ts.time_slot
    ''', (id,))
    slots = cursor.fetchall()

    organized_slots = {}
    for slot in slots:
        batch_id = slot['batch_id']
        day = slot['day']
        if batch_id not in organized_slots:
            organized_slots[batch_id] = {
                'batch_name': slot['batch_name'],
                'days': {}
            }
        if day not in organized_slots[batch_id]['days']:
            organized_slots[batch_id]['days'][day] = []
        organized_slots[batch_id]['days'][day].append(slot)
    
    conn.close()

    time_slots = ['9:00-10:00', '10:00-11:00', '11:00-12:00', '12:00-1:00', 
                    '2:00-3:00', '3:00-4:00', '4:00-5:00']
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

    return render_template('edit_timetable.html',
                           timetable=timetable,
                           batches=batches,
                           subjects=subjects,
                           faculty=faculty,
                           classrooms=classrooms,
                           organized_slots=organized_slots,
                           time_slots=time_slots,
                           days=days)

@app.route('/exam/delete/<int:id>')
@login_required
def delete_exam(id):
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM exams WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    # Log the action
    log_audit('DELETE', 'exams', id)
    
    flash('Exam deleted successfully!', 'success')
    return redirect(url_for('exams'))

@app.route('/events')
@login_required
def events():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT e.*, u.full_name as created_by_name
        FROM events e
        LEFT JOIN users u ON e.created_by = u.id
        ORDER BY e.event_date, e.start_time
    ''')
    events = cursor.fetchall()
    
    conn.close()
    
    return render_template('events.html', events=events)

@app.route('/event/add', methods=['GET', 'POST'])
@login_required
def add_event():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        event_date = request.form['event_date']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        location = request.form['location']
        
        conn = sqlite3.connect('timetable.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO events (title, description, event_date, start_time, end_time, location, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (title, description, event_date, start_time, end_time, location, session['user_id'])
            )
            conn.commit()
            
            # Log the action
            log_audit('INSERT', 'events', cursor.lastrowid, {
                'title': title, 
                'description': description, 
                'event_date': event_date,
                'start_time': start_time,
                'end_time': end_time,
                'location': location
            })
            
            flash('Event added successfully!', 'success')
        except Exception as e:
            flash(f'Error adding event: {str(e)}', 'error')
        finally:
            conn.close()
        
        return redirect(url_for('events'))
    
    return render_template('add_event.html')

@app.route('/event/delete/<int:id>')
@login_required
def delete_event(id):
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM events WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    # Log the action
    log_audit('DELETE', 'events', id)
    
    flash('Event deleted successfully!', 'success')
    return redirect(url_for('events'))



@app.route('/notifications')
@login_required
def notifications():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM notifications 
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (session['user_id'],))
    notifications = cursor.fetchall()
    
    # Mark all as read
    cursor.execute('UPDATE notifications SET is_read = 1 WHERE user_id = ?', (session['user_id'],))
    conn.commit()
    conn.close()
    
    return render_template('notifications.html', notifications=notifications)

@app.route('/notifications/clear')
@login_required
def clear_notifications():
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM notifications WHERE user_id = ?', (session['user_id'],))
    conn.commit()
    conn.close()
    
    flash('Notifications cleared successfully!', 'success')
    return redirect(url_for('notifications'))

@app.route('/profile')
@login_required
def profile():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    cursor.execute('SELECT * FROM departments WHERE id = ?', (user['department_id'],))
    department = cursor.fetchone()
    
    conn.close()
    
    return render_template('profile.html', user=user, department=department)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    cursor.execute('SELECT * FROM departments ORDER BY name')
    departments = cursor.fetchall()
    
    if request.method == 'POST':
        full_name = request.form['full_name']
        department_id = request.form['department_id']
        
        cursor.execute(
            "UPDATE users SET full_name = ?, department_id = ? WHERE id = ?",
            (full_name, department_id, session['user_id'])
        )
        conn.commit()
        
        # Update session
        session['full_name'] = full_name
        
        # Log the action
        log_audit('UPDATE', 'users', session['user_id'], {
            'full_name': full_name, 
            'department_id': department_id
        })
        
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    conn.close()
    return render_template('edit_profile.html', user=user, departments=departments)

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('change_password'))
        
        conn = sqlite3.connect('timetable.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
        user = cursor.fetchone()
        
        if not check_password_hash(user['password'], current_password):
            flash('Current password is incorrect.', 'error')
            conn.close()
            return redirect(url_for('change_password'))
        
        hashed_password = generate_password_hash(new_password)
        cursor.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (hashed_password, session['user_id'])
        )
        conn.commit()
        conn.close()
        
        # Log the action
        log_audit('UPDATE', 'users', session['user_id'], {'password': 'changed'})
        
        flash('Password changed successfully!', 'success')
        return redirect(url_for('profile'))
    
    return render_template('change_password.html')

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@app.route('/export/reports')
@login_required
def export_reports():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get department statistics
    cursor.execute('''
        SELECT d.name as department_name, 
               COUNT(DISTINCT s.id) as subject_count,
               COUNT(DISTINCT f.id) as faculty_count,
               COUNT(DISTINCT b.id) as batch_count,
               COUNT(DISTINCT t.id) as timetable_count
        FROM departments d
        LEFT JOIN subjects s ON d.id = s.department_id
        LEFT JOIN faculty f ON d.id = f.department_id
        LEFT JOIN batches b ON d.id = b.department_id
        LEFT JOIN timetables t ON d.id = t.department_id
        GROUP BY d.id
        ORDER BY d.name
    ''')
    department_stats = cursor.fetchall()
    
    # Create CSV content
    csv_content = "Department Reports\n\n"
    csv_content += "Department Statistics\n"
    csv_content += "Department,Subjects,Faculty,Batches,Timetables\n"
    for dept in department_stats:
        csv_content += f"{dept['department_name']},{dept['subject_count']},{dept['faculty_count']},{dept['batch_count']},{dept['timetable_count']}\n"
    
    csv_content += "\nGenerated on: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n"
    
    conn.close()
    
    # Create response
    response = make_response(csv_content)
    response.headers['Content-Disposition'] = 'attachment; filename=reports_export.csv'
    response.headers['Content-type'] = 'text/csv'
    
    return response

@app.route('/reports')
@login_required
def reports():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get department statistics
    cursor.execute('''
        SELECT d.name as department_name, 
               COUNT(DISTINCT s.id) as subject_count,
               COUNT(DISTINCT f.id) as faculty_count,
               COUNT(DISTINCT b.id) as batch_count,
               COUNT(DISTINCT t.id) as timetable_count
        FROM departments d
        LEFT JOIN subjects s ON d.id = s.department_id
        LEFT JOIN faculty f ON d.id = f.department_id
        LEFT JOIN batches b ON d.id = b.department_id
        LEFT JOIN timetables t ON d.id = t.department_id
        GROUP BY d.id
        ORDER BY d.name
    ''')
    department_stats = cursor.fetchall()
    
    # Get faculty workload statistics
    cursor.execute('''
        SELECT f.name as faculty_name, 
               d.name as department_name,
               COUNT(DISTINCT fs.subject_id) as subjects_assigned,
               COUNT(ts.id) as classes_per_week
        FROM faculty f
        LEFT JOIN departments d ON f.department_id = d.id
        LEFT JOIN faculty_subjects fs ON f.id = fs.faculty_id
        LEFT JOIN timetable_slots ts ON f.id = ts.faculty_id
        GROUP BY f.id
        ORDER BY d.name, f.name
    ''')
    faculty_stats = cursor.fetchall()
    
    # Get classroom utilization
    cursor.execute('''
        SELECT c.name as classroom_name, 
               d.name as department_name,
               COUNT(ts.id) as classes_per_week
        FROM classrooms c
        LEFT JOIN departments d ON c.department_id = d.id
        LEFT JOIN timetable_slots ts ON c.id = ts.classroom_id
        GROUP BY c.id
        ORDER BY d.name, c.name
    ''')
    classroom_stats = cursor.fetchall()
    
    # Get attendance statistics
    cursor.execute('''
        SELECT date, 
               COUNT(*) as total_classes,
               SUM(CASE WHEN status = 'PRESENT' THEN 1 ELSE 0 END) as present_classes,
               ROUND(SUM(CASE WHEN status = 'PRESENT' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as attendance_percentage
        FROM attendance
        GROUP BY date
        ORDER BY date DESC
        LIMIT 30
    ''')
    attendance_stats = cursor.fetchall()
    
    conn.close()
    
    return render_template('reports.html', 
                         department_stats=department_stats,
                         faculty_stats=faculty_stats,
                         classroom_stats=classroom_stats,
                         attendance_stats=attendance_stats)


# @app.route('/users')
@app.route('/user_management')
@login_required
@admin_required
def users():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT u.*, d.name as department_name 
        FROM users u 
        LEFT JOIN departments d ON u.department_id = d.id 
        ORDER BY u.username
    ''')
    users = cursor.fetchall()
    
    conn.close()
    
    return render_template('user_management.html', users=users)

# @app.route('/user/add', methods=['GET', 'POST'])
# @login_required
# @admin_required
# def add_user():
#     conn = sqlite3.connect('timetable.db')
#     conn.row_factory = sqlite3.Row
#     cursor = conn.cursor()
    
#     cursor.execute('SELECT * FROM departments ORDER BY name')
#     departments = cursor.fetchall()
    
#     if request.method == 'POST':
#         username = request.form['username']
#         password = request.form['password']
#         full_name = request.form['full_name']
#         role = request.form['role']
#         department_id = request.form['department_id']
        
#         hashed_password = generate_password_hash(password)
        
#         try:
#             cursor.execute(
#                 "INSERT INTO users (username, password, full_name, role, department_id) VALUES (?, ?, ?, ?, ?)",
#                 (username, hashed_password, full_name, role, department_id)
#             )
#             conn.commit()
            
#             # Log the action
#             log_audit('INSERT', 'users', cursor.lastrowid, {
#                 'username': username, 
#                 'full_name': full_name, 
#                 'role': role,
#                 'department_id': department_id
#             })
            
#             flash('User added successfully!', 'success')
#         except sqlite3.IntegrityError:
#             flash('Username already exists.', 'error')
#         finally:
#             conn.close()
        
#         return redirect(url_for('users'))
    
#     conn.close()
#     return render_template('add_user.html', departments=departments)

# @app.route('/user/edit/<int:id>', methods=['GET', 'POST'])
# @login_required
# @admin_required
# def edit_user(id):
#     conn = sqlite3.connect('timetable.db')
#     conn.row_factory = sqlite3.Row
#     cursor = conn.cursor()
    
#     cursor.execute('SELECT * FROM users WHERE id = ?', (id,))
#     user = cursor.fetchone()
    
#     cursor.execute('SELECT * FROM departments ORDER BY name')
#     departments = cursor.fetchall()
    
#     if request.method == 'POST':
#         username = request.form['username']
#         full_name = request.form['full_name']
#         role = request.form['role']
#         department_id = request.form['department_id']
        
#         try:
#             cursor.execute(
#                 "UPDATE users SET username = ?, full_name = ?, role = ?, department_id = ? WHERE id = ?",
#                 (username, full_name, role, department_id, id)
#             )
#             conn.commit()
            
#             # Log the action
#             log_audit('UPDATE', 'users', id, {
#                 'username': username, 
#                 'full_name': full_name, 
#                 'role': role,
#                 'department_id': department_id
#             })
            
#             flash('User updated successfully!', 'success')
#         except sqlite3.IntegrityError:
#             flash('Username already exists.', 'error')
#         finally:
#             conn.close()
        
#         return redirect(url_for('users'))
    
#     conn.close()
#     return render_template('edit_user.html', user=user, departments=departments)

# @app.route('/user/delete/<int:id>')
# @login_required
# @admin_required
# def delete_user(id):
#     if id == session['user_id']:
#         flash('You cannot delete your own account.', 'error')
#         return redirect(url_for('users'))
    
#     conn = sqlite3.connect('timetable.db')
#     cursor = conn.cursor()
    
#     cursor.execute('DELETE FROM users WHERE id = ?', (id,))
#     conn.commit()
#     conn.close()
    
#     # Log the action
#     log_audit('DELETE', 'users', id)
    
#     flash('User deleted successfully!', 'success')
#     return redirect(url_for('users'))

@app.route('/audit_logs')
@login_required
@admin_required
def audit_logs():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT a.*, u.username 
        FROM audit_logs a 
        LEFT JOIN users u ON a.user_id = u.id 
        ORDER BY a.created_at DESC
        LIMIT 100
    ''')
    logs = cursor.fetchall()
    
    conn.close()
    
    return render_template('audit_logs.html', logs=logs)

@app.route('/api/timetable/<int:department_id>/<int:semester>')
@login_required
def api_timetable(department_id, semester):
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get the latest timetable for the department and semester
    cursor.execute('''
        SELECT t.* FROM timetables t 
        WHERE t.department_id = ? AND t.semester = ?
        ORDER BY t.created_at DESC 
        LIMIT 1
    ''', (department_id, semester))
    
    timetable = cursor.fetchone()
    
    # if not timetable:
    #     return jsonify({'error': 'Timetable not found'}), 404
    
    # Get timetable slots
    cursor.execute('''
        SELECT ts.*, b.name as batch_name, s.name as subject_name, 
               f.name as faculty_name, c.name as classroom_name
        FROM timetable_slots ts
        LEFT JOIN batches b ON ts.batch_id = b.id
        LEFT JOIN subjects s ON ts.subject_id = s.id
        LEFT JOIN faculty f ON ts.faculty_id = f.id
        LEFT JOIN classrooms c ON ts.classroom_id = c.id
        WHERE ts.timetable_id = ?
        ORDER BY ts.batch_id, ts.day, ts.time_slot
    ''', (timetable['id'],))
    
    slots = cursor.fetchall()
    
    # Organize data for JSON response
    result = {
        'timetable_id': timetable['id'],
        'timetable_name': timetable['name'],
        'department_id': timetable['department_id'],
        'semester': timetable['semester'],
        'fitness_score': timetable['fitness_score'],
        'created_at': timetable['created_at'],
        'slots': []
    }
    
    for slot in slots:
        result['slots'].append({
            'batch_id': slot['batch_id'],
            'batch_name': slot['batch_name'],
            'day': slot['day'],
            'time_slot': slot['time_slot'],
            'subject_id': slot['subject_id'],
            'subject_name': slot['subject_name'],
            'faculty_id': slot['faculty_id'],
            'faculty_name': slot['faculty_name'],
            'classroom_id': slot['classroom_id'],
            'classroom_name': slot['classroom_name']
        })
    
    conn.close()
    return jsonify(result)

@app.route('/api/events')
@login_required
def api_events():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM events 
        WHERE event_date >= date('now')
        ORDER BY event_date, start_time
    ''')
    
    events = cursor.fetchall()
    
    result = []
    for event in events:
        result.append({
            'id': event['id'],
            'title': event['title'],
            'description': event['description'],
            'event_date': event['event_date'],
            'start_time': event['start_time'],
            'end_time': event['end_time'],
            'location': event['location'],
            'created_at': event['created_at']
        })
    
    conn.close()
    return jsonify(result)

@app.route('/api/exams')
@login_required
def api_exams():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT e.*, d.name as department_name, s.name as subject_name, 
               c.name as classroom_name
        FROM exams e
        LEFT JOIN departments d ON e.department_id = d.id
        LEFT JOIN subjects s ON e.subject_id = s.id
        LEFT JOIN classrooms c ON e.classroom_id = c.id
        WHERE e.exam_date >= date('now')
        ORDER BY e.exam_date, e.start_time
    ''')
    
    exams = cursor.fetchall()
    
    result = []
    for exam in exams:
        result.append({
            'id': exam['id'],
            'name': exam['name'],
            'department_id': exam['department_id'],
            'department_name': exam['department_name'],
            'semester': exam['semester'],
            'subject_id': exam['subject_id'],
            'subject_name': exam['subject_name'],
            'exam_date': exam['exam_date'],
            'start_time': exam['start_time'],
            'end_time': exam['end_time'],
            'classroom_id': exam['classroom_id'],
            'classroom_name': exam['classroom_name'],
            'created_at': exam['created_at']
        })
    
    conn.close()
    return jsonify(result)

# Error handlers
# @app.errorhandler(404)
# def not_found_error(error):
#     return render_template('404.html'), 404

# @app.errorhandler(500)
# def internal_error(error):
#     return render_template('500.html'), 500

@app.route('/upload_csv', methods=['GET', 'POST'])
@admin_required
def upload_csv():
    if request.method == 'POST':
        file = request.files.get('csv_file')
        data_type = request.form.get('data_type')
        
        if file and file.filename.endswith('.csv'):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                df = pd.read_csv(filepath)
                success_count = process_csv_data(df, data_type)
                flash(f'Successfully imported {success_count} records from CSV.', 'success')
            except Exception as e:
                flash(f'Error processing CSV: {str(e)}', 'error')
            finally:
                if os.path.exists(filepath):
                    os.remove(filepath)
        else:
            flash('Please select a valid CSV file.', 'error')
    
    return render_template('upload_csv.html')

def process_csv_data(df, data_type):
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    success_count = 0
    
    try:
        if data_type == 'subjects':
            for _, row in df.iterrows():
                cursor.execute('''
                    INSERT OR IGNORE INTO subjects (name, code, department_id, subject_type, classes_per_week)
                    VALUES (?, ?, ?, ?, ?)
                ''', (row['name'], row['code'], row.get('department_id', 1), 
                     row.get('subject_type', 'THEORY'), row.get('classes_per_week', 3)))
                success_count += 1
                
        elif data_type == 'faculty':
            for _, row in df.iterrows():
                cursor.execute('''
                    INSERT OR IGNORE INTO faculty (name, employee_id, department_id, max_hours_per_day, preferred_times)
                    VALUES (?, ?, ?, ?, ?)
                ''', (row['name'], row['employee_id'], row.get('department_id', 1),
                     row.get('max_hours_per_day', 8), row.get('preferred_times', '')))
                success_count += 1
                
        elif data_type == 'classrooms':
            for _, row in df.iterrows():
                cursor.execute('''
                    INSERT OR IGNORE INTO classrooms (name, capacity, type, department_id)
                    VALUES (?, ?, ?, ?)
                ''', (row['name'], row['capacity'], row.get('type', 'CLASSROOM'), 
                     row.get('department_id', 1)))
                success_count += 1
                
        elif data_type == 'batches':
            for _, row in df.iterrows():
                cursor.execute('''
                    INSERT OR IGNORE INTO batches (name, department_id, semester, strength)
                    VALUES (?, ?, ?, ?)
                ''', (row['name'], row.get('department_id', 1), row.get('semester', 1), 
                     row.get('strength', 60)))
                success_count += 1
                
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
        
    return success_count

@app.route('/api/get-faculty-classes', methods=['GET'])
@faculty_required
def get_faculty_classes():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get the batches and subjects associated with the current faculty member's department
    # Note: We'll assume the faculty ID is stored in the session as 'teacher_id'
    faculty_id = session.get('teacher_id')

    if not faculty_id:
        return jsonify({'error': 'Faculty ID not found in session'}), 401

    # Fetch batches for the faculty member's department
    cursor.execute('''
        SELECT * from batches 
    ''')
    batches = cursor.fetchall()
    print(batches)
    # Fetch subjects assigned to the faculty member
    cursor.execute('''
        SELECT * FROM subjects 
    ''')
    subjects = cursor.fetchall()
    print(subjects)
    conn.close()

    return jsonify({
        'batches': [dict(row) for row in batches],
        'subjects': [dict(row) for row in subjects]
    })


if __name__ == '__main__':
    # Create upload directory if it doesn't exist
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    # Initialize database
    init_db()
    
    app.run(debug=True, host='0.0.0.0', port=5000, ssl_context='adhoc')
