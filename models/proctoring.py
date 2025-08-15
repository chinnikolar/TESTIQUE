from datetime import datetime
import base64
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProctoringLog:
    def __init__(self, id=None, session_id=None, log_type=None, details=None, timestamp=None, screenshot=None):
        self.id = id
        self.session_id = session_id
        self.log_type = log_type
        self.details = details
        self.timestamp = timestamp
        self.screenshot = screenshot
        
    @staticmethod
    def create_log(session_id, log_type, details=None, screenshot=None):
        """
        Create a new proctoring log entry with improved error handling and validation
        """
        if not session_id:
            logger.error("Cannot create log: session_id is required")
            return None
            
        if not log_type:
            logger.error("Cannot create log: log_type is required")
            return None
        
        try:
            from extensions import mysql
            now = datetime.now()
            cursor = mysql.connection.cursor()
            
            # First, check if the proctoring_logs table exists
            cursor.execute("SHOW TABLES LIKE 'proctoring_logs'")
            if not cursor.fetchone():
                logger.warning("proctoring_logs table does not exist, creating it")
                # Create the table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS proctoring_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        session_id INT NOT NULL,
                        log_type VARCHAR(50) NOT NULL,
                        details TEXT,
                        screenshot LONGTEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES exam_sessions(id) ON DELETE CASCADE
                    )
                """)
                mysql.connection.commit()
            
            # Process screenshot - save truncated version if too large
            processed_screenshot = None
            if screenshot:
                # Check if screenshot is already encoded
                if isinstance(screenshot, str) and screenshot.startswith('data:image/'):
                    # Limit screenshot size if needed
                    if len(screenshot) > 1000000:  # If larger than ~1MB
                        processed_screenshot = screenshot[:100000] + "...truncated..."
                    else:
                        processed_screenshot = screenshot
                else:
                    # Try to encode it
                    try:
                        encoded = base64.b64encode(screenshot).decode('utf-8')
                        processed_screenshot = f"data:image/jpeg;base64,{encoded}"
                    except Exception as e:
                        logger.error(f"Failed to encode screenshot: {e}")
            
            # Insert the log entry
            try:
                cursor.execute("""
                    INSERT INTO proctoring_logs (session_id, log_type, details, screenshot, timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                """, (session_id, log_type, details, processed_screenshot, now))
                
                log_id = cursor.lastrowid
                mysql.connection.commit()
                
                logger.info(f"Created proctoring log: ID={log_id}, Type={log_type}, Session={session_id}")
                return log_id
                
            except Exception as insert_error:
                logger.error(f"Database insertion error: {insert_error}")
                # Check if the error is related to a missing column
                if "Unknown column 'screenshot'" in str(insert_error):
                    # Try without the screenshot column
                    cursor.execute("""
                        INSERT INTO proctoring_logs (session_id, log_type, details, timestamp)
                        VALUES (%s, %s, %s, %s)
                    """, (session_id, log_type, details, now))
                    
                    log_id = cursor.lastrowid
                    mysql.connection.commit()
                    
                    logger.info(f"Created proctoring log without screenshot: ID={log_id}, Type={log_type}")
                    return log_id
                else:
                    # Re-raise if it's not a column issue
                    raise
                    
        except Exception as e:
            logger.error(f"Error creating proctoring log: {e}")
            # Check if the error is related to the foreign key constraint
            if "foreign key constraint fails" in str(e).lower():
                logger.error(f"Foreign key constraint error - Invalid session_id: {session_id}")
                
                # Try to create log in a backup table without foreign key constraints
                try:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS proctoring_logs_backup (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            session_id INT NOT NULL,
                            log_type VARCHAR(50) NOT NULL,
                            details TEXT,
                            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    mysql.connection.commit()
                    
                    cursor.execute("""
                        INSERT INTO proctoring_logs_backup (session_id, log_type, details, timestamp)
                        VALUES (%s, %s, %s, %s)
                    """, (session_id, log_type, details, now))
                    
                    log_id = cursor.lastrowid
                    mysql.connection.commit()
                    logger.info(f"Created backup proctoring log: ID={log_id}")
                    return log_id
                except Exception as backup_error:
                    logger.error(f"Failed to create backup log: {backup_error}")
            
            # Ensure cursor is closed
            if 'cursor' in locals() and cursor:
                cursor.close()
            return None
    
    @staticmethod
    def get_logs_by_session(session_id):
        """
        Get all proctoring logs for a specific session
        """
        try:
            from extensions import mysql
            cursor = mysql.connection.cursor()
            
            # Check if the table exists
            cursor.execute("SHOW TABLES LIKE 'proctoring_logs'")
            if not cursor.fetchone():
                logger.error("proctoring_logs table does not exist")
                return []
            
            # Get all logs for the session
            cursor.execute("""
                SELECT * FROM proctoring_logs
                WHERE session_id = %s
                ORDER BY timestamp DESC
            """, (session_id,))
            
            results = cursor.fetchall()
            cursor.close()
            
            logs = []
            for row in results:
                # Create log object safely by checking column existence
                log_obj = ProctoringLog(
                    id=row.get('id'),
                    session_id=row.get('session_id'),
                    log_type=row.get('log_type'),
                    details=row.get('details'),
                    timestamp=row.get('timestamp')
                )
                
                # Add screenshot if it exists in the row
                if 'screenshot' in row and row['screenshot']:
                    log_obj.screenshot = row['screenshot']
                    
                logs.append(log_obj)
                
            return logs
            
        except Exception as e:
            logger.error(f"Error retrieving proctoring logs: {e}")
            if 'cursor' in locals() and cursor:
                cursor.close()
            return []
    
    @staticmethod
    def get_violations_summary(session_id):
        """
        Get a summary of violations for a session
        """
        try:
            from extensions import mysql
            cursor = mysql.connection.cursor()
            
            # Check for suspicious activities
            cursor.execute("""
                SELECT log_type, COUNT(*) as count
                FROM proctoring_logs
                WHERE session_id = %s 
                AND log_type IN ('multiple_faces', 'face_missing', 'tab_switch', 
                                'phone_usage_suspected', 'serious_violation')
                GROUP BY log_type
            """, (session_id,))
            
            results = cursor.fetchall()
            cursor.close()
            
            violation_summary = {
                'multiple_faces': 0,
                'face_missing': 0,
                'tab_switch': 0,
                'phone_usage_suspected': 0,
                'serious_violation': 0,
                'total_violations': 0
            }
            
            for row in results:
                violation_type = row.get('log_type')
                count = row.get('count', 0)
                if violation_type in violation_summary:
                    violation_summary[violation_type] = count
                    violation_summary['total_violations'] += count
            
            return violation_summary
            
        except Exception as e:
            logger.error(f"Error getting violations summary: {e}")
            if 'cursor' in locals() and cursor:
                cursor.close()
            return {'error': str(e)}
    
    @staticmethod
    def record_critical_violation(session_id, violation_type, details):
        """
        Record a critical violation that requires immediate attention
        """
        try:
            # Create normal log
            log_id = ProctoringLog.create_log(session_id, violation_type, details)
            
            # Also add to critical violations table if it exists
            from extensions import mysql
            cursor = mysql.connection.cursor()
            
            # Check if critical_violations table exists
            cursor.execute("SHOW TABLES LIKE 'critical_violations'")
            if cursor.fetchone():
                cursor.execute("""
                    INSERT INTO critical_violations 
                    (session_id, violation_type, details, timestamp, needs_review)
                    VALUES (%s, %s, %s, %s, %s)
                """, (session_id, violation_type, details, datetime.now(), True))
                mysql.connection.commit()
            else:
                # Create the table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS critical_violations (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        session_id INT NOT NULL,
                        violation_type VARCHAR(50) NOT NULL,
                        details TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        needs_review BOOLEAN DEFAULT TRUE
                    )
                """)
                mysql.connection.commit()
                
                cursor.execute("""
                    INSERT INTO critical_violations 
                    (session_id, violation_type, details, timestamp, needs_review)
                    VALUES (%s, %s, %s, %s, %s)
                """, (session_id, violation_type, details, datetime.now(), True))
                mysql.connection.commit()
            
            cursor.close()
            return log_id
            
        except Exception as e:
            logger.error(f"Error recording critical violation: {e}")
            return None