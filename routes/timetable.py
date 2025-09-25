# routes/timetable.py - Enhanced version with your original structure
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from genetic_algorithm import EnhancedGeneticTimetable
import sqlite3
from datetime import datetime
import json
from functools import wraps

timetable_bp = Blueprint('timetable', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@timetable_bp.route('/generate', methods=['GET', 'POST'])
@admin_required
def generate_timetable():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM departments ORDER BY name')
    departments = cursor.fetchall()
    
    # Fetch all batches and subjects for the initial form load
    cursor.execute('SELECT * FROM batches ORDER BY name')
    batches = cursor.fetchall()
    
    cursor.execute('SELECT * FROM subjects ORDER BY name')
    subjects = cursor.fetchall()
    
    if request.method == 'POST':
        department_id = request.form['department_id']
        semester = request.form['semester']
        timetable_name = request.form['name']
        max_classes_per_day = request.form.get('max_classes_per_day', 6)
        
        # Fetch all required data for genetic algorithm
        cursor.execute('SELECT * FROM subjects WHERE department_id = ?', (department_id,))
        subjects_data = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute('SELECT * FROM batches WHERE department_id = ? AND semester = ?', (department_id, semester))
        batches_data = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute('SELECT * FROM faculty')
        faculty_data = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute('SELECT * FROM classrooms')
        classrooms_data = [dict(row) for row in cursor.fetchall()]
        
        # Get fixed slots from form data
        fixed_slots = []
        fixed_batches = request.form.getlist('fixed_batch[]')
        fixed_days = request.form.getlist('fixed_day[]')
        fixed_times = request.form.getlist('fixed_time[]')
        fixed_subjects = request.form.getlist('fixed_subject[]')
        
        for i in range(len(fixed_batches)):
            if fixed_batches[i] and fixed_days[i] and fixed_times[i] and fixed_subjects[i]:
                fixed_slots.append({
                    'batch_id': int(fixed_batches[i]),
                    'day': fixed_days[i],
                    'time_slot': fixed_times[i],
                    'subject_id': int(fixed_subjects[i])
                })
        
        # Define constraints
        constraints = {
            'days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
            'time_slots': ['9:00-10:00', '10:00-11:00', '11:00-12:00', '12:00-1:00', '1:00-2:00', '2:00-3:00', '3:00-4:00'],
            'lunch_break': '12:00-1:00',
            'max_classes_per_day': int(max_classes_per_day),
            'max_hours_per_faculty': 8,
            'max_classes_per_day_per_batch': int(max_classes_per_day),
            'fixed_slots': fixed_slots
        }
        
        # Generate timetable using genetic algorithm with all required parameters
        genetic_algo = EnhancedGeneticTimetable(
            subjects=subjects_data,
            faculty=faculty_data,
            classrooms=classrooms_data,
            batches=batches_data,
            constraints=constraints
        )
        
        timetable, fitness_score = genetic_algo.run()
        
        # Save timetable to database
        cursor.execute(
            "INSERT INTO timetables (name, department_id, semester, fitness_score, generated_by) VALUES (?, ?, ?, ?, ?)",
            (timetable_name, department_id, semester, fitness_score, session['user_id'])
        )
        
        timetable_id = cursor.lastrowid
        
        # Save timetable slots
        for batch_id, days in timetable.items():
            for day, time_slots in days.items():
                for time_slot, slot_data in time_slots.items():
                    if slot_data:  # Only save non-empty slots
                        cursor.execute(
                            "INSERT INTO timetable_slots (timetable_id, batch_id, day, time_slot, subject_id, faculty_id, classroom_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (timetable_id, batch_id, day, time_slot, slot_data['subject_id'], slot_data['faculty_id'], slot_data['classroom_id'])
                        )
        
        conn.commit()
        conn.close()
        
        flash(f'Timetable generated successfully with fitness score: {fitness_score:.2f}', 'success')
        return redirect(url_for('timetable.view_timetable', timetable_id=timetable_id))
    
    conn.close()
    return render_template('generate_timetable.html', 
                         departments=departments, 
                         batches=batches, 
                         subjects=subjects)

@timetable_bp.route('/timetables')
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

@timetable_bp.route('/view_timetable/<int:id>')  # Change parameter name
def view_timetable(id):  # Change parameter name to match
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get timetable details
    cursor.execute('''
        SELECT t.*, d.name as department_name, u.full_name as generated_by_name
        FROM timetables t 
        LEFT JOIN departments d ON t.department_id = d.id 
        LEFT JOIN users u ON t.generated_by = u.id
        WHERE t.id = ?
    ''', (id,))  # Update parameter name
    timetable = cursor.fetchone()
    
    if not timetable:
        flash('Timetable not found.', 'error')
        return redirect(url_for('timetable.timetables'))
    
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
    ''', (id,))  # Update parameter name
    slots = cursor.fetchall()
    
    # Organize slots by batch and day
    organized_slots = {}
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    time_slots = ['9:00-10:00', '10:00-11:00', '11:00-12:00', '12:00-1:00', '1:00-2:00', '2:00-3:00', '3:00-4:00']
    
    # Initialize structure
    for slot in slots:
        batch_id = slot['batch_id']
        if batch_id not in organized_slots:
            organized_slots[batch_id] = {
                'batch_name': slot['batch_name'],
                'schedule': {day: {time: None for time in time_slots} for day in days}
            }
    
    # Fill in the schedule
    for slot in slots:
        batch_id = slot['batch_id']
        day = slot['day']
        time_slot = slot['time_slot']
        
        if (batch_id in organized_slots and 
            day in organized_slots[batch_id]['schedule'] and 
            time_slot in organized_slots[batch_id]['schedule'][day]):
            organized_slots[batch_id]['schedule'][day][time_slot] = slot
    
    conn.close()
    
    return render_template('view_timetable.html', 
                          timetable=timetable, 
                          organized_slots=organized_slots,
                          days=days,
                          time_slots=time_slots)
@timetable_bp.route('/get_department_data/<int:department_id>')
def get_department_data(department_id):
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Fetch batches for the selected department
    cursor.execute('SELECT * FROM batches WHERE department_id = ? ORDER BY name', (department_id,))
    batches = [dict(row) for row in cursor.fetchall()]
    
    # Fetch subjects for the selected department
    cursor.execute('SELECT * FROM subjects WHERE department_id = ? ORDER BY name', (department_id,))
    subjects = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'batches': batches,
        'subjects': subjects
    })

@timetable_bp.route('/delete_timetable/<int:timetable_id>', methods=['POST'])
@admin_required
def delete_timetable(timetable_id):

    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    # Delete associated slots first
    cursor.execute('DELETE FROM timetable_slots WHERE timetable_id = ?', (timetable_id,))
    
    # Delete timetable
    cursor.execute('DELETE FROM timetables WHERE id = ?', (timetable_id,))
    conn.commit()
    conn.close()
    
    # Log the action (you'll need to implement log_audit)
    # log_audit('DELETE', 'timetables', timetable_id)
    
    flash('Timetable deleted successfully!', 'success')
    return redirect(url_for('timetable.timetables'))

@timetable_bp.route('/api/timetable/<int:id>/export')
def export_timetable(id):
    format = request.args.get('format', 'json')
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get timetable details
    cursor.execute('''
        SELECT t.*, d.name as department_name
        FROM timetables t
        LEFT JOIN departments d ON t.department_id = d.id
        WHERE t.id = ?
    ''', (id,))
    timetable = cursor.fetchone()
    
    # Get timetable slots
    cursor.execute('''
        SELECT ts.*, 
               s.name as subject_name, s.code as subject_code,
               f.name as faculty_name,
               c.name as classroom_name,
               b.name as batch_name
        FROM timetable_slots ts
        LEFT JOIN subjects s ON ts.subject_id = s.id
        LEFT JOIN faculty f ON ts.faculty_id = f.id
        LEFT JOIN classrooms c ON ts.classroom_id = c.id
        LEFT JOIN batches b ON ts.batch_id = b.id
        WHERE ts.timetable_id = ?
    ''', (id,))
    slots = cursor.fetchall()
    
    conn.close()
    
    if format == 'json':
        data = {
            'timetable': dict(timetable),
            'slots': [dict(slot) for slot in slots]
        }
        return jsonify(data)
    
    elif format == 'csv':
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Day', 'Time Slot', 'Batch', 'Subject', 'Faculty', 'Classroom'])
        
        # Write data
        for slot in slots:
            writer.writerow([
                slot['day'],
                slot['time_slot'],
                slot['batch_name'],
                f"{slot['subject_code']} - {slot['subject_name']}",
                slot['faculty_name'],
                slot['classroom_name']
            ])
        
        output.seek(0)
        return output.getvalue(), 200, {
            'Content-Type': 'text/csv',
            'Content-Disposition': f'attachment; filename=timetable_{id}.csv'
        }
    
    else:
        flash('Unsupported export format.', 'error')
        return redirect(url_for('timetable.view_timetable', id=id))

@timetable_bp.route('/api/timetable/analyze')
def analyze_timetable():
    timetable_id = request.args.get('id')
    
    if not timetable_id:
        return jsonify({'error': 'Timetable ID required'}), 400
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get timetable slots
    cursor.execute('''
        SELECT ts.*, 
               s.name as subject_name,
               f.name as faculty_name,
               c.name as classroom_name,
               b.name as batch_name, b.strength as batch_strength
        FROM timetable_slots ts
        LEFT JOIN subjects s ON ts.subject_id = s.id
        LEFT JOIN faculty f ON ts.faculty_id = f.id
        LEFT JOIN classrooms c ON ts.classroom_id = c.id
        LEFT JOIN batches b ON ts.batch_id = b.id
        WHERE ts.timetable_id = ?
    ''', (timetable_id,))
    slots = cursor.fetchall()
    
    # Perform analysis
    analysis = {
        'total_slots': len(slots),
        'faculty_workload': {},
        'classroom_utilization': {},
        'batch_schedule': {},
        'constraint_violations': []
    }
    
    # Faculty workload analysis
    faculty_hours = {}
    for slot in slots:
        faculty_id = slot['faculty_id']
        if faculty_id not in faculty_hours:
            faculty_hours[faculty_id] = 0
        faculty_hours[faculty_id] += 1
    
    for faculty_id, hours in faculty_hours.items():
        faculty_name = next((s['faculty_name'] for s in slots if s['faculty_id'] == faculty_id), 'Unknown')
        analysis['faculty_workload'][faculty_name] = hours
    
    # Classroom utilization analysis
    classroom_usage = {}
    for slot in slots:
        classroom_id = slot['classroom_id']
        if classroom_id not in classroom_usage:
            classroom_usage[classroom_id] = 0
        classroom_usage[classroom_id] += 1
    
    for classroom_id, usage in classroom_usage.items():
        classroom_name = next((s['classroom_name'] for s in slots if s['classroom_id'] == classroom_id), 'Unknown')
        analysis['classroom_utilization'][classroom_name] = usage
    
    # Check for constraint violations
    # 1. Classroom capacity violations
    for slot in slots:
        if slot['batch_strength'] > slot.get('classroom_capacity', 0):
            analysis['constraint_violations'].append({
                'type': 'classroom_capacity',
                'message': f"Batch {slot['batch_name']} exceeds classroom {slot['classroom_name']} capacity",
                'severity': 'high'
            })
    
    conn.close()
    
    return jsonify(analysis)