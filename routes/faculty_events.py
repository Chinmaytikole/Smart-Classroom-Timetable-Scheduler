# routes/faculty_events.py - Faculty Events Management
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

faculty_events_bp = Blueprint('faculty_events', __name__)

def faculty_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'teacher_id' not in session:
            flash('Faculty access required.', 'error')
            return redirect(url_for('teacher_login'))
        return f(*args, **kwargs)
    return decorated_function

@faculty_events_bp.route('/faculty/events')
@faculty_required
def faculty_events():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    teacher_id = session['teacher_id']
    
    # Get faculty-specific events (events they're assigned to or created by them)
    cursor.execute('''
        SELECT e.*, u.username as created_by_username, 
               f.name as faculty_name, te.is_attending
        FROM events e
        LEFT JOIN users u ON e.created_by = u.id
        LEFT JOIN teacher_events te ON e.id = te.event_id AND te.teacher_id = ?
        LEFT JOIN faculty f ON f.id = ?
        WHERE e.id IN (
            SELECT event_id FROM teacher_events WHERE teacher_id = ?
            UNION
            SELECT id FROM events WHERE created_by = ?
        )
        ORDER BY e.event_date, e.start_time
    ''', (teacher_id, teacher_id, teacher_id, session.get('user_id', session.get('teacher_id'))))
    
    events = cursor.fetchall()
    
    # Get upcoming events (next 7 days)
    upcoming_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT e.*, u.username as created_by_username, te.is_attending
        FROM events e
        LEFT JOIN users u ON e.created_by = u.id
        LEFT JOIN teacher_events te ON e.id = te.event_id AND te.teacher_id = ?
        WHERE e.event_date BETWEEN date('now') AND ? 
        AND e.id IN (
            SELECT event_id FROM teacher_events WHERE teacher_id = ?
            UNION
            SELECT id FROM events WHERE created_by = ?
        )
        ORDER BY e.event_date, e.start_time
    ''', (teacher_id, upcoming_date, teacher_id, session.get('user_id', session.get('teacher_id'))))
    
    upcoming_events = cursor.fetchall()
    
    # Convert to dictionaries and calculate days remaining
    now = datetime.now().date()
    events_list = []
    upcoming_events_list = []
    
    for event in events:
        event_dict = dict(event)
        if event_dict['event_date']:
            event_date = datetime.strptime(event_dict['event_date'], '%Y-%m-%d').date()
            event_dict['days_remaining'] = (event_date - now).days
        else:
            event_dict['days_remaining'] = None
        events_list.append(event_dict)
    
    for event in upcoming_events:
        event_dict = dict(event)
        if event_dict['event_date']:
            event_date = datetime.strptime(event_dict['event_date'], '%Y-%m-%d').date()
            event_dict['days_remaining'] = (event_date - now).days
        else:
            event_dict['days_remaining'] = None
        upcoming_events_list.append(event_dict)
    
    conn.close()
    
    return render_template('faculty_events.html', 
                         events=events_list, 
                         upcoming_events=upcoming_events_list)

@faculty_events_bp.route('/faculty/events/attendance/<int:event_id>', methods=['POST'])
@faculty_required
def update_attendance(event_id):
    try:
        is_attending = request.json.get('is_attending', False)
        teacher_id = session['teacher_id']
        
        conn = sqlite3.connect('timetable.db')
        cursor = conn.cursor()
        
        # First, verify the teacher is assigned to this event
        cursor.execute('SELECT * FROM teacher_events WHERE event_id = ? AND teacher_id = ?', 
                      (event_id, teacher_id))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute('''
                UPDATE teacher_events SET is_attending = ?, updated_at = datetime('now')
                WHERE event_id = ? AND teacher_id = ?
            ''', (is_attending, event_id, teacher_id))
        else:
            # If not assigned, check if they have permission to attend
            cursor.execute('''
                SELECT * FROM events WHERE id = ? AND created_by = ?
            ''', (event_id, session.get('user_id', session.get('teacher_id'))))
            event_exists = cursor.fetchone()
            
            if event_exists:
                cursor.execute('''
                    INSERT INTO teacher_events (event_id, teacher_id, is_attending, created_at)
                    VALUES (?, ?, ?, datetime('now'))
                ''', (event_id, teacher_id, is_attending))
            else:
                return jsonify({'success': False, 'message': 'You are not assigned to this event'})
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Attendance updated successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error updating attendance: {str(e)}'})

@faculty_events_bp.route('/api/faculty/events/calendar')
@faculty_required
def faculty_event_calendar():
    start = request.args.get('start')
    end = request.args.get('end')
    teacher_id = session['teacher_id']
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = '''
        SELECT e.*, u.username as created_by_username, te.is_attending
        FROM events e
        LEFT JOIN users u ON e.created_by = u.id
        LEFT JOIN teacher_events te ON e.id = te.event_id AND te.teacher_id = ?
        WHERE e.id IN (
            SELECT event_id FROM teacher_events WHERE teacher_id = ?
            UNION
            SELECT id FROM events WHERE created_by = ?
        )
    '''
    
    params = [teacher_id, teacher_id, session.get('user_id', teacher_id)]
    
    if start:
        query += ' AND e.event_date >= ?'
        params.append(start)
    
    if end:
        query += ' AND e.event_date <= ?'
        params.append(end)
    
    query += ' ORDER BY e.event_date, e.start_time'
    
    cursor.execute(query, params)
    events = cursor.fetchall()
    
    conn.close()
    
    # Format for FullCalendar
    calendar_events = []
    for event in events:
        # Handle NULL is_attending values
        is_attending = bool(event['is_attending']) if event['is_attending'] is not None else False
        color = '#28a745' if is_attending else '#ffc107'
        
        calendar_events.append({
            'id': event['id'],
            'title': event['title'],
            'start': f"{event['event_date']}T{event['start_time']}",
            'end': f"{event['event_date']}T{event['end_time']}",
            'backgroundColor': color,
            'borderColor': color,
            'extendedProps': {
                'location': event['location'] or '',
                'description': event['description'] or '',
                'is_attending': is_attending,
                'type': 'faculty_event'
            }
        })
    
    return jsonify(calendar_events)