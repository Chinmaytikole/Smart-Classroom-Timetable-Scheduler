# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
import sqlite3
import os
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import json
from datetime import datetime
from genetic_algorithm import EnhancedGeneticTimetable

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this in production
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Database initialization
def init_db():
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT,
            role TEXT DEFAULT 'user',
            department_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
    # Add faculty_leaves table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS faculty_leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            faculty_id INTEGER NOT NULL,
            avg_leaves_per_month REAL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (faculty_id) REFERENCES faculty (id)
        )
    ''')

    
    # Create default admin user if not exists
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if cursor.fetchone()[0] == 0:
        hashed_password = generate_password_hash('admin123')
        cursor.execute(
            "INSERT INTO users (username, password, full_name, role) VALUES (?, ?, ?, ?)",
            ('admin', hashed_password, 'Administrator', 'admin')
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

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
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
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
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
    
    # Get recent timetables
    cursor.execute('''
        SELECT t.*, d.name as department_name 
        FROM timetables t 
        LEFT JOIN departments d ON t.department_id = d.id 
        ORDER BY t.created_at DESC 
        LIMIT 5
    ''')
    recent_timetables = cursor.fetchall()
    
    conn.close()
    
    stats = {
        'departments': dept_count,
        'subjects': sub_count,
        'faculty': faculty_count,
        'timetables': timetable_count
    }
    
    return render_template('dashboard.html', stats=stats, recent_timetables=recent_timetables)

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

@app.route('/timetables')
@login_required
def timetables():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT t.*, d.name as department_name, u.full_name as generated_by_name
        FROM timetables t 
        LEFT JOIN departments d ON t.department_id = d.id 
        LEFT JOIN users u ON t.generated_by = u.id
        ORDER BY t.created_at DESC
    ''')
    timetables = cursor.fetchall()
    
    conn.close()
    return render_template('timetables.html', timetables=timetables)

@app.route('/generate_timetable')
@login_required
def generate_timetable():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM departments ORDER BY name')
    departments = cursor.fetchall()
    
    conn.close()
    return render_template('generate_timetable.html', departments=departments)

