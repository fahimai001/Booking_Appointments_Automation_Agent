import sqlite3
import os
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

def setup_database():
    """Set up the appointments database if it doesn't exist."""
    os.makedirs('database', exist_ok=True)
    
    conn = sqlite3.connect('database/appointments.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        purpose TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
    ''')
    conn.commit()
    conn.close()
    print("Database setup complete. Database file at: database/appointments.db")

def is_duplicate_appointment(email: str, date: str, time: str) -> bool:
    """Check if an appointment already exists with the same email, date, and time."""
    conn = sqlite3.connect('database/appointments.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM appointments WHERE email = ? AND date = ? AND time = ?",
        (email, date, time)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

def store_appointment(name: str, email: str, date: str, time: str, purpose: str) -> Tuple[bool, str]:
    """Store an appointment in the database."""
    try:
        if not all([name, email, date, time, purpose]):
            return False, "Missing required information"
        
        if is_duplicate_appointment(email, date, time):
            return False, "duplicate"
        
        conn = sqlite3.connect('database/appointments.db')
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO appointments (name, email, date, time, purpose, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (name, email, date, time, purpose, timestamp)
        )
        conn.commit()
        conn.close()
        print(f"Appointment stored successfully for {email} on {date} at {time}")
        return True, "success"
    except Exception as e:
        print(f"Error storing appointment: {e}")
        return False, str(e)

def get_appointments_by_email(email: str) -> List[Dict]:
    """Retrieve appointments by email address."""
    print(f"Looking up appointments for email: {email}")
    
    conn = sqlite3.connect('database/appointments.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, email, date, time, purpose FROM appointments WHERE email = ?", (email,))
    appointments = cursor.fetchall()
    conn.close()

    result = []
    for app in appointments:
        result.append({
            "name": app[0],
            "email": app[1],
            "date": app[2],
            "time": app[3],
            "purpose": app[4]
        })

    print(f"Found {len(result)} appointments for {email}")
    return result