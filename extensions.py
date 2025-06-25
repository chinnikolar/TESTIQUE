from flask_mysqldb import MySQL
from flask_login import LoginManager

# Initialize extensions
mysql = MySQL()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'