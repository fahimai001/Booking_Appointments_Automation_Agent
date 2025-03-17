import sqlite3
import os
import re
import dateparser

# Ensure data directory exists
os.makedirs('database', exist_ok=True)

# Save new appointment in the database
def insert_appointment(name, email, date, time, appointment_reason):
    conn = sqlite3.connect('database/booking.db')
    c = conn.cursor()
    c.execute("INSERT INTO booking (name, email, date, time, appointment_reason) VALUES (?, ?, ?, ?, ?)",
              (name, email, date, time, appointment_reason))
    conn.commit()
    conn.close()

# Fetch appointment detail from the database
def fetch_appointments(name=None, email=None, date=None):
    conn = sqlite3.connect('database/booking.db')
    c = conn.cursor()
    
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
    
    c.execute(query, params)
    appointments = c.fetchall()
    conn.close()
    return appointments

# Checks if a specific appointment already exists.
def appointment_exists(name, email, date, time):
    conn = sqlite3.connect('database/booking.db')
    c = conn.cursor()
    
    c.execute("SELECT * FROM booking WHERE name = ? AND email = ? AND date = ? AND time = ?", 
              (name, email, date, time))
    result = c.fetchone()
    
    conn.close()
    return result is not None

def fetch_table_columns():
    conn = sqlite3.connect('database/booking.db')
    c = conn.cursor()
    c.execute("PRAGMA table_info(booking)")
    columns = c.fetchall()
    conn.close()
    return [col[1] for col in columns]

def setup_database():
    conn = sqlite3.connect('database/booking.db')
    c = conn.cursor()
    
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='booking'")
    table_exists = c.fetchone()
    
    if table_exists:
        try:
            c.execute("SELECT email FROM booking LIMIT 1")
        except sqlite3.OperationalError:
            print("Adding email column to existing database...")
            c.execute("ALTER TABLE booking ADD COLUMN email TEXT DEFAULT 'no-email@example.com'")
            conn.commit()
    else:
        c.execute('''
        CREATE TABLE booking
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         name TEXT NOT NULL,
         email TEXT NOT NULL,
         date TEXT NOT NULL,
         time TEXT NOT NULL,
         appointment_reason TEXT,
         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
        ''')
        conn.commit()
    
    conn.close()