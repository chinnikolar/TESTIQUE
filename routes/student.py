from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from extensions import mysql

from models.exam import Exam
from models.question import Question
from models.exam_session import ExamSession
from models.proctoring import ProctoringLog

student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'student':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.index'))
    
    active_exams = Exam.get_active_exams()
    return render_template('student/dashboard.html', active_exams=active_exams)

@student_bp.route('/exam/<int:exam_id>/start')
@login_required
def start_exam(exam_id):
    if current_user.role != 'student':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.index'))
    
    exam = Exam.get_by_id(exam_id)
    if not exam:
        flash('Exam not found', 'danger')
        return redirect(url_for('student.dashboard'))
    
    # Check if exam is active
    now = datetime.now()
    if now < exam.start_time or now > exam.end_time:
        flash('Exam is not active at this time', 'danger')
        return redirect(url_for('student.dashboard'))
    
    # Check if student already has an active session
    session = ExamSession.get_active_session(current_user.id, exam_id)
    if session:
        session_id = session.id
    else:
        # Create a new session
        session_id = ExamSession.create_session(current_user.id, exam_id)
    
    return redirect(url_for('student.take_exam', exam_id=exam_id, session_id=session_id))

@student_bp.route('/exam/<int:exam_id>/take/<int:session_id>')
@login_required
def take_exam(exam_id, session_id):
    if current_user.role != 'student':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.index'))
    
    exam = Exam.get_by_id(exam_id)
    if not exam:
        flash('Exam not found', 'danger')
        return redirect(url_for('student.dashboard'))
    
    questions = Question.get_by_exam_id(exam_id)
    if not questions:
        flash('No questions found for this exam', 'danger')
        return redirect(url_for('student.dashboard'))
    
    return render_template('student/take_exam.html', exam=exam, questions=questions, session_id=session_id)

@student_bp.route('/api/proctoring/log', methods=['POST'])
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

@student_bp.route('/api/exam/submit', methods=['POST'])
@login_required
def submit_exam():
    if current_user.role != 'student':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    data = request.json
    session_id = data.get('session_id')
    answers = data.get('answers', {})
    
    if not session_id:
        return jsonify({'status': 'error', 'message': 'Missing session ID'}), 400
    
    # Calculate score
    score = 0
    cursor = mysql.connection.cursor()
    
    for question_id, answer in answers.items():
        cursor.execute("""
            SELECT correct_option, marks FROM questions WHERE id = %s
        """, (question_id,))
        question = cursor.fetchone()
        
        if question and answer == question['correct_option']:
            is_correct = True
            score += question['marks']
        else:
            is_correct = False
        
        # Save student answer
        cursor.execute("""
            INSERT INTO student_answers (session_id, question_id, selected_option, is_correct)
            VALUES (%s, %s, %s, %s)
        """, (session_id, question_id, answer, is_correct))
    
    # Complete the session
    ExamSession.complete_session(session_id, score)
    
    mysql.connection.commit()
    cursor.close()
    
    return jsonify({'status': 'success', 'score': score})

@student_bp.route('/exam/results/<int:session_id>')
@login_required
def view_results(session_id):
    if current_user.role != 'student':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.index'))
    
    # Get session details
    session = ExamSession.get_by_id(session_id)
    if not session or session.student_id != current_user.id:
        flash('Results not found or unauthorized', 'danger')
        return redirect(url_for('student.dashboard'))
    
    # Get exam details
    exam = Exam.get_by_id(session.exam_id)
    
    # Get student answers
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT sa.question_id, sa.selected_option, sa.is_correct, 
               q.question_text, q.option_a, q.option_b, q.option_c, q.option_d, q.correct_option, q.marks
        FROM student_answers sa
        JOIN questions q ON sa.question_id = q.id
        WHERE sa.session_id = %s
    """, (session_id,))
    answers = cursor.fetchall()
    cursor.close()
    
    return render_template('student/exam_results.html', exam=exam, session=session, answers=answers)