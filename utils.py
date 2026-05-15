from app import db
import datetime

def log_audit(action, details, user_id="system"):
    """
    Logs an action to the audit/history collection for Tracking (Audits).
    """
    audit_entry = {
        "timestamp": datetime.datetime.now(),
        "action": action,
        "details": details,
        "user_id": user_id
    }
    db.audits.insert_one(audit_entry)

def send_mock_email(to_email, subject, body):
    """
    Mock Email system to simulate SMTP for examiner projects without exposing passwords.
    """
    print("="*40)
    print("📧 MOCK EMAIL DISPATCHED 📧")
    print(f"TO: {to_email}")
    print(f"SUBJECT: {subject}")
    print(f"BODY:\n{body}")
    print("="*40)
    return True
