# Admin routes
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from datetime import datetime

from models.exam import Exam
from models.question import Question
from models.proctoring import ProctoringLog

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.index'))
    
    exams = Exam.get_all_exams()
    return render_template('admin/dashboard.html', exams=exams)

@admin_bp.route('/create_exam', methods=['GET', 'POST'])
@login_required
def create_exam():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        duration = int(request.form['duration'])
        start_time = datetime.strptime(request.form['start_time'], '%Y-%m-%dT%H:%M')
        end_time = datetime.strptime(request.form['end_time'], '%Y-%m-%dT%H:%M')
        
        exam_id = Exam.create_exam(title, description, duration, start_time, end_time, current_user.id)
        flash('Exam created successfully', 'success')
        return redirect(url_for('admin.add_questions', exam_id=exam_id))
    
    return render_template('admin/create_exam.html')

@admin_bp.route('/exam/<int:exam_id>/questions', methods=['GET', 'POST'])
@login_required
def add_questions(exam_id):
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.index'))
    
    exam = Exam.get_by_id(exam_id)
    if not exam:
        flash('Exam not found', 'danger')
        return redirect(url_for('admin.dashboard'))
    
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
        return redirect(url_for('admin.add_questions', exam_id=exam_id))
    
    questions = Question.get_by_exam_id(exam_id)
    return render_template('admin/add_questions.html', exam=exam, questions=questions)

@admin_bp.route('/proctoring/logs/<int:session_id>')
@login_required
def view_proctoring_logs(session_id):
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.index'))
    
    logs = ProctoringLog.get_logs_by_session(session_id)
    return render_template('admin/proctoring_logs.html', logs=logs)