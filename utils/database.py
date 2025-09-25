# utils/database.py - Enhanced version
import sqlite3
import json
from datetime import datetime
from werkzeug.security import generate_password_hash

def init_database():
    """Initialize the database with all required tables"""
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    # Create tables (same as in app.py but with additional constraints)
    tables = [
        '''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT,
            role TEXT DEFAULT 'user' CHECK(role IN ('admin', 'user', 'viewer')),
            department_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments (id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            department_id INTEGER,
            subject_type TEXT DEFAULT 'THEORY' CHECK(subject_type IN ('THEORY', 'LAB', 'PROJECT')),
            classes_per_week INTEGER DEFAULT 3 CHECK(classes_per_week BETWEEN 1 AND 10),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments (id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS faculty (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            employee_id TEXT UNIQUE NOT NULL,
            department_id INTEGER,
            max_hours_per_day INTEGER DEFAULT 8 CHECK(max_hours_per_day BETWEEN 1 AND 12),
            preferred_times TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments (id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS classrooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            capacity INTEGER CHECK(capacity > 0),
            type TEXT DEFAULT 'CLASSROOM' CHECK(type IN ('CLASSROOM', 'LAB', 'AUDITORIUM', 'SEMINAR_HALL')),
            department_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments (id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department_id INTEGER,
            semester INTEGER CHECK(semester BETWEEN 1 AND 10),
            strength INTEGER CHECK(strength > 0),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments (id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS timetables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department_id INTEGER,
            semester INTEGER,
            fitness_score REAL CHECK(fitness_score BETWEEN 0 AND 1),
            generated_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments (id),
            FOREIGN KEY (generated_by) REFERENCES users (id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS timetable_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timetable_id INTEGER,
            batch_id INTEGER,
            day TEXT NOT NULL CHECK(day IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday')),
            time_slot TEXT NOT NULL,
            subject_id INTEGER,
            faculty_id INTEGER,
            classroom_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (timetable_id) REFERENCES timetables (id),
            FOREIGN KEY (batch_id) REFERENCES batches (id),
            FOREIGN KEY (subject_id) REFERENCES subjects (id),
            FOREIGN KEY (faculty_id) REFERENCES faculty (id),
            FOREIGN KEY (classroom_id) REFERENCES classrooms (id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS faculty_subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            faculty_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (faculty_id) REFERENCES faculty (id),
            FOREIGN KEY (subject_id) REFERENCES subjects (id),
            UNIQUE(faculty_id, subject_id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS faculty_leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            faculty_id INTEGER NOT NULL,
            avg_leaves_per_month REAL DEFAULT 0 CHECK(avg_leaves_per_month >= 0),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (faculty_id) REFERENCES faculty (id),
            UNIQUE(faculty_id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS fixed_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timetable_id INTEGER,
            batch_id INTEGER NOT NULL,
            day TEXT NOT NULL CHECK(day IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday')),
            time_slot TEXT NOT NULL,
            subject_id INTEGER NOT NULL,
            faculty_id INTEGER,
            classroom_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (timetable_id) REFERENCES timetables (id),
            FOREIGN KEY (batch_id) REFERENCES batches (id),
            FOREIGN KEY (subject_id) REFERENCES subjects (id),
            FOREIGN KEY (faculty_id) REFERENCES faculty (id),
            FOREIGN KEY (classroom_id) REFERENCES classrooms (id)
        )
        ''',
        '''
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
            description TEXT,
            created_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments (id),
            FOREIGN KEY (subject_id) REFERENCES subjects (id),
            FOREIGN KEY (classroom_id) REFERENCES classrooms (id),
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            event_date DATE NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            location TEXT,
            created_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timetable_slot_id INTEGER,
            faculty_id INTEGER,
            batch_id INTEGER,
            date DATE NOT NULL,
            status TEXT DEFAULT 'PRESENT' CHECK(status IN ('PRESENT', 'ABSENT', 'LATE', 'CANCELLED')),
            notes TEXT,
            recorded_by INTEGER,
            recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (timetable_slot_id) REFERENCES timetable_slots (id),
            FOREIGN KEY (faculty_id) REFERENCES faculty (id),
            FOREIGN KEY (batch_id) REFERENCES batches (id),
            FOREIGN KEY (recorded_by) REFERENCES users (id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            type TEXT DEFAULT 'info' CHECK(type IN ('info', 'warning', 'error', 'success')),
            is_read BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            table_name TEXT NOT NULL,
            record_id INTEGER,
            changes TEXT,
            ip_address TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        '''
    ]
    
    for table in tables:
        cursor.execute(table)
    
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
    
    # Create triggers for updated_at
    triggers = [
        '''
        CREATE TRIGGER IF NOT EXISTS update_users_timestamp
        AFTER UPDATE ON users
        FOR EACH ROW
        BEGIN
            UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
        END
        ''',
        '''
        CREATE TRIGGER IF NOT EXISTS update_departments_timestamp
        AFTER UPDATE ON departments
        FOR EACH ROW
        BEGIN
            UPDATE departments SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
        END
        ''',
        '''
        CREATE TRIGGER IF NOT EXISTS update_subjects_timestamp
        AFTER UPDATE ON subjects
        FOR EACH ROW
        BEGIN
            UPDATE subjects SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
        END
        ''',
        '''
        CREATE TRIGGER IF NOT EXISTS update_faculty_timestamp
        AFTER UPDATE ON faculty
        FOR EACH ROW
        BEGIN
            UPDATE faculty SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
        END
        ''',
        '''
        CREATE TRIGGER IF NOT EXISTS update_classrooms_timestamp
        AFTER UPDATE ON classrooms
        FOR EACH ROW
        BEGIN
            UPDATE classrooms SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
        END
        ''',
        '''
        CREATE TRIGGER IF NOT EXISTS update_batches_timestamp
        AFTER UPDATE ON batches
        FOR EACH ROW
        BEGIN
            UPDATE batches SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
        END
        ''',
        '''
        CREATE TRIGGER IF NOT EXISTS update_timetables_timestamp
        AFTER UPDATE ON timetables
        FOR EACH ROW
        BEGIN
            UPDATE timetables SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
        END
        ''',
        '''
        CREATE TRIGGER IF NOT EXISTS update_timetable_slots_timestamp
        AFTER UPDATE ON timetable_slots
        FOR EACH ROW
        BEGIN
            UPDATE timetable_slots SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
        END
        ''',
        '''
        CREATE TRIGGER IF NOT EXISTS update_faculty_subjects_timestamp
        AFTER UPDATE ON faculty_subjects
        FOR EACH ROW
        BEGIN
            UPDATE faculty_subjects SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
        END
        ''',
        '''
        CREATE TRIGGER IF NOT EXISTS update_faculty_leaves_timestamp
        AFTER UPDATE ON faculty_leaves
        FOR EACH ROW
        BEGIN
            UPDATE faculty_leaves SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
        END
        ''',
        '''
        CREATE TRIGGER IF NOT EXISTS update_fixed_slots_timestamp
        AFTER UPDATE ON fixed_slots
        FOR EACH ROW
        BEGIN
            UPDATE fixed_slots SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
        END
        ''',
        '''
        CREATE TRIGGER IF NOT EXISTS update_exams_timestamp
        AFTER UPDATE ON exams
        FOR EACH ROW
        BEGIN
            UPDATE exams SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
        END
        ''',
        '''
        CREATE TRIGGER IF NOT EXISTS update_events_timestamp
        AFTER UPDATE ON events
        FOR EACH ROW
        BEGIN
            UPDATE events SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
        END
        ''',
        '''
        CREATE TRIGGER IF NOT EXISTS update_attendance_timestamp
        AFTER UPDATE ON attendance
        FOR EACH ROW
        BEGIN
            UPDATE attendance SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
        END
        '''
    ]
    
    for trigger in triggers:
        try:
            cursor.execute(trigger)
        except:
            pass  # Trigger might already exist
    
    conn.commit()
    conn.close()

