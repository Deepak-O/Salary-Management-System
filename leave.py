from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from bson.objectid import ObjectId
from app import db
from app.utils import log_audit
import datetime

leave_bp = Blueprint('leave', __name__)

@leave_bp.before_request
def check_auth():
    if not session.get('user_id'):
        flash('Unauthorized access', 'danger')
        return redirect(url_for('auth.login'))

@leave_bp.route('/apply', methods=['GET', 'POST'])
def apply_leave():
    if request.method == 'POST':
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        reason = request.form['reason']
        
        # Calculate days (simple estimate, assuming dates are YYYY-MM-DD)
        s_date = datetime.datetime.strptime(start_date, '%Y-%m-%d')
        e_date = datetime.datetime.strptime(end_date, '%Y-%m-%d')
        days = (e_date - s_date).days + 1
        
        leave_entry = {
            "employee_id": str(session.get('user_id')),
            "employee_name": session.get('name', 'Employee'),
            "start_date": start_date,
            "end_date": end_date,
            "days": max(days, 1),
            "reason": reason,
            "status": "Pending",
            "applied_on": datetime.datetime.now()
        }
        db.leaves.insert_one(leave_entry)
        log_audit("Leave Applied", f"Leave applied from {start_date} to {end_date}", session.get('user_id'))
        flash('Leave application submitted successfully', 'success')
        return redirect(url_for('employee.dashboard'))
        
    return render_template('leave/apply.html')

@leave_bp.route('/manage')
def manage_leaves():
    if session.get('role') != 'hr':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('auth.login'))
        
    leaves = list(db.leaves.find().sort('applied_on', -1))
    return render_template('leave/manage.html', leaves=leaves)

@leave_bp.route('/approve/<id>')
def approve_leave(id):
    if session.get('role') != 'hr': return redirect(url_for('auth.login'))
    db.leaves.update_one({'_id': ObjectId(id)}, {'$set': {'status': 'Approved'}})
    log_audit("Leave Approved", f"Leave {id} approved", session.get('user_id'))
    flash('Leave approved', 'success')
    return redirect(url_for('leave.manage_leaves'))

@leave_bp.route('/reject/<id>')
def reject_leave(id):
    if session.get('role') != 'hr': return redirect(url_for('auth.login'))
    db.leaves.update_one({'_id': ObjectId(id)}, {'$set': {'status': 'Rejected'}})
    log_audit("Leave Rejected", f"Leave {id} rejected", session.get('user_id'))
    flash('Leave rejected', 'info')
    return redirect(url_for('leave.manage_leaves'))
