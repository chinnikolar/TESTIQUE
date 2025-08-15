from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app
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
    
    # Get completed exam sessions for the current user
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT COUNT(*) as completed_count 
        FROM exam_sessions 
        WHERE student_id = %s AND status = 'completed'
    """, (current_user.id,))
    completed_result = cursor.fetchone()
    
    # Print the structure to debug
    print("Completed result type:", type(completed_result))
    print("Completed result value:", completed_result)
    
    # Handle different result formats
    completed_exams = 0
    if completed_result:
        if isinstance(completed_result, dict):
            completed_exams = completed_result.get('completed_count', 0)
        elif isinstance(completed_result, tuple):
            completed_exams = completed_result[0] if completed_result else 0
        elif hasattr(completed_result, 'completed_count'):
            completed_exams = completed_result.completed_count
    
    # Get upcoming exams (exams that haven't started yet)
    cursor.execute("""
        SELECT COUNT(*) as upcoming_count 
        FROM exams 
        WHERE start_time > NOW()
    """)
    upcoming_result = cursor.fetchone()
    upcoming_exams = 0
    if upcoming_result:
        if isinstance(upcoming_result, dict):
            upcoming_exams = upcoming_result.get('upcoming_count', 0)
        elif isinstance(upcoming_result, tuple):
            upcoming_exams = upcoming_result[0] if upcoming_result else 0
    
    # Calculate average score for completed exams
    cursor.execute("""
        SELECT AVG(score) as avg_score 
        FROM exam_sessions 
        WHERE student_id = %s AND status = 'completed' AND score IS NOT NULL
    """, (current_user.id,))
    avg_result = cursor.fetchone()
    avg_score = 'N/A'
    if avg_result:
        if isinstance(avg_result, dict) and avg_result.get('avg_score') is not None:
            avg_score = round(float(avg_result.get('avg_score')))
        elif isinstance(avg_result, tuple) and avg_result[0] is not None:
            avg_score = round(float(avg_result[0]))
    
    # Get completed sessions with details for the Results section
    cursor.execute("""
        SELECT es.id, es.start_time, es.end_time, es.score, e.title as exam_title
        FROM exam_sessions es
        JOIN exams e ON es.exam_id = e.id
        WHERE es.student_id = %s AND es.status = 'completed'
        ORDER BY es.end_time DESC
    """, (current_user.id,))
    raw_sessions = cursor.fetchall()
    
    completed_sessions = []
    
    # Print session structure to debug
    if raw_sessions and len(raw_sessions) > 0:
        print("Session result type:", type(raw_sessions[0]))
        print("Sample session:", raw_sessions[0])
    
    # Handle different result formats for sessions
    for row in raw_sessions:
        if isinstance(row, dict):
            # If results are dictionaries
            completed_sessions.append(row)
        elif isinstance(row, tuple):
            # If results are tuples, convert to dictionary
            session = {
                'id': row[0],
                'start_time': row[1],
                'end_time': row[2],
                'score': row[3],
                'exam_title': row[4]
            }
            completed_sessions.append(session)
    
    cursor.close()
    mysql.connection.commit()
    
    return render_template('student/dashboard.html', 
                          active_exams=active_exams,
                          completed_exams=completed_exams,
                          upcoming_exams=upcoming_exams,
                          avg_score=avg_score,
                          completed_sessions=completed_sessions)

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
    
    # Check if student has already completed this exam
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT * FROM exam_sessions 
        WHERE student_id = %s AND exam_id = %s AND status = 'completed'
    """, (current_user.id, exam_id))
    completed_session = cursor.fetchone()
    cursor.close()
    
    if completed_session:
        flash('You have already completed this exam', 'warning')
        return redirect(url_for('student.view_results', session_id=completed_session['id']))
    
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
    
    # Verify that this session belongs to the current user
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT * FROM exam_sessions 
        WHERE id = %s AND student_id = %s AND status = 'in_progress'
    """, (session_id, current_user.id))
    session = cursor.fetchone()
    cursor.close()
    
    if not session:
        flash('Invalid or expired exam session', 'danger')
        return redirect(url_for('student.dashboard'))
    
    exam = Exam.get_by_id(exam_id)
    if not exam:
        flash('Exam not found', 'danger')
        return redirect(url_for('student.dashboard'))
    
    questions = Question.get_by_exam_id(exam_id)
    questions_dict = [question.to_dict() for question in questions]
    if not questions:
        flash('No questions found for this exam', 'danger')
        return redirect(url_for('student.dashboard'))
    
    return render_template('student/take_exam.html', exam=exam, questions=questions_dict, session_id=session_id)

@student_bp.route('/api/proctoring/log', methods=['POST'])
@login_required
def log_proctoring_event():
    if current_user.role != 'student':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    data = request.json
    if not data:
        current_app.logger.error("No JSON data received in proctoring log request")
        return jsonify({'status': 'error', 'message': 'No data received'}), 400
        
    session_id = data.get('session_id')
    log_type = data.get('log_type')
    details = data.get('details', '')
    screenshot = data.get('screenshot')
    
    if not session_id or not log_type:
        current_app.logger.warning(f"Missing required fields in proctoring log: session_id={session_id}, log_type={log_type}")
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400
    
    try:
        log_id = ProctoringLog.create_log(session_id, log_type, details, screenshot)
        current_app.logger.info(f"Proctoring log created: {log_id}, type: {log_type}, session: {session_id}")
        return jsonify({'status': 'success', 'log_id': log_id})
    except Exception as e:
        current_app.logger.error(f"Error creating proctoring log: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Error creating log: {str(e)}'}), 500

@student_bp.route('/api/exam/submit', methods=['POST'])
@login_required
def submit_exam():
    if current_user.role != 'student':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    data = request.json
    if not data:
        current_app.logger.error("Submit exam API: No JSON data received.")
        return jsonify({'status': 'error', 'message': 'Invalid request data. Expected JSON.'}), 400

    session_id = data.get('session_id')
    answers = data.get('answers', {})

    if not session_id:
        current_app.logger.warning(f"Submit exam API: Missing session ID for user {current_user.id}.")
        return jsonify({'status': 'error', 'message': 'Missing session ID'}), 400

    try:
        current_app.logger.info(f"Attempting to submit exam for session_id: {session_id}, user: {current_user.id}")
        current_app.logger.debug(f"Received answers: {answers}")

        score = ExamSession.submit_answers(session_id, answers)

        current_app.logger.info(f"Exam submitted successfully for session_id: {session_id}. Score: {score}")
        return jsonify({'status': 'success', 'score': score})
    except Exception as e:
        current_app.logger.error(f"Error submitting exam for session_id {session_id}: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'An internal error occurred: {str(e)}'}), 500

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
    
    # Calculate total marks
    total_marks = 0
    for answer in answers:
        total_marks += answer['marks']
    
    return render_template('student/results.html', exam=exam, session=session, answers=answers, total_marks=total_marks)