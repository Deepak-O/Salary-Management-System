from flask import Blueprint, render_template, request, redirect, url_for, session, flash, Response
from bson.objectid import ObjectId
from app import db
from app.utils import log_audit, send_mock_email
import datetime
import csv
import io

hr_bp = Blueprint('hr', __name__)

def is_hr():
    return session.get('role') == 'hr'

@hr_bp.before_request
def check_hr():
    if not is_hr():
        flash('Unauthorized access', 'danger')
        return redirect(url_for('auth.login'))

@hr_bp.route('/dashboard')
def dashboard():
    search_name = request.args.get('name', '').lower()
    search_dept = request.args.get('department', '')
    
    query = {'role': 'employee'}
    if search_name:
        query['name'] = {'$regex': search_name, '$options': 'i'}
    if search_dept:
        query['department'] = search_dept
        
    employees = list(db.employees.find(query))
    all_depts = db.employees.distinct('department', {'role': 'employee'})
    
    # Dashboard Stats
    total_employees = db.employees.count_documents({'role': 'employee'})
    current_month = datetime.datetime.now().strftime("%m/%Y")
    recent_payrolls = list(db.payslips.find({'period': current_month}))
    total_payroll_cost = sum(p['net_pay'] for p in recent_payrolls)
    recent_payslips_count = len(recent_payrolls)
    
    return render_template('hr/dashboard.html', 
                           employees=employees, 
                           departments=all_depts,
                           search_name=search_name,
                           search_dept=search_dept,
                           total_emp=total_employees,
                           total_cost=total_payroll_cost,
                           recent_count=recent_payslips_count)

@hr_bp.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    if request.method == 'POST':
        employee = {
            'name': request.form['name'],
            'email': request.form['email'],
            'department': request.form['department'],
            'designation': request.form['designation'],
            'role': 'employee',
            'password': 'password123',
            'salary_template_id': None
        }
        res = db.employees.insert_one(employee)
        log_audit("Added Employee", f"Created employee {employee['name']}", session.get('user_id'))
        flash('Employee registered successfully', 'success')
        return redirect(url_for('hr.dashboard'))
    return render_template('hr/add_employee.html')

@hr_bp.route('/delete_employee/<id>')
def delete_employee(id):
    emp = db.employees.find_one({'_id': ObjectId(id)})
    if emp:
        db.employees.delete_one({'_id': ObjectId(id)})
        log_audit("Deleted Employee", f"Deleted employee {emp['name']}", session.get('user_id'))
        flash('Employee deleted successfully', 'success')
    return redirect(url_for('hr.dashboard'))

@hr_bp.route('/edit_employee/<id>', methods=['GET', 'POST'])
def edit_employee(id):
    employee = db.employees.find_one({'_id': ObjectId(id)})
    if request.method == 'POST':
        db.employees.update_one({'_id': ObjectId(id)}, {'$set': {
            'department': request.form['department'],
            'designation': request.form['designation'],
            'name': request.form['name'],
            'email': request.form['email']
        }})
        log_audit("Edited Employee", f"Updated details for {request.form['name']}", session.get('user_id'))
        flash('Employee updated successfully', 'success')
        return redirect(url_for('hr.dashboard'))
    return render_template('hr/edit_employee.html', employee=employee)

@hr_bp.route('/templates', methods=['GET', 'POST'])
def templates():
    if request.method == 'POST':
        template = {
            'name': request.form['name'],
            'basic_pay': float(request.form['basic_pay']),
            'allowances': float(request.form['allowances']),
            'deductions': float(request.form['deductions'])
        }
        db.templates.insert_one(template)
        log_audit("Created Template", f"Template {template['name']}", session.get('user_id'))
        flash('Template created', 'success')
        return redirect(url_for('hr.templates'))
    templates = list(db.templates.find())
    return render_template('hr/templates.html', templates=templates)

@hr_bp.route('/delete_template/<id>')
def delete_template(id):
    db.templates.delete_one({'_id': ObjectId(id)})
    flash('Template deleted', 'info')
    return redirect(url_for('hr.templates'))

@hr_bp.route('/assign_template/<emp_id>', methods=['GET', 'POST'])
def assign_template(emp_id):
    employee = db.employees.find_one({'_id': ObjectId(emp_id)})
    templates = list(db.templates.find())
    if request.method == 'POST':
        template_id = request.form['template_id']
        db.employees.update_one({'_id': ObjectId(emp_id)}, {'$set': {'salary_template_id': template_id}})
        flash('Template assigned successfully', 'success')
        return redirect(url_for('hr.dashboard'))
    return render_template('hr/assign_template.html', employee=employee, templates=templates)

@hr_bp.route('/calculate_salary/<emp_id>')
def calculate_salary(emp_id):
    employee = db.employees.find_one({'_id': ObjectId(emp_id)})
    if not employee.get('salary_template_id'):
        flash('No template assigned', 'danger')
        return redirect(url_for('hr.dashboard'))
    template = db.templates.find_one({'_id': ObjectId(employee['salary_template_id'])})
    net_pay = template['basic_pay'] + template['allowances'] - template['deductions']
    return render_template('hr/calculate_salary.html', employee=employee, template=template, net_pay=net_pay)

