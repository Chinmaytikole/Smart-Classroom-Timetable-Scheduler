# routes/exams.py - Enhanced version
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
import sqlite3
from datetime import datetime
from functools import wraps

exams_bp = Blueprint('exams', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@exams_bp.route('/exams')
@login_required
def exams_list():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = '''
        SELECT e.*, 
               d.name as department_name,
               s.name as subject_name,
               c.name as classroom_name
        FROM exams e
        LEFT JOIN departments d ON e.department_id = d.id
        LEFT JOIN subjects s ON e.subject_id = s.id
        LEFT JOIN classrooms c ON e.classroom_id = c.id
        ORDER BY e.exam_date, e.start_time
    '''
    
    cursor.execute(query)
    exams = cursor.fetchall()
    conn.close()
    
    return render_template('exams.html', exams=exams)  # Make sure your template is named exams.html

@exams_bp.route('/exams/create', methods=['GET', 'POST'])
@login_required
def create_exam():
    if request.method == 'POST':
        try:
            name = request.form['name']
            department_id = request.form.get('department_id')
            semester = request.form.get('semester')
            subject_id = request.form.get('subject_id')
            exam_date = request.form['exam_date']
            start_time = request.form['start_time']
            end_time = request.form['end_time']
            classroom_id = request.form.get('classroom_id')
            print(name, department_id, semester, subject_id, exam_date, start_time, end_time, classroom_id)
            conn = sqlite3.connect('timetable.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO exams 
                (name, department_id, semester, subject_id, exam_date, start_time, end_time, classroom_id,  created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, department_id, semester, subject_id, exam_date, start_time, end_time, classroom_id, session['user_id']))
            
            conn.commit()
            conn.close()
            
            flash('Exam created successfully!', 'success')
            return redirect(url_for('exams.exams'))
            
        except Exception as e:
            flash(f'Error creating exam: {str(e)}', 'error')
            return redirect(url_for('exams.create_exam'))
    
    # GET request - show form
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM departments ORDER BY name')
    departments = cursor.fetchall()
    
    cursor.execute('SELECT * FROM subjects ORDER BY name')
    subjects = cursor.fetchall()
    
    cursor.execute('SELECT * FROM classrooms ORDER BY name')
    classrooms = cursor.fetchall()
    
    cursor.execute('SELECT DISTINCT semester FROM batches ORDER BY semester')
    semesters = [row['semester'] for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('create_exam.html', 
                         departments=departments,
                         subjects=subjects,
                         classrooms=classrooms,
                         semesters=semesters)

@exams_bp.route('/exams/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_exam(id):
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    
    if request.method == 'POST':
        try:
            name = request.form['name']
            department_id = request.form.get('department_id')
            semester = request.form.get('semester')
            subject_id = request.form.get('subject_id')
            exam_date = request.form['exam_date']
            start_time = request.form['start_time']
            end_time = request.form['end_time']
            classroom_id = request.form.get('classroom_id')
            description = request.form.get('description', '')
            
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE exams 
                SET name = ?, department_id = ?, semester = ?, subject_id = ?, 
                    exam_date = ?, start_time = ?, end_time = ?, classroom_id = ?, description = ?
                WHERE id = ?
            ''', (name, department_id, semester, subject_id, exam_date, start_time, end_time, classroom_id, description, id))
            
            conn.commit()
            flash('Exam updated successfully!', 'success')
            
        except Exception as e:
            flash(f'Error updating exam: {str(e)}', 'error')
        finally:
            conn.close()
        
        return redirect(url_for('exams.exams'))
    
    # GET request - show edit form
    cursor = conn.cursor()
    cursor.execute('''
        SELECT e.* 
        FROM exams e 
        WHERE e.id = ?
    ''', (id,))
    exam = cursor.fetchone()
    
    cursor.execute('SELECT * FROM departments ORDER BY name')
    departments = cursor.fetchall()
    
    cursor.execute('SELECT * FROM subjects ORDER BY name')
    subjects = cursor.fetchall()
    
    cursor.execute('SELECT * FROM classrooms ORDER BY name')
    classrooms = cursor.fetchall()
    
    cursor.execute('SELECT DISTINCT semester FROM batches ORDER BY semester')
    semesters = [row['semester'] for row in cursor.fetchall()]
    
    conn.close()
    
    if not exam:
        flash('Exam not found.', 'error')
        return redirect(url_for('exams.exams'))
    
    return render_template('edit_exam.html', 
                         exam=exam,
                         departments=departments,
                         subjects=subjects,
                         classrooms=classrooms,
                         semesters=semesters)

@exams_bp.route('/exams/<int:id>/delete')
@login_required
def delete_exam(id):
    try:
        conn = sqlite3.connect('timetable.db')
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM exams WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        
        flash('Exam deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting exam: {str(e)}', 'error')
    
    return redirect(url_for('exams.exams'))

@exams_bp.route('/api/exams/calendar')
@login_required
def exam_calendar():
    start = request.args.get('start')
    end = request.args.get('end')
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = '''
        SELECT e.*, 
               d.name as department_name,
               s.name as subject_name,
               c.name as classroom_name
        FROM exams e
        LEFT JOIN departments d ON e.department_id = d.id
        LEFT JOIN subjects s ON e.subject_id = s.id
        LEFT JOIN classrooms c ON e.classroom_id = c.id
        WHERE 1=1
    '''
    
    params = []
    
    if start:
        query += ' AND e.exam_date >= ?'
        params.append(start)
    
    if end:
        query += ' AND e.exam_date <= ?'
        params.append(end)
    
    query += ' ORDER BY e.exam_date, e.start_time'
    
    cursor.execute(query, params)
    exams = cursor.fetchall()
    conn.close()
    
    # Format for FullCalendar
    events = []
    for exam in exams:
        events.append({
            'id': exam['id'],
            'title': f"{exam['name']} - {exam['subject_name']}",
            'start': f"{exam['exam_date']}T{exam['start_time']}",
            'end': f"{exam['exam_date']}T{exam['end_time']}",
            'backgroundColor': '#dc3545',
            'borderColor': '#dc3545',
            'extendedProps': {
                'department': exam['department_name'],
                'classroom': exam['classroom_name'],
                'type': 'exam'
            }
        })
    
    return jsonify(events)

@exams_bp.route('/exams/calendar')
@login_required
def exam_calendar_page():
    return render_template('exam_calendar.html')  # Create this template for calendar view