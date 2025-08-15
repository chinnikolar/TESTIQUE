from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file, current_app
from flask_login import login_required, current_user
from datetime import datetime
import pandas as pd
import io
from extensions import mysql
from models.exam import Exam
from models.question import Question
from models.exam_session import ExamSession
from models.proctoring import ProctoringLog

# Import the mysql instance or use current_app
# You have two options:
# 1. Import mysql directly if it's defined in your app initialization
# from your_app import mysql
# 2. Or access it through current_app, which is what we'll do here

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.index'))
    
    exams = Exam.get_all_exams()
    # Get recent exam sessions for the dashboard
    recent_sessions = ExamSession.get_recent_sessions()
    
    return render_template('admin/dashboard.html', exams=exams, recent_sessions=recent_sessions)

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

@admin_bp.route('/exam/<int:exam_id>/question/<int:question_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_question(exam_id, question_id):
    # Implement question editing logic
    pass

@admin_bp.route('/exam/<int:exam_id>/question/<int:question_id>/delete')
@login_required
def delete_question(exam_id, question_id):
    # Implement question deletion logic
    pass

@admin_bp.route('/exam/<int:exam_id>/results')
@login_required
def view_exam_results(exam_id):
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.index'))
    
    exam = Exam.get_by_id(exam_id)
    if not exam:
        flash('Exam not found', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    # Get exam results
    results = ExamSession.get_results_by_exam(exam_id)
    
    # Calculate statistics
    stats = calculate_exam_stats(results, exam)
    
    # Get question statistics 
    question_stats = calculate_question_stats(exam_id)
    
    total_marks = calculate_total_marks(exam_id)
    
    # Pass helper function to template to fix the dictionary access issue
    def get_session_url(result):
        # Check if result is a dict or an object
        if isinstance(result, dict):
            session_id = result.get('id') or result.get('session_id')
        else:
            session_id = getattr(result, 'id', None) or getattr(result, 'session_id', None)
        
        if session_id:
            return url_for('admin.view_student_result', session_id=session_id)
        return "#"  # Fallback URL if no session_id found
    
    return render_template('admin/results.html', 
                           exam=exam, 
                           results=results, 
                           stats=stats, 
                           question_stats=question_stats,
                           total_marks=total_marks,
                           get_session_url=get_session_url)

@admin_bp.route('/exam/<int:exam_id>/export')
@login_required
def export_results(exam_id):
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.index'))
    
    exam = Exam.get_by_id(exam_id)
    if not exam:
        flash('Exam not found', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    # Get exam results
    results = ExamSession.get_results_by_exam(exam_id)
    total_marks = calculate_total_marks(exam_id)
    
    # Convert to DataFrame for Excel export
    data = []
    for result in results:
        # Handle both object and dictionary format
        if isinstance(result, dict):
            student_name = result.get('student_name', '')
            start_time = result.get('start_time', datetime.now())
            end_time = result.get('end_time', datetime.now())
            score = result.get('score', 0)
        else:
            student_name = result.student_name
            start_time = result.start_time
            end_time = result.end_time
            score = result.score
            
        data.append({
            'Student Name': student_name,
            'Start Time': start_time.strftime('%Y-%m-%d %H:%M') if hasattr(start_time, 'strftime') else start_time,
            'End Time': end_time.strftime('%Y-%m-%d %H:%M') if hasattr(end_time, 'strftime') else end_time,
            'Score': score,
            'Total Marks': total_marks,
            'Percentage': round(score / total_marks * 100) if total_marks > 0 else 0,
            'Status': 'Pass' if score / total_marks >= 0.7 else 
                      'Average' if score / total_marks >= 0.4 else 'Fail'
        })
    
    df = pd.DataFrame(data)
    
    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Results', index=False)
        
        # Access the workbook and worksheet objects
        workbook = writer.book
        worksheet = writer.sheets['Results']
        
        # Add formats
        header_format = workbook.add_format({'bold': True, 'bg_color': '#4472C4', 'color': 'white'})
        pass_format = workbook.add_format({'bg_color': '#C6EFCE'})
        avg_format = workbook.add_format({'bg_color': '#FFEB9C'})
        fail_format = workbook.add_format({'bg_color': '#FFC7CE'})
        
        # Apply header format
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Auto-adjust columns width
        for i, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.set_column(i, i, max_len)
    
    output.seek(0)
    
    # Generate filename
    filename = f"{exam.title.replace(' ', '_')}_results_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@admin_bp.route('/exam/session/<int:session_id>')
@login_required
def view_student_result(session_id):
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.index'))
    
    # Get the exam session details
    session_info = ExamSession.get_by_id(session_id)
    if not session_info:
        flash('Exam session not found', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    # Get the exam details
    exam = Exam.get_by_id(session_info.exam_id)
    if not exam:
        flash('Exam not found', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    # Get the student's info (including email)
    from models.user import User
    student = User.get_by_id(session_info.student_id)
    if not student:
        flash('Student information not found', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    # Add student information to session_info
    session_info.student_name = student.username  # or full_name if available
    session_info.student_email = student.email
    
    # Get the student's answers
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT * FROM student_answers 
        WHERE session_id = %s
    """, (session_id,))
    student_answers = cursor.fetchall()
    cursor.close()
    
    # Create a dictionary for faster lookup
    student_answer_dict = {}
    for answer in student_answers:
        # Convert question_id to int for consistent type comparison
        student_answer_dict[int(answer['question_id'])] = answer
    
    # Get all questions for this exam
    exam_questions = Question.get_by_exam_id(exam.id)
    
    # Calculate total possible marks
    total_marks = calculate_total_marks(exam.id)
    
    return render_template('admin/student_result.html',
                          session=session_info,
                          exam=exam,
                          answers=student_answers,
                          answer_dict=student_answer_dict,  # Pass the dictionary for easier lookup
                          questions=exam_questions,
                          total_marks=total_marks)

@admin_bp.route('/proctoring/logs/<int:session_id>')
@login_required
def view_proctoring_logs(session_id):
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.index'))
    
    session_info = ExamSession.get_by_id(session_id)
    if not session_info:
        flash('Exam session not found', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    logs = ProctoringLog.get_logs_by_session(session_id)
    return render_template('admin/proctoring_logs.html', logs=logs, session=session_info)

# Helper functions
def calculate_exam_stats(results, exam):
    total_students = len(results)
    if total_students == 0:
        return {
            'total_students': 0,
            'average_score': 0,
            'pass_rate': 0
        }
    
    # Handle results as either dictionaries or objects
    total_score = 0
    for result in results:
        if isinstance(result, dict):
            total_score += result.get('score', 0)
        else:
            total_score += getattr(result, 'score', 0)
    
    average_score = total_score / total_students
    
    # Calculate total marks for this exam
    total_marks = calculate_total_marks(exam.id)
    
    # Pass rate (percentage of students who scored >= 70%)
    passed_students = 0
    for result in results:
        score = result.get('score', 0) if isinstance(result, dict) else getattr(result, 'score', 0)
        if score / total_marks >= 0.7:
            passed_students += 1
    
    pass_rate = (passed_students / total_students) * 100 if total_students > 0 else 0
    
    return {
        'total_students': total_students,
        'average_score': average_score,
        'pass_rate': round(pass_rate)
    }

def calculate_question_stats(exam_id):
    # Instead of direct SQL queries, let's use the models we've already imported
    # This assumes you have proper ORM models set up
    
    # If you have a Question model with appropriate methods
    questions = Question.get_by_exam_id(exam_id)
    stats = []
    
    for question in questions:
        # This assumes your models have methods to get answer statistics
        # If not, you'll need to implement them according to your data model
        correct_count = question.get_correct_answers_count() if hasattr(question, 'get_correct_answers_count') else 0
        incorrect_count = question.get_incorrect_answers_count() if hasattr(question, 'get_incorrect_answers_count') else 0
        
        total_attempts = correct_count + incorrect_count
        success_rate = (correct_count / total_attempts * 100) if total_attempts > 0 else 0
        
        stats.append({
            'question_text': question.question_text,
            'correct_count': correct_count,
            'incorrect_count': incorrect_count,
            'success_rate': round(success_rate)
        })
    
    return stats

def calculate_total_marks(exam_id):
    # Use the Question model instead of direct SQL
    questions = Question.get_by_exam_id(exam_id)
    
    # Sum the marks for all questions
    total_marks = sum(question.marks for question in questions) if questions else 0
    
    return total_marks