class Question:
    def __init__(self, id, exam_id, question_text, option_a, option_b, option_c, option_d, correct_option, marks):
        self.id = id
        self.exam_id = exam_id
        self.question_text = question_text
        self.option_a = option_a
        self.option_b = option_b
        self.option_c = option_c
        self.option_d = option_d
        self.correct_option = correct_option
        self.marks = marks

    @staticmethod
    def get_by_id(question_id):
        from extensions import mysql
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM questions WHERE id = %s", (question_id,))
        question_data = cursor.fetchone()
        cursor.close()
        
        if question_data:
            return Question(
                id=question_data['id'],
                exam_id=question_data['exam_id'],
                question_text=question_data['question_text'],
                option_a=question_data['option_a'],
                option_b=question_data['option_b'],
                option_c=question_data['option_c'],
                option_d=question_data['option_d'],
                correct_option=question_data['correct_option'],
                marks=question_data['marks']
            )
        return None
    
    @staticmethod
    def get_by_exam_id(exam_id):
        from extensions import mysql
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM questions WHERE exam_id = %s", (exam_id,))
        questions_data = cursor.fetchall()
        cursor.close()
        
        questions = []
        for question_data in questions_data:
            questions.append(Question(
                id=question_data['id'],
                exam_id=question_data['exam_id'],
                question_text=question_data['question_text'],
                option_a=question_data['option_a'],
                option_b=question_data['option_b'],
                option_c=question_data['option_c'],
                option_d=question_data['option_d'],
                correct_option=question_data['correct_option'],
                marks=question_data['marks']
            ))
        return questions
        
    def to_dict(self):
        """Convert the Question object to a dictionary for JSON serialization"""
        # Create a dictionary of all attributes that don't start with underscore
        result = {}
        for key in dir(self):
            # Skip private attributes and methods
            if key.startswith('_') or callable(getattr(self, key)):
                continue
            
            # Add attribute to dictionary if it's a basic type that can be serialized
            value = getattr(self, key)
            try:
                # Test if value is JSON serializable
                import json
                json.dumps(value)
                result[key] = value
            except (TypeError, OverflowError):
                # If it's not serializable, convert to string
                result[key] = str(value)
        
        return result
        
    @staticmethod
    def create_question(exam_id, question_text, option_a, option_b, option_c, option_d, correct_option, marks):
        from extensions import mysql
        
        # Convert the correct_option value to a single character to avoid truncation
        # Map option_a -> 'a', option_b -> 'b', etc.
        option_map = {
            'option_a': 'a',
            'option_b': 'b',
            'option_c': 'c',
            'option_d': 'd'
        }
        
        # If the correct_option is in our map, use the shortened version
        # Otherwise, keep it as is (fallback)
        shortened_option = option_map.get(correct_option, correct_option)
        
        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO questions (exam_id, question_text, option_a, option_b, option_c, option_d, correct_option, marks)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (exam_id, question_text, option_a, option_b, option_c, option_d, shortened_option, marks))
        question_id = cursor.lastrowid
        mysql.connection.commit()
        cursor.close()
        return question_id