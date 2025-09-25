
# routes/reports.py - Enhanced version
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
import sqlite3
from datetime import datetime, timedelta
import json
from functools import wraps

reports_bp = Blueprint('reports', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@reports_bp.route('/reports')
@admin_required
def reports():
    report_type = request.args.get('type', 'usage')
    period = request.args.get('period', 'week')
    department_id = request.args.get('department_id')
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get departments for filter
    cursor.execute('SELECT * FROM departments ORDER BY name')
    departments = cursor.fetchall()
    
    conn.close()
    
    return render_template('reports.html',
                         report_type=report_type,
                         period=period,
                         departments=departments,
                         department_id=department_id)

@reports_bp.route('/api/reports/usage')
@admin_required
def usage_report():
    period = request.args.get('period', 'week')
    department_id = request.args.get('department_id')
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if period == 'week':
        # Classroom usage by day of week
        query = '''
            SELECT ts.day, 
                   COUNT(*) as total_classes,
                   COUNT(DISTINCT ts.classroom_id) as unique_classrooms,
                   COUNT(DISTINCT ts.faculty_id) as unique_faculty,
                   COUNT(DISTINCT ts.batch_id) as unique_batches
            FROM timetable_slots ts
            LEFT JOIN batches b ON ts.batch_id = b.id
            WHERE 1=1
        '''
        
        params = []
        
        if department_id:
            query += ' AND b.department_id = ?'
            params.append(department_id)
        
        query += ' GROUP BY ts.day ORDER BY ts.day'
        
        cursor.execute(query, params)
        data = cursor.fetchall()
        
    elif period == 'month':
        # Monthly usage trends
        query = '''
            SELECT strftime('%Y-%m', t.created_at) as month,
                   COUNT(DISTINCT t.id) as timetables_generated,
                   COUNT(DISTINCT ts.id) as total_classes_scheduled
            FROM timetables t
            LEFT JOIN timetable_slots ts ON t.id = ts.timetable_id
            WHERE 1=1
        '''
        
        params = []
        
        if department_id:
            query += ' AND t.department_id = ?'
            params.append(department_id)
        
        query += ' GROUP BY month ORDER BY month'
        
        cursor.execute(query, params)
        data = cursor.fetchall()
    
    conn.close()
    
    return jsonify([dict(row) for row in data])

@reports_bp.route('/api/reports/faculty-workload')
@admin_required
def faculty_workload_report():
    period = request.args.get('period', 'week')
    department_id = request.args.get('department_id')
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = '''
        SELECT f.id, f.name, 
               COUNT(ts.id) as total_classes,
               COUNT(DISTINCT ts.subject_id) as unique_subjects,
               COUNT(DISTINCT ts.batch_id) as unique_batches,
               AVG(fl.avg_leaves_per_month) as avg_leaves
        FROM faculty f
        LEFT JOIN timetable_slots ts ON f.id = ts.faculty_id
        LEFT JOIN faculty_leaves fl ON f.id = fl.faculty_id
        LEFT JOIN batches b ON ts.batch_id = b.id
        WHERE 1=1
    '''
    
    params = []
    
    if department_id:
        query += ' AND b.department_id = ?'
        params.append(department_id)
    
    query += ' GROUP BY f.id, f.name ORDER BY total_classes DESC'
    
    cursor.execute(query, params)
    data = cursor.fetchall()
    
    conn.close()
    
    return jsonify([dict(row) for row in data])

@reports_bp.route('/api/reports/classroom-utilization')
@admin_required
def classroom_utilization_report():
    period = request.args.get('period', 'week')
    department_id = request.args.get('department_id')
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = '''
        SELECT c.id, c.name, c.capacity, c.type,
               COUNT(ts.id) as total_classes,
               COUNT(DISTINCT ts.day) as days_used,
               COUNT(DISTINCT ts.faculty_id) as unique_faculty,
               COUNT(DISTINCT ts.batch_id) as unique_batches,
               MAX(b.strength) as max_occupancy
        FROM classrooms c
        LEFT JOIN timetable_slots ts ON c.id = ts.classroom_id
        LEFT JOIN batches b ON ts.batch_id = b.id
        WHERE 1=1
    '''
    
    params = []
    
    if department_id:
        query += ' AND b.department_id = ?'
        params.append(department_id)
    
    query += ' GROUP BY c.id, c.name, c.capacity, c.type ORDER BY total_classes DESC'
    
    cursor.execute(query, params)
    data = cursor.fetchall()
    
    # Calculate utilization percentage
    for row in data:
        if row['capacity'] and row['max_occupancy']:
            row['utilization'] = min(100, (row['max_occupancy'] / row['capacity']) * 100)
        else:
            row['utilization'] = 0
    
    conn.close()
    
    return jsonify([dict(row) for row in data])

@reports_bp.route('/api/reports/timetable-quality')
@admin_required
def timetable_quality_report():
    department_id = request.args.get('department_id')
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = '''
        SELECT t.id, t.name, t.fitness_score, t.created_at,
               d.name as department_name,
               u.username as generated_by,
               COUNT(ts.id) as total_slots,
               COUNT(DISTINCT ts.faculty_id) as unique_faculty,
               COUNT(DISTINCT ts.classroom_id) as unique_classrooms,
               COUNT(DISTINCT ts.batch_id) as unique_batches
        FROM timetables t
        LEFT JOIN departments d ON t.department_id = d.id
        LEFT JOIN users u ON t.generated_by = u.id
        LEFT JOIN timetable_slots ts ON t.id = ts.timetable_id
        WHERE 1=1
    '''
    
    params = []
    
    if department_id:
        query += ' AND t.department_id = ?'
        params.append(department_id)
    
    query += ' GROUP BY t.id, t.name, t.fitness_score, t.created_at, d.name, u.username ORDER BY t.created_at DESC'
    
    cursor.execute(query, params)
    data = cursor.fetchall()
    
    conn.close()
    
    return jsonify([dict(row) for row in data])

@reports_bp.route('/api/reports/export')
@admin_required
def export_report():
    report_type = request.args.get('type', 'usage')
    format = request.args.get('format', 'csv')
    period = request.args.get('period', 'week')
    department_id = request.args.get('department_id')
    
    # Get data based on report type
    if report_type == 'usage':
        data = usage_report().get_json()
        filename = f'usage_report_{period}.{format}'
    elif report_type == 'faculty-workload':
        data = faculty_workload_report().get_json()
        filename = f'faculty_workload_report.{format}'
    elif report_type == 'classroom-utilization':
        data = classroom_utilization_report().get_json()
        filename = f'classroom_utilization_report.{format}'
    elif report_type == 'timetable-quality':
        data = timetable_quality_report().get_json()
        filename = f'timetable_quality_report.{format}'
    else:
        return jsonify({'error': 'Invalid report type'}), 400
    
    if format == 'csv':
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
        return output.getvalue(), 200, {
            'Content-Type': 'text/csv',
            'Content-Disposition': f'attachment; filename={filename}'
        }
    
    else:
        return jsonify(data)