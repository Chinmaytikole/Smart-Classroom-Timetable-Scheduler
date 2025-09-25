# routes/attendance.py - Enhanced version with QR attendance marking
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
import sqlite3
from datetime import datetime, date, timedelta
from functools import wraps
import base64
import io

# Add these imports at the top
from datetime import datetime
attendance_bp = Blueprint('attendance', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'student':
            flash('Student access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def faculty_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'teacher_id' not in session:
            flash('Faculty access required.', 'error')
            return redirect(url_for('teacher_login'))
        return f(*args, **kwargs)
    return decorated_function


@attendance_bp.route('/attendance')
@admin_required
def attendance():
    date_str = request.args.get('date', date.today().isoformat())
    faculty_id = request.args.get('faculty_id')
    batch_id = request.args.get('batch_id')
    
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        selected_date = date.today()
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get timetable slots for the selected date
    day_name = selected_date.strftime('%A')
    
    query = '''
        SELECT ts.*, 
               s.name as subject_name,
               f.name as faculty_name,
               c.name as classroom_name,
               b.name as batch_name,
               a.status as attendance_status,
               a.notes as attendance_notes
        FROM timetable_slots ts
        LEFT JOIN subjects s ON ts.subject_id = s.id
        LEFT JOIN faculty f ON ts.faculty_id = f.id
        LEFT JOIN classrooms c ON ts.classroom_id = c.id
        LEFT JOIN batches b ON ts.batch_id = b.id
        LEFT JOIN attendance a ON ts.id = a.timetable_slot_id AND a.date = ?
        WHERE ts.day = ?
    '''
    
    params = [selected_date.isoformat(), day_name]
    
    if faculty_id:
        query += ' AND ts.faculty_id = ?'
        params.append(faculty_id)
    
    if batch_id:
        query += ' AND ts.batch_id = ?'
        params.append(batch_id)
    
    query += ' ORDER BY ts.time_slot'
    
    cursor.execute(query, params)
    slots = cursor.fetchall()
    
    # Get faculty for filter
    cursor.execute('SELECT id, name FROM faculty ORDER BY name')
    faculty_list = cursor.fetchall()
    
    # Get batches for filter
    cursor.execute('SELECT id, name FROM batches ORDER BY name')
    batches_list = cursor.fetchall()
    
    conn.close()
    
    return render_template('attendance.html',
                         slots=slots,
                         selected_date=selected_date,
                         faculty_list=faculty_list,
                         batches_list=batches_list,
                         selected_faculty=faculty_id,
                         selected_batch=batch_id)

@attendance_bp.route('/attendance/record', methods=['POST'])
@admin_required
def record_attendance():
    try:
        slot_id = request.form['slot_id']
        date_str = request.form['date']
        status = request.form['status']
        notes = request.form.get('notes', '')
        faculty_id = request.form['faculty_id']
        batch_id = request.form['batch_id']
        
        conn = sqlite3.connect('timetable.db')
        cursor = conn.cursor()
        
        # Check if attendance already recorded
        cursor.execute('''
            SELECT id FROM attendance 
            WHERE timetable_slot_id = ? AND date = ?
        ''', (slot_id, date_str))
        
        existing = cursor.fetchone()
        
        if existing:
            # Update existing record
            cursor.execute('''
                UPDATE attendance 
                SET status = ?, notes = ?, recorded_by = ?, recorded_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, notes, session['user_id'], existing[0]))
        else:
            # Insert new record
            cursor.execute('''
                INSERT INTO attendance 
                (timetable_slot_id, faculty_id, batch_id, date, status, notes, recorded_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (slot_id, faculty_id, batch_id, date_str, status, notes, session['user_id']))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Attendance recorded successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error recording attendance: {str(e)}'})

# NEW: QR-based attendance marking endpoint for students
@attendance_bp.route('/api/mark-attendance', methods=['POST'])
@student_required
def mark_attendance_qr():
    """Mark attendance using QR code data and face verification"""
    try:
        data = request.get_json()
        qr_data = data.get('qr_data')
        student_id = session.get('user_id')  # Using user_id from session
        face_image = data.get('face_image')
        
        if not all([qr_data, student_id, face_image]):
            return jsonify({'success': False, 'message': 'Missing required data'})
        
        # Validate QR data
        if qr_data.get('type') != 'attendance':
            return jsonify({'success': False, 'message': 'Invalid QR code type'})
        
        # Check expiry (QR data uses milliseconds timestamp)
        current_timestamp = datetime.now().timestamp() * 1000
        if current_timestamp > qr_data.get('expiry', 0):
            return jsonify({'success': False, 'message': 'QR code has expired'})
        
        conn = sqlite3.connect('timetable.db')
        cursor = conn.cursor()
        
        # Get subject and batch names for response
        cursor.execute('SELECT name FROM subjects WHERE id = ?', (qr_data['subject_id'],))
        subject = cursor.fetchone()
        cursor.execute('SELECT name FROM batches WHERE id = ?', (qr_data['batch_id'],))
        batch = cursor.fetchone()
        
        if not subject or not batch:
            return jsonify({'success': False, 'message': 'Invalid subject or batch'})
        
        # Check if attendance already marked for this session today
        cursor.execute('''
            SELECT id FROM attendance 
            WHERE student_id = ? AND subject_id = ? AND batch_id = ? AND date = DATE('now')
        ''', (student_id, qr_data['subject_id'], qr_data['batch_id']))
        
        existing_attendance = cursor.fetchone()
        if existing_attendance:
            return jsonify({'success': False, 'message': 'Attendance already marked for this class today'})
        
        # Insert attendance record with face image
        cursor.execute('''
            INSERT INTO attendance 
            (student_id, faculty_id, subject_id, batch_id, 
             date, attendance_time, status, face_image, 
             recorded_by, recorded_at)
            VALUES (?, ?, ?, ?, DATE('now'), TIME('now'), 'Present', ?, 
                    'qr_system', CURRENT_TIMESTAMP)
        ''', (student_id, qr_data['faculty_id'], qr_data['subject_id'], 
              qr_data['batch_id'], face_image))
        
        conn.commit()
        attendance_id = cursor.lastrowid
        
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Attendance marked successfully!',
            'attendance_id': attendance_id,
            'subject_name': subject[0],
            'batch_name': batch[0],
            'attendance_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error marking attendance: {str(e)}'})

# NEW: Faculty QR code generation endpoint
@attendance_bp.route('/api/generate-qr-data', methods=['POST'])
@faculty_required
def generate_qr_data():
    """Generate QR code data for faculty"""
    try:
        data = request.get_json()
        batch_id = data.get('batch_id')
        subject_id = data.get('subject_id')
        faculty_id = session.get('user_id')
        
        if not all([batch_id, subject_id, faculty_id]):
            return jsonify({'success': False, 'message': 'Missing required data'})
        
        # Generate QR code data with essential information
        qr_data = {
            'type': 'attendance',
            'faculty_id': faculty_id,
            'batch_id': batch_id,
            'subject_id': subject_id,
            'timestamp': datetime.now().timestamp() * 1000,  # milliseconds
            'expiry': (datetime.now() + timedelta(minutes=15)).timestamp() * 1000  # 15 minutes expiry
        }
        
        return jsonify({
            'success': True,
            'qr_data': qr_data,
            'expiry_time': (datetime.now() + timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error generating QR data: {str(e)}'})

# NEW: Get student's attendance history
@attendance_bp.route('/student/attendance-history')
@student_required
def student_attendance_history():
    """View attendance history for logged-in student"""
    student_id = session.get('user_id')
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get attendance history
    cursor.execute('''
        SELECT a.*, s.name as subject_name, b.name as batch_name, f.name as faculty_name
        FROM attendance a
        LEFT JOIN subjects s ON a.subject_id = s.id
        LEFT JOIN batches b ON a.batch_id = b.id
        LEFT JOIN faculty f ON a.faculty_id = f.id
        WHERE a.student_id = ?
        ORDER BY a.date DESC, a.attendance_time DESC
    ''', (student_id,))
    
    attendance_history = cursor.fetchall()
    
    # Calculate attendance statistics
    cursor.execute('''
        SELECT 
            COUNT(*) as total_classes,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_classes,
            SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_classes
        FROM attendance 
        WHERE student_id = ?
    ''', (student_id,))
    
    stats = cursor.fetchone()
    
    conn.close()
    
    return render_template('student_attendance_history.html',
                         attendance_history=attendance_history,
                         stats=stats)

@attendance_bp.route('/attendance/reports')
@admin_required
def attendance_reports():
    report_type = request.args.get('type', 'faculty')
    start_date = request.args.get('start_date', (date.today() - timedelta(days=30)).isoformat())
    end_date = request.args.get('end_date', date.today().isoformat())
    faculty_id = request.args.get('faculty_id')
    batch_id = request.args.get('batch_id')
    
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
    except:
        start_dt = date.today() - timedelta(days=30)
        end_dt = date.today()
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if report_type == 'faculty':
        # Faculty attendance report
        query = '''
            SELECT f.id, f.name, 
                   COUNT(a.id) as total_classes,
                   SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_classes,
                   SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_classes,
                   SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) as late_classes
            FROM faculty f
            LEFT JOIN attendance a ON f.id = a.faculty_id AND a.date BETWEEN ? AND ?
            WHERE 1=1
        '''
        
        params = [start_dt.isoformat(), end_dt.isoformat()]
        
        if faculty_id:
            query += ' AND f.id = ?'
            params.append(faculty_id)
        
        query += ' GROUP BY f.id, f.name ORDER BY f.name'
        
        cursor.execute(query, params)
        report_data = cursor.fetchall()
        
    elif report_type == 'batch':
        # Batch attendance report
        query = '''
            SELECT b.id, b.name, 
                   COUNT(a.id) as total_classes,
                   SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_classes,
                   SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_classes
            FROM batches b
            LEFT JOIN attendance a ON b.id = a.batch_id AND a.date BETWEEN ? AND ?
            WHERE 1=1
        '''
        
        params = [start_dt.isoformat(), end_dt.isoformat()]
        
        if batch_id:
            query += ' AND b.id = ?'
            params.append(batch_id)
        
        query += ' GROUP BY b.id, b.name ORDER BY b.name'
        
        cursor.execute(query, params)
        report_data = cursor.fetchall()
    
    elif report_type == 'student':
        # Student attendance report
        query = '''
            SELECT s.id, s.name, s.roll_number, b.name as batch_name,
                   COUNT(a.id) as total_classes,
                   SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_classes,
                   SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_classes
            FROM students s
            LEFT JOIN batches b ON s.batch_id = b.id
            LEFT JOIN attendance a ON s.id = a.student_id AND a.date BETWEEN ? AND ?
            WHERE 1=1
        '''
        
        params = [start_dt.isoformat(), end_dt.isoformat()]
        
        if batch_id:
            query += ' AND s.batch_id = ?'
            params.append(batch_id)
        
        query += ' GROUP BY s.id, s.name, s.roll_number, b.name ORDER BY s.name'
        
        cursor.execute(query, params)
        report_data = cursor.fetchall()
    
    # Get faculty for filter
    cursor.execute('SELECT id, name FROM faculty ORDER BY name')
    faculty_list = cursor.fetchall()
    
    # Get batches for filter
    cursor.execute('SELECT id, name FROM batches ORDER BY name')
    batches_list = cursor.fetchall()
    
    conn.close()
    
    return render_template('attendance_reports.html',
                         report_type=report_type,
                         report_data=report_data,
                         start_date=start_dt,
                         end_date=end_dt,
                         faculty_list=faculty_list,
                         batches_list=batches_list,
                         selected_faculty=faculty_id,
                         selected_batch=batch_id)

@attendance_bp.route('/api/attendance/stats')
@admin_required
def attendance_stats():
    period = request.args.get('period', 'week')  # week, month, year
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if period == 'week':
        # Last 7 days
        dates = [(date.today() - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
        
        query = '''
            SELECT date, 
                   COUNT(*) as total_classes,
                   SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_classes
            FROM attendance
            WHERE date BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date
        '''
        
        cursor.execute(query, [dates[0], dates[-1]])
        data = cursor.fetchall()
        
        # Fill in missing dates
        result = []
        for d in dates:
            record = next((row for row in data if row['date'] == d), None)
            if record:
                result.append({
                    'date': d,
                    'total': record['total_classes'],
                    'present': record['present_classes'],
                    'attendance_rate': (record['present_classes'] / record['total_classes'] * 100) if record['total_classes'] > 0 else 0
                })
            else:
                result.append({
                    'date': d,
                    'total': 0,
                    'present': 0,
                    'attendance_rate': 0
                })
    
    conn.close()
    
    return jsonify(result)

# NEW: Student scan face page
@attendance_bp.route('/student/scan-face')
@student_required
def student_scan_face():
    """QR + Face scanning interface for students"""
    return render_template('student_scan_face.html')

# NEW: Faculty QR generation page
@attendance_bp.route('/faculty/generate-qr')
@faculty_required
def faculty_generate_qr():
    """QR code generation interface for faculty"""
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    # Get faculty's batches and subjects
    faculty_id = session.get('user_id')
    
    cursor.execute('''
        SELECT DISTINCT b.id, b.name 
        FROM timetable_slots ts
        JOIN batches b ON ts.batch_id = b.id
        WHERE ts.faculty_id = ?
        ORDER BY b.name
    ''', (faculty_id,))
    batches = cursor.fetchall()
    
    cursor.execute('''
        SELECT DISTINCT s.id, s.name 
        FROM timetable_slots ts
        JOIN subjects s ON ts.subject_id = s.id
        WHERE ts.faculty_id = ?
        ORDER BY s.name
    ''', (faculty_id,))
    subjects = cursor.fetchall()
    
    conn.close()
    
    return render_template('faculty_generate_qr.html',
                         batches=batches,
                         subjects=subjects)


@attendance_bp.route('/faculty/attendance')
@faculty_required
def faculty_attendance():
    """Faculty attendance marking interface"""
    faculty_id = session.get('user_id')
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get faculty's batches and subjects (FIXED QUERY - removed semesters table join)
    cursor.execute('''
        SELECT DISTINCT b.id as batch_id, b.name as batch_name, 
               s.id as subject_id, s.name as subject_name,
               b.semester as semester_id
        FROM timetable_slots ts
        JOIN batches b ON ts.batch_id = b.id
        JOIN subjects s ON ts.subject_id = s.id
        WHERE ts.faculty_id = ?
        ORDER BY b.semester, b.name, s.name
    ''', (faculty_id,))
    
    teaching_data = cursor.fetchall()
    
    # Organize data by semester (using the semester integer from batches)
    semesters = {}
    for row in teaching_data:
        sem_id = row['semester_id']  # This is now an integer from batches.semester
        
        # Create semester name dynamically
        semester_name = f"Semester {sem_id}"
        
        if sem_id not in semesters:
            semesters[sem_id] = {
                'name': semester_name,
                'batches': {}
            }
        
        batch_id = row['batch_id']
        if batch_id not in semesters[sem_id]['batches']:
            semesters[sem_id]['batches'][batch_id] = {
                'name': row['batch_name'],
                'subjects': []
            }
        
        semesters[sem_id]['batches'][batch_id]['subjects'].append({
            'id': row['subject_id'],
            'name': row['subject_name']
        })
    
    # Get today's date for default selection
    today = date.today().isoformat()
    
    conn.close()
    
    return render_template('faculty_attendance.html',
                         semesters=semesters,
                         today=today,
                         faculty_id=faculty_id)

@attendance_bp.route('/api/faculty/get-students')
@faculty_required
def get_students_for_attendance():
    """Get students list for selected batch"""
    batch_id = request.args.get('batch_id')
    faculty_id = session.get('user_id')
    
    if not batch_id:
        return jsonify({'success': False, 'message': 'Batch ID required'})
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Verify that the faculty teaches this batch
    cursor.execute('''
        SELECT 1 FROM timetable_slots 
        WHERE faculty_id = ? AND batch_id = ? LIMIT 1
    ''', (faculty_id, batch_id))
    
    if not cursor.fetchone():
        return jsonify({'success': False, 'message': 'You are not assigned to this batch'})
    
    # Get students from the batch
    cursor.execute('''
        SELECT s.id, s.roll_number, s.name, s.email
        FROM students s
        WHERE s.batch_id = ?
        ORDER BY s.roll_number
    ''', (batch_id,))
    
    students = cursor.fetchall()
    
    # Get today's attendance for this batch (if any)
    selected_date = request.args.get('date', date.today().isoformat())
    subject_id = request.args.get('subject_id')
    
    existing_attendance = {}
    if subject_id:
        cursor.execute('''
            SELECT student_id, status, notes
            FROM attendance 
            WHERE batch_id = ? AND subject_id = ? AND date = ?
        ''', (batch_id, subject_id, selected_date))
        
        for record in cursor.fetchall():
            existing_attendance[record['student_id']] = {
                'status': record['status'],
                'notes': record['notes'] or ''
            }
    
    conn.close()
    
    students_list = []
    for student in students:
        student_data = dict(student)
        student_id = student['id']
        
        if student_id in existing_attendance:
            student_data['attendance'] = existing_attendance[student_id]
        else:
            student_data['attendance'] = {'status': '', 'notes': ''}
        
        students_list.append(student_data)
    
    return jsonify({
        'success': True,
        'students': students_list,
        'date': selected_date
    })

@attendance_bp.route('/api/faculty/mark-attendance', methods=['POST'])
@faculty_required
def faculty_mark_attendance():
    """Mark attendance for students (manual entry by faculty)"""
    try:
        data = request.get_json()
        batch_id = data.get('batch_id')
        subject_id = data.get('subject_id')
        attendance_date = data.get('date')
        students_data = data.get('students', [])
        faculty_id = session.get('user_id')
        
        if not all([batch_id, subject_id, attendance_date]):
            return jsonify({'success': False, 'message': 'Missing required data'})
        
        # Validate date format
        try:
            datetime.strptime(attendance_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format'})
        
        conn = sqlite3.connect('timetable.db')
        cursor = conn.cursor()
        
        # Verify faculty teaches this batch and subject
        cursor.execute('''
            SELECT 1 FROM timetable_slots 
            WHERE faculty_id = ? AND batch_id = ? AND subject_id = ? LIMIT 1
        ''', (faculty_id, batch_id, subject_id))
        
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'You are not assigned to teach this subject for the selected batch'})
        
        # Process each student's attendance
        success_count = 0
        for student_data in students_data:
            student_id = student_data.get('student_id')
            status = student_data.get('status', '')
            notes = student_data.get('notes', '')
            
            if not student_id or not status:
                continue
            
            # Check if attendance already exists for this student on this date
            cursor.execute('''
                SELECT id FROM attendance 
                WHERE student_id = ? AND batch_id = ? AND subject_id = ? AND date = ?
            ''', (student_id, batch_id, subject_id, attendance_date))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing record
                cursor.execute('''
                    UPDATE attendance 
                    SET status = ?, notes = ?, recorded_by = ?, recorded_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (status, notes, faculty_id, existing[0]))
            else:
                # Insert new record
                cursor.execute('''
                    INSERT INTO attendance 
                    (student_id, faculty_id, batch_id, subject_id, date, 
                     attendance_time, status, notes, recorded_by)
                    VALUES (?, ?, ?, ?, ?, TIME('now'), ?, ?, ?)
                ''', (student_id, faculty_id, batch_id, subject_id, attendance_date, 
                      status, notes, faculty_id))
            
            success_count += 1
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Attendance marked for {success_count} students',
            'count': success_count
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error marking attendance: {str(e)}'})

@attendance_bp.route('/faculty/attendance-history')
@faculty_required
def faculty_attendance_history():
    """View attendance history marked by faculty"""
    faculty_id = session.get('user_id')
    
    # Get filter parameters
    batch_id = request.args.get('batch_id')
    subject_id = request.args.get('subject_id')
    start_date = request.args.get('start_date', (date.today() - timedelta(days=30)).isoformat())
    end_date = request.args.get('end_date', date.today().isoformat())
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Build query with filters
    query = '''
        SELECT a.*, 
               s.name as student_name, s.roll_number,
               b.name as batch_name,
               sub.name as subject_name,
               COUNT(*) OVER() as total_count
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        JOIN batches b ON a.batch_id = b.id
        JOIN subjects sub ON a.subject_id = sub.id
        WHERE a.faculty_id = ? AND a.date BETWEEN ? AND ?
    '''
    
    params = [faculty_id, start_date, end_date]
    
    if batch_id:
        query += ' AND a.batch_id = ?'
        params.append(batch_id)
    
    if subject_id:
        query += ' AND a.subject_id = ?'
        params.append(subject_id)
    
    query += ' ORDER BY a.date DESC, a.attendance_time DESC'
    
    # Add pagination
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    query += ' LIMIT ? OFFSET ?'
    params.extend([per_page, offset])
    
    cursor.execute(query, params)
    attendance_history = cursor.fetchall()
    
    # Get faculty's batches and subjects for filters
    cursor.execute('''
        SELECT DISTINCT b.id, b.name as batch_name, 
               sub.id as subject_id, sub.name as subject_name
        FROM timetable_slots ts
        JOIN batches b ON ts.batch_id = b.id
        JOIN subjects sub ON ts.subject_id = sub.id
        WHERE ts.faculty_id = ?
        ORDER BY b.name, sub.name
    ''', (faculty_id,))
    
    teaching_options = cursor.fetchall()
    
    conn.close()
    
    # Organize batches and subjects
    batches = []
    subjects = []
    seen_batches = set()
    seen_subjects = set()
    
    for row in teaching_options:
        if row['id'] not in seen_batches:
            batches.append({'id': row['id'], 'name': row['batch_name']})
            seen_batches.add(row['id'])
        
        if row['subject_id'] not in seen_subjects:
            subjects.append({'id': row['subject_id'], 'name': row['subject_name']})
            seen_subjects.add(row['subject_id'])
    
    return render_template('faculty_attendance_history.html',
                         attendance_history=attendance_history,
                         batches=batches,
                         subjects=subjects,
                         current_filters={
                             'batch_id': batch_id,
                             'subject_id': subject_id,
                             'start_date': start_date,
                             'end_date': end_date,
                             'page': page
                         })