@app.route('/generate_timetable_process', methods=['POST'])
@login_required
def generate_timetable_process():
    name = request.form['name']
    department_id = request.form['department_id']
    semester = request.form['semester']
    
    print(f"Generating timetable: {name}, Dept: {department_id}, Semester: {semester}")
    
    # Get all necessary data for genetic algorithm
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get subjects for the department and semester
    cursor.execute('SELECT * FROM subjects WHERE department_id = ?', (department_id,))
    subjects = [dict(row) for row in cursor.fetchall()]
    print(f"Found {len(subjects)} subjects")
    
    # Get faculty for the department
    cursor.execute('SELECT * FROM faculty WHERE department_id = ?', (department_id,))
    faculty = [dict(row) for row in cursor.fetchall()]
    print(f"Found {len(faculty)} faculty members")
    
    # Get classrooms
    cursor.execute('SELECT * FROM classrooms WHERE department_id = ?', (department_id,))
    classrooms = [dict(row) for row in cursor.fetchall()]
    print(f"Found {len(classrooms)} classrooms")
    
    # Get batches for the department and semester
    cursor.execute('SELECT * FROM batches WHERE department_id = ? AND semester = ?', (department_id, semester))
    batches = [dict(row) for row in cursor.fetchall()]
    print(f"Found {len(batches)} batches")
    
    if not subjects or not faculty or not classrooms or not batches:
        flash('Insufficient data for timetable generation. Please ensure you have subjects, faculty, classrooms, and batches defined.', 'error')
        conn.close()
        return redirect(url_for('generate_timetable'))
    
    # Define constraints
    constraints = {
    'days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
    'time_slots': ['9:00-10:00', '10:00-11:00', '11:00-12:00', '12:00-1:00', '1:00-2:00', '2:00-3:00', '3:00-4:00', '4:00-5:00'],
    'lunch_break': '12:00-1:00',
    'max_classes_per_day_per_batch': 6,  # Maximum classes per day per batch
    'max_hours_per_faculty': 8,
    'fixed_slots': get_fixed_slots()  # You'll need to implement this
}
    def get_fixed_slots(self):
        """Get fixed slots from database"""
        conn = sqlite3.connect('timetable.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT batch_id, day, time_slot, subject_id, faculty_id, classroom_id
            FROM fixed_slots
        ''')
        
        fixed_slots = []
        for row in cursor.fetchall():
            fixed_slots.append({
                'batch_id': row[0],
                'day': row[1],
                'time_slot': row[2],
                'subject_id': row[3],
                'faculty_id': row[4],
                'classroom_id': row[5]
            })
        
        conn.close()
        return fixed_slots
    try:
        # Initialize and run genetic algorithm
        genetic_timetable = EnhancedGeneticTimetable(subjects, faculty, classrooms, batches, constraints)
        best_timetable, fitness_score = genetic_timetable.run()
        
        print(f"Genetic algorithm completed. Fitness score: {fitness_score}")
        print(f"Best timetable structure: {list(best_timetable.keys()) if best_timetable else 'Empty'}")
        
        # Save the timetable to database
        cursor.execute(
            'INSERT INTO timetables (name, department_id, semester, fitness_score, generated_by) VALUES (?, ?, ?, ?, ?)',
            (name, department_id, semester, fitness_score, session['user_id'])
        )
        timetable_id = cursor.lastrowid
        print(f"Created timetable record with ID: {timetable_id}")
        
        # Save timetable slots
        slot_count = 0
        for batch_id, schedule in best_timetable.items():
            for day, time_slots in schedule.items():
                for time_slot, slot_data in time_slots.items():
                    if slot_data:  # If there's a class scheduled
                        cursor.execute(
                            '''INSERT INTO timetable_slots 
                            (timetable_id, batch_id, day, time_slot, subject_id, faculty_id, classroom_id) 
                            VALUES (?, ?, ?, ?, ?, ?, ?)''',
                            (timetable_id, batch_id, day, time_slot, 
                             slot_data['subject_id'], slot_data['faculty_id'], slot_data['classroom_id'])
                        )
                        slot_count += 1
        
        conn.commit()
        print(f"Saved {slot_count} timetable slots")
        
        flash(f'Timetable generated successfully with fitness score: {fitness_score:.2f}', 'success')
        return redirect(url_for('view_timetable', timetable_id=timetable_id))
        
    except Exception as e:
        conn.rollback()
        print(f"Error generating timetable: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Error generating timetable: {str(e)}', 'error')
        return redirect(url_for('generate_timetable'))
    finally:
        conn.close()

@app.route('/timetable/<int:timetable_id>')
@login_required
def view_timetable(timetable_id):
    print(f"Viewing timetable ID: {timetable_id}")
    try:
        conn = sqlite3.connect('timetable.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get timetable info
        cursor.execute('''
            SELECT t.*, d.name as department_name 
            FROM timetables t 
            LEFT JOIN departments d ON t.department_id = d.id 
            WHERE t.id = ?
        ''', (timetable_id,))
        
        timetable_row = cursor.fetchone()
        if not timetable_row:
            flash('Timetable not found!', 'error')
            return redirect(url_for('timetables'))
        
        timetable_info = dict(timetable_row)
        print(f"Timetable info: {timetable_info}")

        # Get timetable slots
        cursor.execute('''
            SELECT ts.*, s.name as subject_name, s.code as subject_code, 
                   f.name as faculty_name, c.name as classroom_name,
                   b.name as batch_name, b.id as batch_id
            FROM timetable_slots ts
            LEFT JOIN subjects s ON ts.subject_id = s.id
            LEFT JOIN faculty f ON ts.faculty_id = f.id
            LEFT JOIN classrooms c ON ts.classroom_id = c.id
            LEFT JOIN batches b ON ts.batch_id = b.id
            WHERE ts.timetable_id = ?
            ORDER BY b.name, ts.day, ts.time_slot
        ''', (timetable_id,))
        
        slots = cursor.fetchall()
        print(f"Fetched {len(slots)} timetable slots")

        # Organize slots by batch and day/time
        organized_slots = {}
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        time_slots = ['9:00-10:00', '10:00-11:00', '11:00-12:00', '12:00-1:00', '1:00-2:00', '2:00-3:00', '3:00-4:00', '4:00-5:00']
        
        # Initialize structure for all batches in this timetable
        for slot in slots:
            batch_id = slot['batch_id']
            if batch_id not in organized_slots:
                organized_slots[batch_id] = {
                    'batch_name': slot['batch_name'],
                    'schedule': {day: {time: None for time in time_slots} for day in days}
                }
        
        # Fill in the slot data
        for slot in slots:
            batch_id = slot['batch_id']
            day = slot['day']
            time_slot = slot['time_slot']
            
            if (batch_id in organized_slots and 
                day in organized_slots[batch_id]['schedule'] and 
                time_slot in organized_slots[batch_id]['schedule'][day]):
                organized_slots[batch_id]['schedule'][day][time_slot] = slot

        conn.close()
        print(f"Organized slots for {organized_slots} batches")
        return render_template('view_timetable.html', 
                             timetable_info=timetable_info,
                             organized_slots=organized_slots,
                             days=days,
                             time_slots=time_slots)
                             
    except Exception as e:
        print(f"Error viewing timetable: {str(e)}")

        flash(f'Error loading timetable: {str(e)}', 'error')
        return redirect(url_for('timetables'))
    
@app.template_filter('average')
def average_filter(sequence):
    try:
        return sum(sequence) / len(sequence)
    except (TypeError, ZeroDivisionError):
        return 0
# Update these routes in app.py to include departments data

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
    
    cursor.execute('SELECT * FROM departments ORDER BY name')
    departments = cursor.fetchall()
    
    conn.close()
    return render_template('subjects.html', subjects=subjects, departments=departments)

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
    
    cursor.execute('SELECT * FROM departments ORDER BY name')
    departments = cursor.fetchall()
    
    conn.close()
    return render_template('faculty.html', faculty=faculty, departments=departments)

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
    
    cursor.execute('SELECT * FROM departments ORDER BY name')
    departments = cursor.fetchall()
    
    conn.close()
    return render_template('classrooms.html', classrooms=classrooms, departments=departments)

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

@app.route('/api/timetable/<int:timetable_id>')
@login_required
def api_timetable(timetable_id):
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get timetable info
    cursor.execute('''
        SELECT t.*, d.name as department_name 
        FROM timetables t 
        LEFT JOIN departments d ON t.department_id = d.id 
        WHERE t.id = ?
    ''', (timetable_id,))
    timetable_info = dict(cursor.fetchone())
    
    # Get timetable slots
    cursor.execute('''
        SELECT ts.*, s.name as subject_name, s.code as subject_code, 
               f.name as faculty_name, c.name as classroom_name,
               b.name as batch_name
        FROM timetable_slots ts
        LEFT JOIN subjects s ON ts.subject_id = s.id
        LEFT JOIN faculty f ON ts.faculty_id = f.id
        LEFT JOIN classrooms c ON ts.classroom_id = c.id
        LEFT JOIN batches b ON ts.batch_id = b.id
        WHERE ts.timetable_id = ?
        ORDER BY ts.batch_id, ts.day, ts.time_slot
    ''', (timetable_id,))
    slots = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'timetable': timetable_info,
        'slots': slots
    })

# Add these routes after the existing ones

@app.route('/add_department', methods=['POST'])
@admin_required
def add_department():
    code = request.form['code']
    name = request.form['name']
    
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            'INSERT INTO departments (code, name) VALUES (?, ?)',
            (code, name)
        )
        conn.commit()
        flash(f'Department "{name}" added successfully!', 'success')
    except sqlite3.IntegrityError:
        flash(f'Department code "{code}" already exists!', 'error')
    except Exception as e:
        flash(f'Error adding department: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('departments'))

@app.route('/edit_department', methods=['POST'])
@admin_required
def edit_department():
    department_id = request.form['department_id']
    code = request.form['code']
    name = request.form['name']
    
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            'UPDATE departments SET code = ?, name = ? WHERE id = ?',
            (code, name, department_id)
        )
        conn.commit()
        flash(f'Department "{name}" updated successfully!', 'success')
    except sqlite3.IntegrityError:
        flash(f'Department code "{code}" already exists!', 'error')
    except Exception as e:
        flash(f'Error updating department: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('departments'))

@app.route('/delete_department', methods=['POST'])
@admin_required
def delete_department():
    department_id = request.form['department_id']
    
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        # Get department name for flash message
        cursor.execute('SELECT name FROM departments WHERE id = ?', (department_id,))
        dept_name = cursor.fetchone()[0]
        
        # Delete department and all associated data (cascade delete)
        cursor.execute('DELETE FROM departments WHERE id = ?', (department_id,))
        conn.commit()
        flash(f'Department "{dept_name}" and all associated data deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting department: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('departments'))

# Add these routes after the existing routes in app.py

# ===== SUBJECTS ROUTES =====
@app.route('/add_subject', methods=['POST'])
@admin_required
def add_subject():
    name = request.form['name']
    code = request.form['code']
    department_id = request.form['department_id']
    subject_type = request.form['subject_type']
    classes_per_week = request.form['classes_per_week']
    
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            'INSERT INTO subjects (name, code, department_id, subject_type, classes_per_week) VALUES (?, ?, ?, ?, ?)',
            (name, code, department_id, subject_type, classes_per_week)
        )
        conn.commit()
        flash(f'Subject "{name}" added successfully!', 'success')
    except sqlite3.IntegrityError:
        flash(f'Subject code "{code}" already exists!', 'error')
    except Exception as e:
        flash(f'Error adding subject: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('subjects'))

@app.route('/edit_subject', methods=['POST'])
@admin_required
def edit_subject():
    subject_id = request.form['subject_id']
    name = request.form['name']
    code = request.form['code']
    department_id = request.form['department_id']
    subject_type = request.form['subject_type']
    classes_per_week = request.form['classes_per_week']
    
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            'UPDATE subjects SET name = ?, code = ?, department_id = ?, subject_type = ?, classes_per_week = ? WHERE id = ?',
            (name, code, department_id, subject_type, classes_per_week, subject_id)
        )
        conn.commit()
        flash(f'Subject "{name}" updated successfully!', 'success')
    except sqlite3.IntegrityError:
        flash(f'Subject code "{code}" already exists!', 'error')
    except Exception as e:
        flash(f'Error updating subject: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('subjects'))

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

# ===== FACULTY ROUTES =====
@app.route('/add_faculty', methods=['POST'])
@admin_required
def add_faculty():
    name = request.form['name']
    employee_id = request.form['employee_id']
    department_id = request.form['department_id']
    max_hours_per_day = request.form['max_hours_per_day']
    preferred_times = request.form.get('preferred_times', '')
    
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            'INSERT INTO faculty (name, employee_id, department_id, max_hours_per_day, preferred_times) VALUES (?, ?, ?, ?, ?)',
            (name, employee_id, department_id, max_hours_per_day, preferred_times)
        )
        conn.commit()
        flash(f'Faculty "{name}" added successfully!', 'success')
    except sqlite3.IntegrityError:
        flash(f'Employee ID "{employee_id}" already exists!', 'error')
    except Exception as e:
        flash(f'Error adding faculty: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('faculty'))

@app.route('/edit_faculty', methods=['POST'])
@admin_required
def edit_faculty():
    faculty_id = request.form['faculty_id']
    name = request.form['name']
    employee_id = request.form['employee_id']
    department_id = request.form['department_id']
    max_hours_per_day = request.form['max_hours_per_day']
    preferred_times = request.form.get('preferred_times', '')
    
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            'UPDATE faculty SET name = ?, employee_id = ?, department_id = ?, max_hours_per_day = ?, preferred_times = ? WHERE id = ?',
            (name, employee_id, department_id, max_hours_per_day, preferred_times, faculty_id)
        )
        conn.commit()
        flash(f'Faculty "{name}" updated successfully!', 'success')
    except sqlite3.IntegrityError:
        flash(f'Employee ID "{employee_id}" already exists!', 'error')
    except Exception as e:
        flash(f'Error updating faculty: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('faculty'))

@app.route('/delete_faculty', methods=['POST'])
@admin_required
def delete_faculty():
    faculty_id = request.form['faculty_id']
    
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT name FROM faculty WHERE id = ?', (faculty_id,))
        faculty_name = cursor.fetchone()[0]
        
        cursor.execute('DELETE FROM faculty WHERE id = ?', (faculty_id,))
        conn.commit()
        flash(f'Faculty "{faculty_name}" deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting faculty: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('faculty'))

# ===== CLASSROOMS ROUTES =====
@app.route('/add_classroom', methods=['POST'])
@admin_required
def add_classroom():
    name = request.form['name']
    capacity = request.form['capacity']
    room_type = request.form['type']
    department_id = request.form['department_id']
    
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            'INSERT INTO classrooms (name, capacity, type, department_id) VALUES (?, ?, ?, ?)',
            (name, capacity, room_type, department_id)
        )
        conn.commit()
        flash(f'Classroom "{name}" added successfully!', 'success')
    except Exception as e:
        flash(f'Error adding classroom: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('classrooms'))

@app.route('/edit_classroom', methods=['POST'])
@admin_required
def edit_classroom():
    classroom_id = request.form['classroom_id']
    name = request.form['name']
    capacity = request.form['capacity']
    room_type = request.form['type']
    department_id = request.form['department_id']
    
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            'UPDATE classrooms SET name = ?, capacity = ?, type = ?, department_id = ? WHERE id = ?',
            (name, capacity, room_type, department_id, classroom_id)
        )
        conn.commit()
        flash(f'Classroom "{name}" updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating classroom: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('classrooms'))

@app.route('/delete_classroom', methods=['POST'])
@admin_required
def delete_classroom():
    classroom_id = request.form['classroom_id']
    
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT name FROM classrooms WHERE id = ?', (classroom_id,))
        classroom_name = cursor.fetchone()[0]
        
        cursor.execute('DELETE FROM classrooms WHERE id = ?', (classroom_id,))
        conn.commit()
        flash(f'Classroom "{classroom_name}" deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting classroom: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('classrooms'))

# ===== BATCHES ROUTES =====
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
        ORDER BY d.name, b.semester, b.name
    ''')
    batches = cursor.fetchall()
    
    cursor.execute('SELECT * FROM departments ORDER BY name')
    departments = cursor.fetchall()
    
    conn.close()
    return render_template('batches.html', batches=batches, departments=departments)

