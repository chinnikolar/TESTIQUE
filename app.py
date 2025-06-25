from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_mysqldb import MySQL
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import bcrypt
import os
from datetime import datetime, timedelta

# Import config
from config import Config

# Create the Flask application
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
mysql = MySQL(app)  # This attaches MySQL to app directly
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Import models after initializing app and MySQL
from models.user import User
from models.exam import Exam
from models.question import Question
from models.exam_session import ExamSession
from models.proctoring import ProctoringLog

def create_app(config_class=Config):
    """
    Application factory function to create and configure the Flask app
    """
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions with the app
    mysql.init_app(app)
    login_manager.init_app(app)
    
    # Load user from session
    @login_manager.user_loader
    def load_user(user_id):
        return User.get_by_id(user_id)
    
    # Register blueprints
    from blueprints.auth import auth_bp
    from blueprints.admin import admin_bp
    from blueprints.student import student_bp
    from blueprints.main import main_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(main_bp)
    
    # Root route for the index page
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            if current_user.role == 'admin':
                return app.redirect(url_for('admin.dashboard'))
            else:
                return app.redirect(url_for('student.dashboard'))
        return render_template('index.html')
    
    # Create upload folder if it doesn't exist
    if 'UPLOAD_FOLDER' in app.config:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    return app

# Load user from session
@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(user_id)

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.get_by_username(username)
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        full_name = request.form['full_name']
        role = request.form.get('role', 'student')  # Default to student if not specified
        
        # Check if username already exists
        if User.username_exists(username):
            flash('Username already exists', 'danger')
            return render_template('register.html')
        
        # Hash the password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Create new user
        User.create_user(username, hashed_password, email, full_name, role)
        
        flash('Registration successful. Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
    
    exams = Exam.get_all_exams()
    return render_template('admin/dashboard.html', exams=exams)

@app.route('/admin/create_exam', methods=['GET', 'POST'])
@login_required
def create_exam():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        duration = int(request.form['duration'])
        start_time = datetime.strptime(request.form['start_time'], '%Y-%m-%dT%H:%M')
        end_time = datetime.strptime(request.form['end_time'], '%Y-%m-%dT%H:%M')
        
        exam_id = Exam.create_exam(title, description, duration, start_time, end_time, current_user.id)
        flash('Exam created successfully', 'success')
        return redirect(url_for('add_questions', exam_id=exam_id))
    
    return render_template('admin/create_exam.html')

@app.route('/admin/exam/<int:exam_id>/questions', methods=['GET', 'POST'])
@login_required
def add_questions(exam_id):
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
    
    exam = Exam.get_by_id(exam_id)
    if not exam:
        flash('Exam not found', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        question_text = request.form['question_text']
        option_a = request.form['option_a']
        option_b = request.form['option_b']
        option_c = request.form['option_c']
        option_d = request.form['option_d']
        correct_option = request.form['correct_option']
        marks = int(request.form['marks'])
        
        Question.create_question(exam_id, question_text, option_a, option_b, option_c, option_d, correct_option, marks)
        flash('Question added successfully', 'success')
        return redirect(url_for('add_questions', exam_id=exam_id))
    
    questions = Question.get_by_exam_id(exam_id)
    return render_template('admin/add_questions.html', exam=exam, questions=questions)


@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
    
    active_exams = Exam.get_active_exams()
    return render_template('student/dashboard.html', active_exams=active_exams)

@app.route('/student/exam/<int:exam_id>/start')
@login_required
def start_exam(exam_id):
    if current_user.role != 'student':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
    
    exam = Exam.get_by_id(exam_id)
    if not exam:
        flash('Exam not found', 'danger')
        return redirect(url_for('student_dashboard'))
    
    # Check if exam is active
    now = datetime.now()
    if now < exam.start_time or now > exam.end_time:
        flash('Exam is not active at this time', 'danger')
        return redirect(url_for('student_dashboard'))
    
    # Check if student already has an active session
    session = ExamSession.get_active_session(current_user.id, exam_id)
    if session:
        session_id = session.id
    else:
        # Create a new session
        session_id = ExamSession.create_session(current_user.id, exam_id)
    
    return redirect(url_for('take_exam', exam_id=exam_id, session_id=session_id))

@app.route('/student/exam/<int:exam_id>/take/<int:session_id>')
@login_required
def take_exam(exam_id, session_id):
    if current_user.role != 'student':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
    
    exam = Exam.get_by_id(exam_id)
    if not exam:
        flash('Exam not found', 'danger')
        return redirect(url_for('student_dashboard'))
    
    questions = Question.get_by_exam_id(exam_id)
    if not questions:
        flash('No questions found for this exam', 'danger')
        return redirect(url_for('student_dashboard'))
    
    return render_template('student/take_exam.html', exam=exam, questions=questions, session_id=session_id)

@app.route('/api/proctoring/log', methods=['POST'])
@login_required
def log_proctoring_event():
    if current_user.role != 'student':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    data = request.json
    session_id = data.get('session_id')
    log_type = data.get('log_type')
    details = data.get('details', '')
    screenshot = data.get('screenshot')
    
    if not session_id or not log_type:
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400
    
    log_id = ProctoringLog.create_log(session_id, log_type, details, screenshot)
    
    return jsonify({'status': 'success', 'log_id': log_id})

@app.route('/api/exam/submit', methods=['POST'])
@login_required
def submit_exam():
    if current_user.role != 'student':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    data = request.json
    session_id = data.get('session_id')
    answers = data.get('answers', {})
    
    if not session_id:
        return jsonify({'status': 'error', 'message': 'Missing session ID'}), 400
    
    score = ExamSession.submit_answers(session_id, answers)
    
    return jsonify({'status': 'success', 'score': score})

@app.route('/admin/proctoring/logs/<int:session_id>')
@login_required
def view_proctoring_logs(session_id):
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
    
    logs = ProctoringLog.get_logs_by_session(session_id)
    return render_template('admin/proctoring_logs.html', logs=logs)

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app = create_app()
    app.run(debug=True)