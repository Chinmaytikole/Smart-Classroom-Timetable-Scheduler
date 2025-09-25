# routes/events.py - Enhanced version
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
import sqlite3
from datetime import datetime
from functools import wraps

events_bp = Blueprint('events', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@events_bp.route('/events')
@login_required
def events():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT e.*, u.username as created_by_username
        FROM events e
        LEFT JOIN users u ON e.created_by = u.id
        ORDER BY e.event_date, e.start_time
    ''')
    events = cursor.fetchall()
    
    # Convert Row objects to dictionaries and calculate days remaining
    now = datetime.now().date()
    events_list = []
    
    for event in events:
        # Convert sqlite3.Row to dictionary
        event_dict = dict(event)
        
        # Calculate days remaining
        event_date = datetime.strptime(event_dict['event_date'], '%Y-%m-%d').date()
        days_remaining = (event_date - now).days
        event_dict['days_remaining'] = days_remaining
        
        events_list.append(event_dict)
    
    conn.close()
    
    return render_template('events.html', events=events_list)

@events_bp.route('/events/create', methods=['GET', 'POST'])
@login_required
def create_event():
    if request.method == 'POST':
        try:
            title = request.form['title']
            description = request.form.get('description', '')
            event_date = request.form['event_date']
            start_time = request.form['start_time']
            end_time = request.form['end_time']
            location = request.form.get('location', '')
            
            conn = sqlite3.connect('timetable.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO events 
                (title, description, event_date, start_time, end_time, location, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (title, description, event_date, start_time, end_time, location, session['user_id']))
            
            conn.commit()
            conn.close()
            
            flash('Event created successfully!', 'success')
            return redirect('/events')
            
        except Exception as e:
            flash(f'Error creating event: {str(e)}', 'error')
            return redirect('/events/create')
    
    # GET request - show form
    return render_template('create_event.html')

@events_bp.route('/events/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(id):
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    
    if request.method == 'POST':
        try:
            title = request.form['title']
            description = request.form.get('description', '')
            event_date = request.form['event_date']
            start_time = request.form['start_time']
            end_time = request.form['end_time']
            location = request.form.get('location', '')
            
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE events 
                SET title = ?, description = ?, event_date = ?, start_time = ?, end_time = ?, location = ?
                WHERE id = ?
            ''', (title, description, event_date, start_time, end_time, location, id))
            
            conn.commit()
            flash('Event updated successfully!', 'success')
            
        except Exception as e:
            flash(f'Error updating event: {str(e)}', 'error')
        finally:
            conn.close()
        
        return redirect(url_for('events.events'))
    
    # GET request - show edit form
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM events WHERE id = ?', (id,))
    event = cursor.fetchone()
    
    conn.close()
    
    if not event:
        flash('Event not found.', 'error')
        return redirect(url_for('events.events'))
    
    return render_template('edit_event.html', event=event)

@events_bp.route('/events/<int:id>/delete')
@login_required
def delete_event(id):
    try:
        conn = sqlite3.connect('timetable.db')
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM events WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        
        flash('Event deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting event: {str(e)}', 'error')
    
    return redirect(url_for('events.events'))

@events_bp.route('/api/events/calendar')
@login_required
def event_calendar():
    start = request.args.get('start')
    end = request.args.get('end')
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = '''
        SELECT e.*, u.username as created_by_username
        FROM events e
        LEFT JOIN users u ON e.created_by = u.id
        WHERE 1=1
    '''
    
    params = []
    
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
        calendar_events.append({
            'id': event['id'],
            'title': event['title'],
            'start': f"{event['event_date']}T{event['start_time']}",
            'end': f"{event['event_date']}T{event['end_time']}",
            'backgroundColor': '#28a745',
            'borderColor': '#28a745',
            'extendedProps': {
                'location': event['location'],
                'description': event['description'],
                'type': 'event'
            }
        })
    
    return jsonify(calendar_events)