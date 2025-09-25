# routes/notifications.py - Enhanced version
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
import sqlite3
from functools import wraps

notifications_bp = Blueprint('notifications', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@notifications_bp.route('/notifications')
@login_required
def notifications():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    type_filter = request.args.get('type')
    read_filter = request.args.get('read')
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Build query with filters
    query = '''
        SELECT * FROM notifications
        WHERE user_id = ?
    '''
    
    params = [session['user_id']]
    
    if type_filter:
        query += ' AND type = ?'
        params.append(type_filter)
    
    if read_filter is not None:
        if read_filter == '1':
            query += ' AND is_read = 1'
        else:
            query += ' AND is_read = 0'
    
    query += ' ORDER BY created_at DESC'
    
    # Get total count
    count_query = 'SELECT COUNT(*) as total FROM (' + query + ')'
    cursor.execute(count_query, params)
    total = cursor.fetchone()['total']
    
    # Add pagination
    query += ' LIMIT ? OFFSET ?'
    params.extend([per_page, (page - 1) * per_page])
    
    cursor.execute(query, params)
    notifications = cursor.fetchall()
    
    conn.close()
    
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('notifications.html',
                         notifications=notifications,
                         page=page,
                         total_pages=total_pages,
                         type_filter=type_filter,
                         read_filter=read_filter)

@notifications_bp.route('/api/notifications/mark-read', methods=['POST'])
@login_required
def mark_notifications_read():
    try:
        notification_ids = request.json.get('notification_ids')
        
        conn = sqlite3.connect('timetable.db')
        cursor = conn.cursor()
        
        if notification_ids:
            # Mark specific notifications as read
            placeholders = ','.join(['?'] * len(notification_ids))
            query = f'UPDATE notifications SET is_read = 1 WHERE id IN ({placeholders}) AND user_id = ?'
            cursor.execute(query, notification_ids + [session['user_id']])
        else:
            # Mark all notifications as read
            cursor.execute('UPDATE notifications SET is_read = 1 WHERE user_id = ?', (session['user_id'],))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Notifications marked as read'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error marking notifications as read: {str(e)}'})

@notifications_bp.route('/api/notifications/unread-count')
@login_required
def unread_notifications_count():
    conn = sqlite3.connect('timetable.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0', (session['user_id'],))
    count = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({'count': count})

@notifications_bp.route('/api/notifications/create', methods=['POST'])
def create_notification():
    # This endpoint is for internal use, typically called by other parts of the system
    try:
        user_id = request.json.get('user_id')
        title = request.json.get('title')
        message = request.json.get('message')
        notification_type = request.json.get('type', 'info')
        
        if not user_id or not title or not message:
            return jsonify({'success': False, 'message': 'Missing required fields'})
        
        conn = sqlite3.connect('timetable.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO notifications (user_id, title, message, type)
            VALUES (?, ?, ?, ?)
        ''', (user_id, title, message, notification_type))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Notification created'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error creating notification: {str(e)}'})

@notifications_bp.route('/api/notifications/<int:id>/delete', methods=['DELETE'])
@login_required
def delete_notification(id):
    try:
        conn = sqlite3.connect('timetable.db')
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM notifications WHERE id = ? AND user_id = ?', (id, session['user_id']))
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'success': False, 'message': 'Notification not found or access denied'})
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Notification deleted'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error deleting notification: {str(e)}'})