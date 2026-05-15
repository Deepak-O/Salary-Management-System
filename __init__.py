import os
from flask import Flask
from pymongo import MongoClient

# Database instance
db = None

def create_app():
    global db
    app = Flask(__name__)
    app.secret_key = os.getenv('SECRET_KEY', 'supersecretkey_change_in_production')

    # Setup MongoDB
    mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
    client = MongoClient(mongo_uri)
    db = client['salary_management_db']

    # Register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.hr import hr_bp
    from app.routes.employee import employee_bp
    from app.routes.leave import leave_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(hr_bp, url_prefix='/hr')
    app.register_blueprint(employee_bp, url_prefix='/employee')
    app.register_blueprint(leave_bp, url_prefix='/leave')

    return app
