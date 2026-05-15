from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from app import db
from app.utils import log_audit

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def home():
    if 'user_id' in session:
        if session.get('role') == 'hr':
            return redirect(url_for('hr.dashboard'))
        else:
            return redirect(url_for('employee.dashboard'))
    return render_template('auth/index.html')

@auth_bp.route('/login/hr', methods=['GET', 'POST'])
def hr_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = db.employees.find_one({'email': email, 'role': 'hr'})
        
        if user and (user.get('password') == password or check_password_hash(user.get('password', ''), password)):
            session['user_id'] = str(user['_id'])
            session['role'] = 'hr'
            session['name'] = user.get('name', 'HR Manager')
            flash('HR Login successful!', 'success')
            return redirect(url_for('hr.dashboard'))
            
        flash('Invalid email or password for HR', 'danger')
    return render_template('auth/hr_login.html')

@auth_bp.route('/login/employee', methods=['GET', 'POST'])
def emp_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = db.employees.find_one({'email': email, 'role': 'employee'})
        
        if user and (user.get('password') == password or check_password_hash(user.get('password', ''), password)):
            session['user_id'] = str(user['_id'])
            session['role'] = 'employee'
            session['name'] = user.get('name', 'Employee')
            flash('Login successful!', 'success')
            return redirect(url_for('employee.dashboard'))
            
        flash('Invalid email or password for Employee', 'danger')
    return render_template('auth/emp_login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        
        # Check if already exists
        if db.employees.find_one({'email': email}):
            flash('Email is already registered. Please login.', 'danger')
            return redirect(url_for('auth.emp_login'))
            
        employee = {
            'name': request.form['name'],
            'email': email,
            'department': request.form['department'],
            'designation': request.form['designation'],
            'role': 'employee',
            'password': request.form['password'], # Highly recommended to hash this in production
            'salary_template_id': None
        }
        res = db.employees.insert_one(employee)
        log_audit("Employee Self-Registration", f"Account created for {employee['name']}", str(res.inserted_id))
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('auth.emp_login'))
    return render_template('auth/register.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('auth.home'))
