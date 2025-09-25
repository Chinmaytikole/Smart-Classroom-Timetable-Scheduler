# routes/users.py - Enhanced version
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from functools import wraps

users_bp = Blueprint('users', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        
        if session.get('role') != 'faculty':
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@users_bp.route('/users')
@admin_required
def user_management():
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT u.*, d.name as department_name, f.employee_id, f.name as faculty_name
        FROM users u
        LEFT JOIN departments d ON u.department_id = d.id
        LEFT JOIN faculty f ON u.employee_id = f.employee_id
        ORDER BY u.created_at DESC
    ''')
    users = cursor.fetchall()
    
    cursor.execute('SELECT * FROM departments ORDER BY name')
    departments = cursor.fetchall()
    
    cursor.execute('SELECT employee_id, name FROM faculty ORDER BY name')
    faculty_members = cursor.fetchall()
    
    conn.close()
    
    return render_template('user_management.html', 
                         users=users, 
                         departments=departments,
                         faculty_members=faculty_members)

@users_bp.route('/users/create', methods=['POST'])
@admin_required
def create_user():
    try:
        username = request.form['username']
        password = request.form['password']
        full_name = request.form['full_name']
        role = request.form['role']
        department_id = request.form.get('department_id')
        employee_id = request.form.get('employee_id')  # New field for faculty
        
        if not username or not password:
            flash('Username and password are required.', 'error')
            return redirect(url_for('users.user_management'))
        
        # Validate faculty relationship
        if role == 'faculty' and not employee_id:
            flash('Faculty members must be linked to an employee ID.', 'error')
            return redirect(url_for('users.user_management'))
        
        hashed_password = generate_password_hash(password)
        
        conn = sqlite3.connect('timetable.db')
        cursor = conn.cursor()
        
        # Check if username already exists
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            flash('Username already exists.', 'error')
            conn.close()
            return redirect(url_for('users.user_management'))
        
        # Check if employee_id is already linked to another user (for faculty role)
        if role == 'faculty' and employee_id:
            cursor.execute('SELECT id FROM users WHERE employee_id = ?', (employee_id,))
            if cursor.fetchone():
                flash('This employee is already linked to another user account.', 'error')
                conn.close()
                return redirect(url_for('users.user_management'))
        
        cursor.execute('''
            INSERT INTO users (username, password, full_name, role, department_id, employee_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, hashed_password, full_name, role, department_id, employee_id))
        
        conn.commit()
        conn.close()
        
        flash('User created successfully!', 'success')
        
    except Exception as e:
        flash(f'Error creating user: {str(e)}', 'error')
    
    return redirect(url_for('users.user_management'))

@users_bp.route('/users/update', methods=['POST'])  # Remove <int:id> from route
@admin_required
# @faculty_required
def update_user():  # Remove the id parameter
    try:
        # Get user_id from form data instead of URL parameter
        user_id = request.form['user_id']
        username = request.form['username']
        full_name = request.form['full_name']
        role = request.form['role']
        department_id = request.form.get('department_id') or None
        employee_id = request.form.get('employee_id') or None
        password = request.form.get('password')
        print(user_id, username, full_name, role, department_id, employee_id, password)
        conn = sqlite3.connect('timetable.db')
        cursor = conn.cursor()
        
        # Check if username already exists (excluding current user)
        cursor.execute('SELECT id FROM users WHERE username = ? AND id != ?', (username, user_id))
        if cursor.fetchone():
            flash('Username already exists.', 'error')
            conn.close()
            return redirect(url_for('users.user_management'))
        
        # Check if employee_id is already linked to another user (for faculty role)
        if role == 'faculty' and employee_id:
            cursor.execute('SELECT id FROM users WHERE employee_id = ? AND id != ?', (employee_id, user_id))
            if cursor.fetchone():
                flash('This employee is already linked to another user account.', 'error')
                conn.close()
                return redirect(url_for('users.user_management'))
        
        if password:
            hashed_password = generate_password_hash(password)
            cursor.execute('''
                UPDATE users 
                SET username = ?, password = ?, full_name = ?, role = ?, department_id = ?, employee_id = ?
                WHERE id = ?
            ''', (username, hashed_password, full_name, role, department_id, employee_id, user_id))
        else:
            cursor.execute('''
                UPDATE users 
                SET username = ?, full_name = ?, role = ?, department_id = ?, employee_id = ?
                WHERE id = ?
            ''', (username, full_name, role, department_id, employee_id, user_id))
        
        conn.commit()
        conn.close()
        
        flash('User updated successfully!', 'success')
        
    except Exception as e:
        flash(f'Error updating user: {str(e)}', 'error')
    
    return redirect(url_for('users.user_management'))

@users_bp.route('/users/<int:id>/delete')
@admin_required
def delete_user(id):
    try:
        # Prevent deleting own account
        if id == session['user_id']:
            flash('You cannot delete your own account.', 'error')
            return redirect(url_for('users.user_management'))
        
        conn = sqlite3.connect('timetable.db')
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM users WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        
        flash('User deleted successfully!', 'success')
        
    except Exception as e:
        flash(f'Error deleting user: {str(e)}', 'error')
    
    return redirect(url_for('users.user_management'))

