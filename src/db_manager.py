import sqlite3
from datetime import datetime
import re
from datetime import timedelta
import os

class DatabaseManager:
    def __init__(self, db_path="appointments.db"):
        """Initialize database connection and create tables if they don't exist."""
        self.db_path = os.path.abspath(db_path)
        print(f"Using database at: {self.db_path}")
        self.conn = None
        self.cursor = None
        self.connect()
        self.create_tables()
    
    def connect(self):
        """Establish connection to the SQLite database."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            print("Database connected successfully")
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None
    
    def create_tables(self):
        """Create the appointments table if it doesn't exist."""
        try:
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                email TEXT NOT NULL,
                appointment_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            self.conn.commit()
            print("Table created or already exists")
        except sqlite3.Error as e:
            print(f"Error creating tables: {e}")
    
    def save_appointment(self, appointment_data):
        """
        Save appointment data to the database.
        
        Args:
            appointment_data (dict): Dictionary containing appointment details
                with keys: user_name, date, time, email, appointment_type
        
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            if self.conn is None or self.cursor is None:
                self.connect()
            
            print(f"Attempting to save appointment: {appointment_data}")
            
            required_fields = ["user_name", "date", "time", "email", "appointment_type"]
            if not all(field in appointment_data for field in required_fields):
                missing = [f for f in required_fields if f not in appointment_data]
                print(f"Missing required appointment fields: {missing}")
                return False, f"Missing required fields: {', '.join(missing)}"
            
            query = '''
            SELECT COUNT(*) FROM appointments 
            WHERE date = ? AND time = ? AND email = ?
            '''
            self.cursor.execute(query, (
                appointment_data['date'],
                appointment_data['time'],
                appointment_data['email']
            ))
            if self.cursor.fetchone()[0] > 0:
                return False, "You already have an appointment scheduled at this time"
            
            query = '''
            INSERT INTO appointments (user_name, date, time, email, appointment_type)
            VALUES (?, ?, ?, ?, ?)
            '''
            self.cursor.execute(query, (
                appointment_data['user_name'],
                appointment_data['date'],
                appointment_data['time'],
                appointment_data['email'],
                appointment_data['appointment_type']
            ))
            
            self.conn.commit()
            
            self.cursor.execute('''
            SELECT COUNT(*) FROM appointments WHERE email = ? AND date = ? AND time = ?
            ''', (
                appointment_data['email'],
                appointment_data['date'],
                appointment_data['time']
            ))
            
            if self.cursor.fetchone()[0] > 0:
                print(f"Appointment saved successfully with ID: {self.cursor.lastrowid}")
                return True, f"Appointment saved with ID: {self.cursor.lastrowid}"
            else:
                print("Appointment not saved despite no errors")
                return False, "Failed to save appointment (database transaction issue)"
                
        except sqlite3.Error as e:
            print(f"Error saving appointment: {e}")
            return False, f"Database error: {str(e)}"
    
    def get_all_appointments(self):
        """
        Retrieve all appointments in the database.
        
        Returns:
            list: List of appointment dictionaries
        """
        try:
            if self.conn is None or self.cursor is None:
                self.connect()
                
            query = "SELECT * FROM appointments ORDER BY date, time"
            self.cursor.execute(query)
            
            appointments = [dict(row) for row in self.cursor.fetchall()]
            print(f"Retrieved {len(appointments)} total appointments")
            return appointments
        except sqlite3.Error as e:
            print(f"Error retrieving all appointments: {e}")
            return []
    
    def get_appointments(self, email=None, date=None):
        """
        Retrieve appointments, optionally filtered by email and/or date.
        
        Args:
            email (str, optional): Filter appointments by this email
            date (str, optional): Filter appointments by this date (YYYY-MM-DD format)
        
        Returns:
            list: List of appointment dictionaries
        """
        try:
            if self.conn is None or self.cursor is None:
                self.connect()
                
            params = []
            query = "SELECT * FROM appointments WHERE 1=1"
            
            if email:
                query += " AND email = ?"
                params.append(email)
            
            if date:
                query += " AND date = ?"
                params.append(date)
            
            query += " ORDER BY date, time"
            
            print(f"Executing query: {query} with params: {params}")
            self.cursor.execute(query, params)
            
            appointments = [dict(row) for row in self.cursor.fetchall()]
            print(f"Retrieved {len(appointments)} appointments for email: {email}, date: {date}")
            return appointments
        except sqlite3.Error as e:
            print(f"Error retrieving appointments: {e}")
            return []
    
    def get_appointments_by_date(self, date, email=None):
        """
        Retrieve appointments for a specific date, optionally filtered by email.
        
        Args:
            date (str): Date to filter appointments by (YYYY-MM-DD format)
            email (str, optional): Email to filter appointments by
        
        Returns:
            list: List of appointment dictionaries
        """
        return self.get_appointments(email=email, date=date)
    
    def get_future_appointments(self, email=None):
        """
        Retrieve all future appointments, optionally filtered by email.
        
        Args:
            email (str, optional): Email to filter appointments by
            
        Returns:
            list: List of appointment dictionaries
        """
        try:
            if self.conn is None or self.cursor is None:
                self.connect()
                
            today = datetime.now().strftime("%Y-%m-%d")
            current_time = datetime.now().strftime("%H:%M")
            
            params = [today, today, current_time]
            query = """
            SELECT * FROM appointments 
            WHERE (date > ? OR (date = ? AND time >= ?))
            """
            
            if email:
                query += " AND email = ?"
                params.append(email)
            
            query += " ORDER BY date, time"
            
            print(f"Executing future appointments query: {query} with params: {params}")
            self.cursor.execute(query, params)
            
            appointments = [dict(row) for row in self.cursor.fetchall()]
            print(f"Retrieved {len(appointments)} future appointments for email: {email}")
            return appointments
        except sqlite3.Error as e:
            print(f"Error retrieving future appointments: {e}")
            return []
    
    def get_next_appointment(self, email=None):
        """
        Get the next upcoming appointment, optionally filtered by email.
        
        Args:
            email (str, optional): Email to filter by
            
        Returns:
            dict or None: The next appointment or None if no future appointments
        """
        future_appointments = self.get_future_appointments(email)
        return future_appointments[0] if future_appointments else None
    
    def delete_appointment(self, appointment_id):
        """
        Delete an appointment by ID.
        
        Args:
            appointment_id (int): ID of the appointment to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            if self.conn is None or self.cursor is None:
                self.connect()
                
            query = "DELETE FROM appointments WHERE id = ?"
            self.cursor.execute(query, (appointment_id,))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error deleting appointment: {e}")
            return False
    
    def format_appointment_response(self, appointments):
        """
        Format appointments into a readable string for the chatbot response.
        
        Args:
            appointments (list): List of appointment dictionaries
            
        Returns:
            str: Formatted string of appointments
        """
        if not appointments:
            return "You don't have any appointments scheduled."
        
        formatted = "Here are your appointment details:\n\n"
        for i, appt in enumerate(appointments, 1):
            formatted += f"Appointment {i}:\n"
            formatted += f"- Name: {appt['user_name']}\n"
            formatted += f"- Date: {appt['date']}\n"
            formatted += f"- Time: {appt['time']}\n"
            formatted += f"- Service: {appt['appointment_type']}\n\n"
        
        return formatted

def is_appointment_query(text):
    """Check if text is asking about appointments"""
    query_patterns = [
        r"(do i have|any|my).*appointment",
        r"(when|what).*appointment",
        r"(check|show|list|view|get).*appointment",
        r"(upcoming|next|scheduled).*appointment",
        r"appointment.*(today|tomorrow|this week|next week)",
        r"appointment.*(check|status|detail)",
    ]
    
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in query_patterns)

def extract_date_from_query(text):
    """Extract date information from query text"""
    today_patterns = [r"today", r"this day"]
    tomorrow_patterns = [r"tomorrow", r"next day"]
    
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in today_patterns):
        return datetime.now().strftime("%Y-%m-%d")
    
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in tomorrow_patterns):
        tomorrow = datetime.now() + timedelta(days=1)
        return tomorrow.strftime("%Y-%m-%d")
    
    date_patterns = [
        r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})",
        r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})"
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0).replace("/", "-").replace("\\", "-")
    
    return None

def extract_email_from_query(text):
    """Extract email from query text"""
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    match = re.search(email_pattern, text)
    return match.group(0) if match else None