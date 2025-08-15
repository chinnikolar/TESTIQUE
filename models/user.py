from flask import current_app
from flask_login import UserMixin
from extensions import mysql

class User(UserMixin):
    def __init__(self, id, username, email, full_name, role, password=None):
        self.id = id
        self.username = username
        self.email = email
        self.full_name = full_name
        self.role = role
        self.password = password  # Used for comparison only, not stored in the object after login

    @staticmethod
    def get_by_id(user_id):
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        cursor.close()

        if user:
            return User(
                id=user['id'],
                username=user['username'],
                email=user['email'],
                full_name=user['full_name'],
                role=user['role']
            )
        return None

    @staticmethod
    def get_by_username(username):
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()

        if user:
            return User(
                id=user['id'],
                username=user['username'],
                email=user['email'],
                full_name=user['full_name'],
                role=user['role'],
                password=user['password']
            )
        return None
    
    @staticmethod
    def username_exists(username):
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        exists = cursor.fetchone() is not None
        cursor.close()
        return exists
    
    @staticmethod
    def create_user(username, password, email, full_name, role):
        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO users (username, password, email, full_name, role)
            VALUES (%s, %s, %s, %s, %s)
        """, (username, password, email, full_name, role))
        user_id = cursor.lastrowid
        mysql.connection.commit()
        cursor.close()
        return user_id