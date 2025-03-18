import sqlite3
import os
import dateparser 

DATABASE_DIR = "database"
DATABASE_FILE = "booking.db"
DATABASE_PATH = os.path.join(DATABASE_DIR, DATABASE_FILE)

os.makedirs(DATABASE_DIR, exist_ok=True)

def insert_appointment(name, email, date, time, appointment_reason):
    """
    Insert a new appointment record into the booking table.
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO booking (name, email, date, time, appointment_reason) VALUES (?, ?, ?, ?, ?)",
            (name, email, date, time, appointment_reason)
        )
        conn.commit()

def fetch_appointments(name=None, email=None, date=None):
    """
    Retrieve appointment records, optionally filtered by name, email, and date.
    Results are ordered by date and time.
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM booking"
        params = []
        conditions = []
        
        if name:
            conditions.append("name = ?")
            params.append(name)
        if email:
            conditions.append("email = ?")
            params.append(email)
        if date:
            conditions.append("date = ?")
            params.append(date)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY date, time"
        cursor.execute(query, params)
        appointments = cursor.fetchall()
    return appointments

def appointment_exists(name, email, date, time):
    """
    Check if an appointment exists in the booking table for the provided details.
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM booking WHERE name = ? AND email = ? AND date = ? AND time = ?",
            (name, email, date, time)
        )
        exists = cursor.fetchone() is not None
    return exists

def fetch_table_columns():
    """
    Get a list of column names for the booking table.
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(booking)")
        columns_info = cursor.fetchall()
    return [col[1] for col in columns_info]

def setup_database():
    """
    Set up the database by creating the booking table if it doesn't exist,
    or modifying it if needed.
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='booking'")
        table_exists = cursor.fetchone()
        
        if table_exists:
            try:
                cursor.execute("SELECT email FROM booking LIMIT 1")
            except sqlite3.OperationalError:
                print("Email column missing. Adding email column to the booking table...")
                cursor.execute("ALTER TABLE booking ADD COLUMN email TEXT DEFAULT 'no-email@example.com'")
                conn.commit()
        else:
            cursor.execute('''
                CREATE TABLE booking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    date TEXT NOT NULL,
                    time TEXT NOT NULL,
                    appointment_reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

if __name__ == "__main__":
    setup_database()
