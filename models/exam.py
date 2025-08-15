from flask import current_app
from datetime import datetime

class Exam:
    def __init__(self, id, title, description, duration, start_time, end_time, created_by):
        self.id = id
        self.title = title
        self.description = description
        self.duration = duration
        self.start_time = start_time
        self.end_time = end_time
        self.created_by = created_by

    @staticmethod
    def get_by_id(exam_id):
        from extensions import mysql
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM exams WHERE id = %s", (exam_id,))
        exam_data = cursor.fetchone()
        cursor.close()
        
        if exam_data:
            return Exam(
                id=exam_data['id'],
                title=exam_data['title'],
                description=exam_data['description'],
                duration=exam_data['duration'],
                start_time=exam_data['start_time'],
                end_time=exam_data['end_time'],
                created_by=exam_data['created_by']
            )
        return None
    
    @staticmethod
    def get_all_exams():
        from extensions import mysql
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM exams ORDER BY created_at DESC")
        exams_data = cursor.fetchall()
        cursor.close()
        
        exams = []
        for exam_data in exams_data:
            exams.append(Exam(
                id=exam_data['id'],
                title=exam_data['title'],
                description=exam_data['description'],
                duration=exam_data['duration'],
                start_time=exam_data['start_time'],
                end_time=exam_data['end_time'],
                created_by=exam_data['created_by']
            ))
        return exams
    
    @staticmethod
    def get_active_exams():
        from extensions import mysql
        now = datetime.now()
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT * FROM exams 
            WHERE start_time <= %s AND end_time >= %s
            ORDER BY start_time
        """, (now, now))
        exams_data = cursor.fetchall()
        cursor.close()
        
        exams = []
        for exam_data in exams_data:
            exams.append(Exam(
                id=exam_data['id'],
                title=exam_data['title'],
                description=exam_data['description'],
                duration=exam_data['duration'],
                start_time=exam_data['start_time'],
                end_time=exam_data['end_time'],
                created_by=exam_data['created_by']
            ))
        return exams
    
    @staticmethod
    def create_exam(title, description, duration, start_time, end_time, created_by):
        from extensions import mysql
        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO exams (title, description, duration, start_time, end_time, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (title, description, duration, start_time, end_time, created_by))
        exam_id = cursor.lastrowid
        mysql.connection.commit()
        cursor.close()
        return exam_id