@app.route('/add_batch', methods=['POST'])
@admin_required
def add_batch():
    name = request.form['name']
    department_id = request.form['department_id']
    semester = request.form['semester']
    strength = request.form['strength']
    
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            'INSERT INTO batches (name, department_id, semester, strength) VALUES (?, ?, ?, ?)',
            (name, department_id, semester, strength)
        )
        conn.commit()
        flash(f'Batch "{name}" added successfully!', 'success')
    except Exception as e:
        flash(f'Error adding batch: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('batches'))

@app.route('/edit_batch', methods=['POST'])
@admin_required
def edit_batch():
    batch_id = request.form['batch_id']
    name = request.form['name']
    department_id = request.form['department_id']
    semester = request.form['semester']
    strength = request.form['strength']
    
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            'UPDATE batches SET name = ?, department_id = ?, semester = ?, strength = ? WHERE id = ?',
            (name, department_id, semester, strength, batch_id)
        )
        conn.commit()
        flash(f'Batch "{name}" updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating batch: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('batches'))

@app.route('/delete_batch', methods=['POST'])
@admin_required
def delete_batch():
    batch_id = request.form['batch_id']
    
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT name FROM batches WHERE id = ?', (batch_id,))
        batch_name = cursor.fetchone()[0]
        
        cursor.execute('DELETE FROM batches WHERE id = ?', (batch_id,))
        conn.commit()
        flash(f'Batch "{batch_name}" deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting batch: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('batches'))

@app.route('/delete_timetable/<int:timetable_id>', methods=['POST'])
@admin_required
def delete_timetable(timetable_id):
    """Delete a timetable and all its associated slots"""
    try:
        conn = sqlite3.connect('timetable.db')
        cursor = conn.cursor()
        
        # First get timetable name for flash message
        cursor.execute('SELECT name FROM timetables WHERE id = ?', (timetable_id,))
        timetable = cursor.fetchone()
        
        if not timetable:
            flash('Timetable not found!', 'error')
            return redirect(url_for('timetables'))
        
        timetable_name = timetable[0]
        
        # Delete timetable slots first (foreign key constraint)
        cursor.execute('DELETE FROM timetable_slots WHERE timetable_id = ?', (timetable_id,))
        
        # Delete the timetable
        cursor.execute('DELETE FROM timetables WHERE id = ?', (timetable_id,))
        
        conn.commit()
        conn.close()
        
        flash(f'Timetable "{timetable_name}" has been deleted successfully!', 'success')
        
    except Exception as e:
        conn.rollback()
        print(f"Error deleting timetable: {str(e)}")
        flash(f'Error deleting timetable: {str(e)}', 'error')
    finally:
        if conn:
            conn.close()
    
    return redirect(url_for('timetables'))

# Add faculty subject management routes
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

@app.route('/add_faculty_subject', methods=['POST'])
@admin_required
def add_faculty_subject():
    """Add a subject to a faculty member"""
    faculty_id = request.form['faculty_id']
    subject_id = request.form['subject_id']
    
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            'INSERT INTO faculty_subjects (faculty_id, subject_id) VALUES (?, ?)',
            (faculty_id, subject_id)
        )
        conn.commit()
        flash('Subject added to faculty successfully!', 'success')
    except sqlite3.IntegrityError:
        flash('This faculty already teaches this subject!', 'error')
    except Exception as e:
        flash(f'Error adding subject: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('faculty_subjects', faculty_id=faculty_id))

@app.route('/remove_faculty_subject/<int:faculty_id>/<int:subject_id>')
@admin_required
def remove_faculty_subject(faculty_id, subject_id):
    """Remove a subject from a faculty member"""
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            'DELETE FROM faculty_subjects WHERE faculty_id = ? AND subject_id = ?',
            (faculty_id, subject_id)
        )
        conn.commit()
        flash('Subject removed from faculty successfully!', 'success')
    except Exception as e:
        flash(f'Error removing subject: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('faculty_subjects', faculty_id=faculty_id))

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

# Make the function available to templates
@app.context_processor
def utility_processor():
    return dict(get_faculty_subjects=get_faculty_subjects)

if __name__ == '__main__':
    # Create upload directory if it doesn't exist
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    # Initialize database
    init_db()
    
    app.run(debug=True)