def backup_database():
    """Create a backup of the database"""
    import shutil
    from datetime import datetime
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'backups/timetable_backup_{timestamp}.db'
    
    # Create backups directory if it doesn't exist
    import os
    if not os.path.exists('backups'):
        os.makedirs('backups')
    
    shutil.copy2('timetable.db', backup_file)
    return backup_file

def restore_database(backup_file):
    """Restore database from backup"""
    import shutil
    import os
    
    if not os.path.exists(backup_file):
        return False
    
    # Create a backup of current database first
    current_backup = backup_database()
    
    try:
        shutil.copy2(backup_file, 'timetable.db')
        return True
    except:
        # Restore from the backup we just made
        shutil.copy2(current_backup, 'timetable.db')
        return False

def export_data(table_name, format='json'):
    """Export data from a specific table"""
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(f'SELECT * FROM {table_name}')
    data = cursor.fetchall()
    
    conn.close()
    
    if format == 'json':
        return json.dumps([dict(row) for row in data], indent=2, default=str)
    
    elif format == 'csv':
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        if data:
            # Write header
            writer.writerow(data[0].keys())
            
            # Write data
            for row in data:
                writer.writerow(row.values())
        
        output.seek(0)
        return output.getvalue()
    
    return None

def import_data(table_name, data, format='json'):
    """Import data into a specific table"""
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        if format == 'json':
            records = json.loads(data)
            
            if not records:
                return True
            
            # Get column names
            columns = list(records[0].keys())
            placeholders = ','.join(['?'] * len(columns))
            
            # Delete existing data
            cursor.execute(f'DELETE FROM {table_name}')
            
            # Insert new data
            for record in records:
                values = [record[col] for col in columns]
                cursor.execute(f'INSERT INTO {table_name} ({",".join(columns)}) VALUES ({placeholders})', values)
            
            conn.commit()
            return True
        
        else:
            return False
            
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()