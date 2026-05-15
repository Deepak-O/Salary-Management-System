from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
client = MongoClient(mongo_uri)
db = client['salary_management_db']

def seed_db():
    hr_exists = db.employees.find_one({'email': 'hr@example.com'})
    if not hr_exists:
        db.employees.insert_one({
            'name': 'HR Manager',
            'email': 'hr@example.com',
            'role': 'hr',
            'password': 'admin',
            'department': 'Human Resources',
            'designation': 'Admin'
        })
        print("Default HR created: hr@example.com / admin")
    else:
        print("HR user already exists")

if __name__ == '__main__':
    seed_db()
