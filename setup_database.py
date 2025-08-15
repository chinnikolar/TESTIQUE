from flask import Flask
from flask_mysqldb import MySQL
import bcrypt
import os
import sys

# Import your config
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Initialize MySQL
mysql = MySQL(app)

def setup_database():
    with app.app_context():
        cursor = mysql.connection.cursor()
        
        # Create users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(100) NOT NULL,
            email VARCHAR(100) NOT NULL,
            full_name VARCHAR(100) NOT NULL,
            role VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create exams table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS exams (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            duration INT NOT NULL,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            created_by INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
        ''')
        
        # Create questions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            exam_id INT NOT NULL,
            question_text TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_option CHAR(1) NOT NULL,
            marks INT NOT NULL,
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
        )
        ''')
        
        # Create exam_sessions table with student_id instead of user_id
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS exam_sessions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT NOT NULL,
            exam_id INT NOT NULL,
            start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            end_time DATETIME,
            score INT,
            status VARCHAR(50) DEFAULT 'active',
            FOREIGN KEY (student_id) REFERENCES users(id),
            FOREIGN KEY (exam_id) REFERENCES exams(id)
        )
        ''')
        
        # Create student_answers table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_answers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            session_id INT NOT NULL,
            question_id INT NOT NULL,
            selected_option CHAR(1),
            is_correct BOOLEAN,
            FOREIGN KEY (session_id) REFERENCES exam_sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
        )
        ''')
        
        # Create proctoring_logs table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS proctoring_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            session_id INT NOT NULL,
            log_type VARCHAR(50) NOT NULL,
            details TEXT,
            screenshot MEDIUMTEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES exam_sessions(id) ON DELETE CASCADE
        )
        ''')
        
        # Check if admin already exists
        cursor.execute("SELECT * FROM users WHERE role = 'admin'")
        admin = cursor.fetchone()
        
        if not admin:
            # Create admin user
            username = "admin"
            password = "Chandana"  # You should change this
            email = "admin@example.com"
            full_name = "System Administrator"
            role = "admin"
            
            # Hash the password
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Insert admin user
            cursor.execute("""
                INSERT INTO users (username, password, email, full_name, role)
                VALUES (%s, %s, %s, %s, %s)
            """, (username, hashed_password, email, full_name, role))
            
            print("Admin user created successfully.")
            print(f"Username: {username}")
            print(f"Password: {password}")
        else:
            print("Admin user already exists.")
        
        mysql.connection.commit()
        cursor.close()
        
        print("Database setup completed successfully!")

if __name__ == "__main__":
    setup_database()