@users_bp.route('/faculty/update-profile', methods=['GET', 'POST'])
def update_faculty_profile():
    # Check if current user is a faculty member
    if session.get('role') != 'faculty' or 'employee_id' not in session:
        flash('Faculty access required.', 'error')
        return redirect(url_for('teacher_dashboard'))
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get current user data
    cursor.execute('''
        SELECT u.*, f.*, d.name as department_name 
        FROM users u
        LEFT JOIN faculty f ON u.employee_id = f.employee_id
        LEFT JOIN departments d ON f.department_id = d.id
        WHERE u.id = ?
    ''', (session['employee_id'],))
    
    user_data = cursor.fetchone()
    
    if request.method == 'POST':
        try:
            username = request.form['username']
            full_name = request.form['full_name']
            password = request.form.get('password')
            
            # Check if username already exists (excluding current user)
            cursor.execute('SELECT id FROM users WHERE username = ? AND id != ?', 
                         (username, session['employee_id']))
            if cursor.fetchone():
                flash('Username already exists.', 'error')
                conn.close()
                return render_template('faculty_edit_profile.html', user=user_data)
            
            if password:
                hashed_password = generate_password_hash(password)
                cursor.execute('''
                    UPDATE users 
                    SET username = ?, password = ?, full_name = ?
                    WHERE id = ?
                ''', (username, hashed_password, full_name, session['employee_id']))
            else:
                cursor.execute('''
                    UPDATE users 
                    SET username = ?, full_name = ?
                    WHERE id = ?
                ''', (username, full_name, session['employee_id']))
            
            conn.commit()
            flash('Profile updated successfully!', 'success')
            
            # Update session data
            session['username'] = username
            session['full_name'] = full_name
            
        except Exception as e:
            flash(f'Error updating profile: {str(e)}', 'error')
    
    conn.close()
    
    # Refresh user data after update
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.*, f.*, d.name as department_name 
        FROM users u
        LEFT JOIN faculty f ON u.employee_id = f.employee_id
        LEFT JOIN departments d ON f.department_id = d.id
        WHERE u.id = ?
    ''', (session['employee_id'],))
    user_data = cursor.fetchone()
    conn.close()
    
    return render_template('faculty_edit_profile.html', user=user_data)

# Add this function to get faculty information
def get_faculty_info(employee_id):
    if not employee_id:
        return None
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT f.*, d.name as department_name 
        FROM faculty f 
        LEFT JOIN departments d ON f.department_id = d.id 
        WHERE f.employee_id = ?
    ''', (employee_id,))
    
    faculty = cursor.fetchone()
    conn.close()
    
    return dict(faculty) if faculty else None

@users_bp.route('/api/users/<int:user_id>/faculty-info')
@admin_required
def get_user_faculty_info(user_id):
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT employee_id FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    
    if user and user['employee_id']:
        faculty_info = get_faculty_info(user['employee_id'])
        conn.close()
        return jsonify(faculty_info)
    
    conn.close()
    return jsonify({'error': 'No faculty information found'}), 404

@users_bp.route('/faculty/profile')
def faculty_profile():
    print(session)
    # Check if current user is a faculty member
    if 'employee_id' not in session or session.get('role') != 'faculty':
        flash('Faculty access required.', 'error')
        return redirect(url_for('teacher_dashboard'))
    
    conn = sqlite3.connect('timetable.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # CORRECTED QUERY: Use employee_id instead of id
    cursor.execute('''
        SELECT u.*, f.*, d.name as department_name 
        FROM users u
        LEFT JOIN faculty f ON u.employee_id = f.employee_id
        LEFT JOIN departments d ON f.department_id = d.id
        WHERE u.employee_id = ?
    ''', (session['employee_id'],))
    
    faculty_data = cursor.fetchone()
    conn.close()
    
    if not faculty_data:
        flash('Faculty profile not found.', 'error')
        return redirect(url_for('teacher_dashboard'))
    
    return render_template('faculty_profile.html', faculty=faculty_data)

@users_bp.route('/faculty/change-password', methods=['GET', 'POST'])
def change_password():
    if 'employee_id' not in session or session.get('role') != 'faculty':
        flash('Faculty access required.', 'error')
        return redirect(url_for('teacher_dashboard'))
    
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('users.change_password'))
        
        conn = sqlite3.connect('timetable.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Verify current password
        cursor.execute('SELECT password FROM users WHERE employee_id = ?', (session['employee_id'],))
        user = cursor.fetchone()
        
        if not user or not check_password_hash(user['password'], current_password):
            flash('Current password is incorrect.', 'error')
            conn.close()
            return redirect(url_for('users.change_password'))
        
        # Update password
        hashed_password = generate_password_hash(new_password)
        cursor.execute('UPDATE users SET password = ? WHERE employee_id = ?', 
                      (hashed_password, session['employee_id']))
        conn.commit()
        conn.close()
        
        flash('Password changed successfully!', 'success')
        return redirect(url_for('users.faculty_profile'))
    
    return render_template('change_password.html')