from flask import Blueprint, render_template, make_response, session, flash, redirect, url_for
from bson.objectid import ObjectId
from app import db
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

employee_bp = Blueprint('employee', __name__)

def is_employee():
    return session.get('role') == 'employee'

@employee_bp.before_request
def check_employee():
    if not is_employee():
        flash('Unauthorized access', 'danger')
        return redirect(url_for('auth.login'))

@employee_bp.route('/dashboard')
def dashboard():
    user_id = session.get('user_id')
    history = list(db.payslips.find({'employee_id': str(user_id)}).sort('generated_date', -1))
    leaves = list(db.leaves.find({'employee_id': str(user_id)}).sort('applied_on', -1))
    
    employee_data = db.employees.find_one({'_id': ObjectId(user_id)})
    template_data = None
    if employee_data and employee_data.get('salary_template_id'):
        template_data = db.templates.find_one({'_id': ObjectId(employee_data['salary_template_id'])})
        
    return render_template('employee/dashboard.html', history=history, employee=employee_data, template=template_data, leaves=leaves)

@employee_bp.route('/download_payslip/<payslip_id>')
def download_payslip(payslip_id):
    payslip = db.payslips.find_one({'_id': ObjectId(payslip_id), 'employee_id': str(session.get('user_id'))})
    if not payslip:
        flash('Payslip not found', 'danger')
        return redirect(url_for('employee.dashboard'))
    
    # Generate PDF
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(200, 750, "Payslip - Salary Management System")
    
    p.setFont("Helvetica", 12)
    p.drawString(50, 700, f"Employee Name: {payslip['employee_name']}")
    p.drawString(50, 680, f"Payroll Period: {payslip['period']}")
    
    p.drawString(50, 640, f"Basic Pay: Rs.{payslip['basic_pay']:.2f}")
    p.drawString(50, 620, f"Allowances (+): Rs.{payslip['allowances']:.2f}")
    p.drawString(50, 600, f"Deductions (-): Rs.{payslip['deductions']:.2f}")
    p.drawString(50, 580, f"Leaves Docked: {payslip.get('leave_days', 0)} days")
    
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, 540, f"Net Pay: Rs.{payslip['net_pay']:.2f}")
    
    p.showPage()
    p.save()
    
    buffer.seek(0)
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=payslip_{payslip["period"].replace("/", "_")}.pdf'
    return response
