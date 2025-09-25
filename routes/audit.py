# routes/audit.py - Enhanced version
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

audit_bp = Blueprint('audit', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@audit_bp.route('/audit-logs')
@admin_required
def audit_logs():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    user_id = request.args.get('user_id')
    action = request.args.get('action')
    table_name = request.args.get('table_name')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Build query with filters
    query = '''
        SELECT a.*, u.username, u.full_name
        FROM audit_logs a
        LEFT JOIN users u ON a.user_id = u.id
        WHERE 1=1
    '''
    
    params = []
    
    if user_id:
        query += ' AND a.user_id = ?'
        params.append(user_id)
    
    if action:
        query += ' AND a.action = ?'
        params.append(action)
    
    if table_name:
        query += ' AND a.table_name = ?'
        params.append(table_name)
    
    if start_date:
        query += ' AND a.created_at >= ?'
        params.append(start_date)
    
    if end_date:
        query += ' AND a.created_at <= ?'
        params.append(end_date + ' 23:59:59')
    
    query += ' ORDER BY a.created_at DESC'
    
    # Get total count
    count_query = 'SELECT COUNT(*) as total FROM (' + query + ')'
    cursor.execute(count_query, params)
    total = cursor.fetchone()['total']
    
    # Add pagination
    query += ' LIMIT ? OFFSET ?'
    params.extend([per_page, (page - 1) * per_page])
    
    cursor.execute(query, params)
    logs = cursor.fetchall()
    
    # Get users for filter
    cursor.execute('SELECT id, username, full_name FROM users ORDER BY username')
    users = cursor.fetchall()
    
    # Get distinct actions and tables
    cursor.execute('SELECT DISTINCT action FROM audit_logs ORDER BY action')
    actions = [row['action'] for row in cursor.fetchall()]
    
    cursor.execute('SELECT DISTINCT table_name FROM audit_logs ORDER BY table_name')
    tables = [row['table_name'] for row in cursor.fetchall()]
    
    conn.close()
    
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('audit_logs.html',
                         logs=logs,
                         users=users,
                         actions=actions,
                         tables=tables,
                         page=page,
                         total_pages=total_pages,
                         user_id=user_id,
                         action=action,
                         table_name=table_name,
                         start_date=start_date,
                         end_date=end_date)

@audit_bp.route('/api/audit-logs/stats')
@admin_required
def audit_stats():
    period = request.args.get('period', 'day')  # day, week, month
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if period == 'day':
        # Last 24 hours by hour
        query = '''
            SELECT strftime('%Y-%m-%d %H:00:00', created_at) as hour,
                   COUNT(*) as count
            FROM audit_logs
            WHERE created_at >= datetime('now', '-1 day')
            GROUP BY hour
            ORDER BY hour
        '''
    elif period == 'week':
        # Last 7 days by day
        query = '''
            SELECT date(created_at) as day,
                   COUNT(*) as count
            FROM audit_logs
            WHERE created_at >= date('now', '-7 days')
            GROUP BY day
            ORDER BY day
        '''
    else:  # month
        # Last 30 days by day
        query = '''
            SELECT date(created_at) as day,
                   COUNT(*) as count
            FROM audit_logs
            WHERE created_at >= date('now', '-30 days')
            GROUP BY day
            ORDER BY day
        '''
    
    cursor.execute(query)
    data = cursor.fetchall()
    
    # Top actions
    cursor.execute('''
        SELECT action, COUNT(*) as count
        FROM audit_logs
        WHERE created_at >= datetime('now', '-1 day')
        GROUP BY action
        ORDER BY count DESC
        LIMIT 10
    ''')
    top_actions = cursor.fetchall()
    
    # Top users
    cursor.execute('''
        SELECT u.username, COUNT(*) as count
        FROM audit_logs a
        LEFT JOIN users u ON a.user_id = u.id
        WHERE a.created_at >= datetime('now', '-1 day')
        GROUP BY a.user_id
        ORDER BY count DESC
        LIMIT 10
    ''')
    top_users = cursor.fetchall()
    
    conn.close()
    
    return jsonify({
        'timeline': [dict(row) for row in data],
        'top_actions': [dict(row) for row in top_actions],
        'top_users': [dict(row) for row in top_users]
    })

@audit_bp.route('/api/audit-logs/export')
@admin_required
def export_audit_logs():
    format = request.args.get('format', 'csv')
    user_id = request.args.get('user_id')
    action = request.args.get('action')
    table_name = request.args.get('table_name')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Build query with filters
    query = '''
        SELECT a.*, u.username, u.full_name
        FROM audit_logs a
        LEFT JOIN users u ON a.user_id = u.id
        WHERE 1=1
    '''
    
    params = []
    
    if user_id:
        query += ' AND a.user_id = ?'
        params.append(user_id)
    
    if action:
        query += ' AND a.action = ?'
        params.append(action)
    
    if table_name:
        query += ' AND a.table_name = ?'
        params.append(table_name)
    
    if start_date:
        query += ' AND a.created_at >= ?'
        params.append(start_date)
    
    if end_date:
        query += ' AND a.created_at <= ?'
        params.append(end_date + ' 23:59:59')
    
    query += ' ORDER BY a.created_at DESC'
    
    cursor.execute(query, params)
    logs = cursor.fetchall()
    
    conn.close()
    
    if format == 'csv':
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Timestamp', 'User', 'Action', 'Table', 'Record ID', 'Changes', 'IP Address'])
        
        # Write data
        for log in logs:
            writer.writerow([
                log['created_at'],
                log['username'] or 'System',
                log['action'],
                log['table_name'],
                log['record_id'] or '',
                log['changes'] or '',
                log['ip_address'] or ''
            ])
        
        output.seek(0)
        return output.getvalue(), 200, {
            'Content-Type': 'text/csv',
            'Content-Disposition': 'attachment; filename=audit_logs.csv'
        }
    
    else:
        return jsonify([dict(log) for log in logs])