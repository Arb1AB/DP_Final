import sqlite3

DB_FILE = "attendance.db"

conn = sqlite3.connect(DB_FILE)
c = conn.cursor()

# Users table (with student_id)
c.execute('''CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT,
                name TEXT,
                student_id TEXT
            )''')

# Courses table
c.execute('''CREATE TABLE IF NOT EXISTS courses (
                id TEXT PRIMARY KEY,
                name TEXT
            )''')

# Attendance table
c.execute('''CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                course_id TEXT,
                checkin_time TEXT
            )''')

# Manual check-in table
c.execute('''CREATE TABLE IF NOT EXISTS manual_checkin (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id TEXT,
                student_name TEXT,
                student_surname TEXT,
                student_id TEXT,
                checkin_time TEXT,
                status TEXT DEFAULT 'pending'
            )''')

# Professor data table
c.execute('''CREATE TABLE IF NOT EXISTS professor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id TEXT,
                student_id TEXT,
                student_name TEXT,
                checkin_time TEXT,
                status TEXT
            )''')

conn.commit()
conn.close()
print("Tables created successfully.")
