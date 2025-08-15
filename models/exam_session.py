from datetime import datetime
from extensions import mysql

class ExamSession:
    def __init__(self, id, student_id, exam_id, start_time, end_time=None, status='in_progress', score=None):
        self.id = id
        self.student_id = student_id
        self.exam_id = exam_id
        self.start_time = start_time
        self.end_time = end_time
        self.status = status
        self.score = score
    
    @staticmethod
    def get_by_id(session_id):
        from extensions import mysql
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT es.*, u.username, u.email 
            FROM exam_sessions es
            JOIN users u ON es.student_id = u.id
            WHERE es.id = %s
        """, (session_id,))
        session_data = cursor.fetchone()
        cursor.close()
        
        if session_data:
            session = ExamSession(
                id=session_data['id'],
                student_id=session_data['student_id'],
                exam_id=session_data['exam_id'],
                start_time=session_data['start_time'],
                end_time=session_data['end_time'],
                status=session_data['status'],
                score=session_data['score']
            )
            
            # Add additional fields directly to the session object
            session.student_name = session_data['username']
            session.student_email = session_data['email']
            
            return session
        return None
    
    
    def get_student_answers(self):
        """Get all answers submitted by the student in this exam session"""
        from extensions import mysql
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT * FROM student_answers 
            WHERE session_id = %s
        """, (self.id,))
        answers = cursor.fetchall()
        cursor.close()
        
        return answers
    
    @staticmethod
    def get_active_session(student_id, exam_id):
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT * FROM exam_sessions 
            WHERE student_id = %s AND exam_id = %s AND status = 'in_progress'
        """, (student_id, exam_id))
        session_data = cursor.fetchone()
        cursor.close()
        
        if session_data:
            return ExamSession(
                id=session_data['id'],
                student_id=session_data['student_id'],
                exam_id=session_data['exam_id'],
                start_time=session_data['start_time'],
                end_time=session_data['end_time'],
                status=session_data['status'],
                score=session_data['score']
            )
        return None
    
    @staticmethod
    def create_session(student_id, exam_id):
        now = datetime.now()
        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO exam_sessions (student_id, exam_id, start_time, status)
            VALUES (%s, %s, %s, 'in_progress')
        """, (student_id, exam_id, now))
        session_id = cursor.lastrowid
        mysql.connection.commit()
        cursor.close()
        return session_id
    
    @staticmethod
    def get_completed_session(student_id, exam_id):
        """Get a completed exam session for the student and exam"""
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT * FROM exam_sessions 
            WHERE student_id = %s AND exam_id = %s AND status = 'completed'
            ORDER BY end_time DESC 
            LIMIT 1
        """, (student_id, exam_id))
        session_data = cursor.fetchone()
        cursor.close()
        
        if session_data:
            return ExamSession(
                id=session_data['id'],
                student_id=session_data['student_id'],
                exam_id=session_data['exam_id'],
                start_time=session_data['start_time'],
                end_time=session_data['end_time'],
                status=session_data['status'],
                score=session_data['score']
            )
        return None
    
    @staticmethod
    def submit_answers(session_id, answers):
        """Submit student answers and calculate the score"""
        from flask import current_app
        
        # Verify session exists and is active
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM exam_sessions WHERE id = %s", (session_id,))
        session = cursor.fetchone()
        
        if not session or session['status'] != 'in_progress':
            current_app.logger.error(f"Invalid session for submission: {session_id}")
            raise ValueError("Invalid or already completed session")
        
        # Get all questions for this exam
        exam_id = session['exam_id']
        cursor.execute("SELECT * FROM questions WHERE exam_id = %s", (exam_id,))
        questions = cursor.fetchall()
        
        if not questions:
            current_app.logger.error(f"No questions found for exam_id: {exam_id}")
            raise ValueError("No questions found for this exam")
        
        # Calculate score
        total_marks = 0
        obtained_marks = 0
        
        # Process each answer
        for question in questions:
            question_id = str(question['id'])
            total_marks += question['marks']
            
            # Check if student answered this question
            if question_id in answers:
                selected_option = answers[question_id]
                
                # Debug logging
                current_app.logger.info(f"Processing answer for question {question_id}: selected={selected_option}, correct={question['correct_option']}")
                
                # Ensure consistent comparison by normalizing format
                # Convert both to same format for comparison (lowercase single character)
                correct_option = question['correct_option'].lower()
                if correct_option.startswith('option_'):
                    correct_option = correct_option[-1]  # Extract the last character (a, b, c, d)
                    
                selected_normalized = selected_option.lower()
                if selected_normalized.startswith('option_'):
                    selected_normalized = selected_normalized[-1]
                    
                is_correct = (selected_normalized == correct_option)
                
                # Debug logging
                current_app.logger.info(f"Normalized comparison: selected={selected_normalized}, correct={correct_option}, is_correct={is_correct}")
                
                if is_correct:
                    obtained_marks += question['marks']
                
                # Save student's answer with the original format
                cursor.execute("""
                    INSERT INTO student_answers 
                    (session_id, question_id, selected_option, is_correct)
                    VALUES (%s, %s, %s, %s)
                """, (session_id, question_id, selected_option, is_correct))
        
        # Calculate percentage
        percentage_score = (obtained_marks / total_marks) * 100 if total_marks > 0 else 0
        
        # Update session as completed
        now = datetime.now()
        cursor.execute("""
            UPDATE exam_sessions 
            SET status = 'completed', end_time = %s, score = %s
            WHERE id = %s
        """, (now, obtained_marks, session_id))  # Store raw score instead of percentage
        
        # Log exam completion
        score_message = f"Score: {obtained_marks}/{total_marks} ({percentage_score:.1f}%)"
        cursor.execute("""
            INSERT INTO proctoring_logs (session_id, log_type, details, timestamp)
            VALUES (%s, %s, %s, %s)
        """, (session_id, 'exam_end', score_message, now))
        
        mysql.connection.commit()
        cursor.close()
        
        return percentage_score
    
    @staticmethod
    def get_student_sessions(student_id):
        """Get all exam sessions for a student"""
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT es.*, e.title as exam_title
            FROM exam_sessions es
            JOIN exams e ON es.exam_id = e.id
            WHERE es.student_id = %s
            ORDER BY es.start_time DESC
        """, (student_id,))
        sessions_data = cursor.fetchall()
        cursor.close()
        
        return sessions_data
    
    
    
    @staticmethod
    def get_recent_sessions(limit=10):
        """Get the most recent exam sessions"""
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT es.*, e.title as exam_title, u.username as student_name
            FROM exam_sessions es
            JOIN exams e ON es.exam_id = e.id
            JOIN users u ON es.student_id = u.id
            ORDER BY es.start_time DESC
            LIMIT %s
        """, (limit,))
        sessions_data = cursor.fetchall()
        cursor.close()
        
        return sessions_data
    
    @staticmethod
    def get_results_by_exam(exam_id):
        """Get all exam session results for a specific exam"""
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT es.*, u.username as student_name
            FROM exam_sessions es
            JOIN users u ON es.student_id = u.id
            WHERE es.exam_id = %s AND es.status = 'completed'
            ORDER BY es.score DESC
        """, (exam_id,))
        results = cursor.fetchall()
        cursor.close()
    
        return results