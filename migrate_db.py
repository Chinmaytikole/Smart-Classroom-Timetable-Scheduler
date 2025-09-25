import sqlite3

def migrate_database():
    """Add missing columns to existing database"""
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    try:
        # Check if attendance_time column exists
        cursor.execute("PRAGMA table_info(student_attendance)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'attendance_time' not in columns:
            cursor.execute('ALTER TABLE student_attendance ADD COLUMN attendance_time TIME')
            print("Added attendance_time column to student_attendance table")
        
        # Check if events table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
        if not cursor.fetchone():
            cursor.execute('''
                CREATE TABLE events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    event_type TEXT DEFAULT 'event',
                    event_date DATE NOT NULL,
                    start_time TIME,
                    end_time TIME,
                    location TEXT,
                    priority TEXT DEFAULT 'medium',
                    created_by INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            print("Created events table")
        
        conn.commit()
        print("Database migration completed successfully!")
        
    except Exception as e:
        print(f"Migration error: {e}")
        conn.rollback()
    finally:
        conn.close()

# Run the migration
migrate_database()