@hr_bp.route('/generate_payroll', methods=['GET', 'POST'])
def generate_payroll():
    if request.method == 'POST':
        period = request.form['period']
        working_days = int(request.form.get('working_days', 30))
        
        employees = list(db.employees.find({'role': 'employee'}))
        count = 0
        for emp in employees:
            if emp.get('salary_template_id'):
                temp = db.templates.find_one({'_id': ObjectId(emp['salary_template_id'])})
                if temp:
                    # Calculate leave days
                    approved_leaves = list(db.leaves.find({'employee_id': str(emp['_id']), 'status': 'Approved'}))
                    leave_days = sum(l['days'] for l in approved_leaves)
                    attended_days = working_days - leave_days
                    if attended_days < 0: attended_days = 0
                    
                    attendance_multiplier = attended_days / working_days if working_days > 0 else 1
                    
                    base_net = temp['basic_pay'] + temp['allowances'] - temp['deductions']
                    final_net = base_net * attendance_multiplier
                    
                    payslip = {
                        'employee_id': str(emp['_id']),
                        'employee_name': emp['name'],
                        'employee_email': emp.get('email'),
                        'period': period,
                        'basic_pay': temp['basic_pay'],
                        'allowances': temp['allowances'],
                        'deductions': temp['deductions'],
                        'leave_days': leave_days,
                        'net_pay': final_net,
                        'generated_date': datetime.datetime.now()
                    }
                    db.payslips.insert_one(payslip)
                    count += 1
        db.payrolls.insert_one({'period': period, 'generated_at': datetime.datetime.now(), 'processed_by': session.get('user_id')})
        log_audit("Generated Payroll", f"Payroll for period {period}", session.get('user_id'))
        flash(f'Payroll generated for {count} employees. Processed Leaves.', 'success')
        return redirect(url_for('hr.payroll_reports'))
    return render_template('hr/generate_payroll.html')

@hr_bp.route('/payroll_reports')
def payroll_reports():
    period = request.args.get('period')
    query = {}
    if period:
        query['period'] = period
    reports = list(db.payslips.find(query))
    periods = db.payrolls.distinct('period')
    return render_template('hr/payroll_reports.html', reports=reports, periods=periods, selected_period=period)

@hr_bp.route('/email_payslip/<payslip_id>')
def email_payslip(payslip_id):
    payslip = db.payslips.find_one({'_id': ObjectId(payslip_id)})
    if payslip and payslip.get('employee_email'):
        subject = f"Your Payslip for {payslip['period']}"
        body = f"Hello {payslip['employee_name']},\nYour net pay for {payslip['period']} is ₹{payslip['net_pay']:.2f}. You had {payslip.get('leave_days', 0)} days of leave deducted.\nPlease login to download the full PDF."
        send_mock_email(payslip['employee_email'], subject, body)
        log_audit("Emailed Payslip", f"Sent to {payslip['employee_email']}", session.get('user_id'))
        flash('Payslip emailed successfully! (Check terminal for mock output)', 'success')
    else:
        flash('Failed to send email. Check employee email address.', 'danger')
    return redirect(url_for('hr.payroll_reports'))

@hr_bp.route('/export_employees')
def export_employees():
    employees = list(db.employees.find({'role': 'employee'}))
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Name', 'Email', 'Department', 'Designation'])
    for e in employees:
        cw.writerow([str(e['_id']), e.get('name'), e.get('email'), e.get('department'), e.get('designation')])
    return Response(si.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment;filename=employees.csv'})

@hr_bp.route('/export_payroll')
def export_payroll():
    payslips = list(db.payslips.find())
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Employee Name', 'Period', 'Basic Pay', 'Allowances', 'Deductions', 'Leave Days', 'Net Pay'])
    for p in payslips:
        cw.writerow([str(p['_id']), p.get('employee_name'), p.get('period'), p.get('basic_pay'), p.get('allowances'), p.get('deductions'), p.get('leave_days', 0), p.get('net_pay')])
    return Response(si.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment;filename=payroll.csv'})

@hr_bp.route('/audits')
def audits():
    records = list(db.audits.find().sort('timestamp', -1))
    return render_template('hr/audits.html', audits=records)

@hr_bp.route('/analytics')
def analytics():
    # Gather data for Chart.js
    payslips = list(db.payslips.find())
    
    # Monthly cost map
    monthly_costs = {}
    dept_costs = {}
    
    for p in payslips:
        pd = p['period']
        monthly_costs[pd] = monthly_costs.get(pd, 0) + p['net_pay']
        
        # Dept cost
        emp = db.employees.find_one({'_id': ObjectId(p['employee_id'])})
        if emp:
            dept = emp.get('department', 'Unknown')
            dept_costs[dept] = dept_costs.get(dept, 0) + p['net_pay']
            
    months = list(monthly_costs.keys())
    costs = list(monthly_costs.values())
    depts = list(dept_costs.keys())
    d_costs = list(dept_costs.values())
    
    return render_template('hr/analytics.html', 
                           months=months, costs=costs, 
                           depts=depts, d_costs=d_costs)
