from flask import Flask, render_template, redirect, url_for, session, request, send_file, abort, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from authlib.integrations.flask_client import OAuth
import os
from dotenv import load_dotenv
load_dotenv()
import qrcode
import io
from datetime import datetime
import sqlite3
from collections import defaultdict
import socket
from flask import jsonify
# ========================
# CONFIG
# ========================
MASTER_KEY = os.getenv("MASTER_KEY", "arbi123")
PROFESSOR_EMAIL = os.getenv("PROFESSOR_EMAIL", "abazi.arbisjan@uklo.edu.mk").lower()

# Automatically detect local IP
hostname = socket.gethostname()
local_ip = socket.gethostbyname(hostname)
BASE_URL = os.getenv("BASE_URL", f"http://{local_ip}:5000")

courses = {
    '1': 'Математика 1',
    '2': 'Дигитална логика и системи',
    '3': 'Структурирано програмирање',
    '4': 'Апликативен софтвер',
    '5': 'Математика 2',
    '6': 'Архитектура и организација на компјутери',
    '7': 'Веб технологии',
    '8': 'Напредно програмирање',
    '9': 'Системски софтвер',
    '10': 'Податочни комуникации и мрежи',
    '11': 'Алгоритми и структури на податоци',
    '12': 'Објектно ориентирано програмирање',
    '13': 'Бази на податоци',
    '14': 'Компјутерска графика',
    '15': 'Проектирање и менаџмент на компјутерски мрежи',
    '16': 'Солид моделирање',
    '17': 'Деловни информациски системи',
    '18': 'Математичко моделирање и компјутерски симулации',
    '19': 'Анализа и логички дизајн на информациски системи',
    '20': 'Принципи на мултимедиски системи',
    '21': 'Веб програмирање',
    '22': 'Основи на вештачка интелигенција',
    '23': 'Индустриска информатика',
    '24': 'Неструктурирани бази на податоци',
    '25': 'Безбедност на компјутерски системи и мрежи',
    '26': 'Роботика и автоматизација',
    '27': 'Податочно рударење и аналитика на големи количества на податоци',
    '28': 'Сервисно-ориентирани архитектури',
    '29': 'Безжични комуникации',
    '30': 'Бизнис интелигенција и системи за поддршка на одлучување',
    '31': 'Програмирање за мобилни платформи',
    '32': 'Системи базирани на знаење',
    '33': 'Иновациски менаџмент',
    '34': 'Финансиски технологии',
    '35': 'Интелектуален капитал и конкурентност',
    '36': 'е-влада и е-управување',
    '37': 'Организациско однесување и развој',
    '38': 'Англиски за специфични цели',
    '39': 'Англиски јазик за основни вештини',
    '40': 'Деловни комуникациски вештини',
    '41': 'Економија и бизнис',
    '42': 'Концепти на информатичко општество',
    '43': 'Интернет банкарство',
    '44': 'Организациско претприемништво',
    '45': 'Криптографија и информациска безбедност',
    '46': 'Комуникациски технологии',
    '47': 'Обработка на природен јазик'
}

# ========================
# GLOBALS
# ========================
checkin_cooldowns = {}       # {(user_id, course_id): datetime}
qr_code_timestamps = {}      # {course_id: datetime}

# ========================
# FLASK APP & LOGIN
# ========================
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID', '139131999772-e9rghkdiic7tfop94s7tqgn7ckd9ilr5.apps.googleusercontent.com'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET', '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'),
    authorization_endpoint='https://accounts.google.com/o/oauth2/auth',
    token_endpoint='https://oauth2.googleapis.com/token',
    userinfo_endpoint='https://www.googleapis.com/oauth2/v1/userinfo',
    jwks_uri='https://www.googleapis.com/oauth2/v3/certs',
    client_kwargs={'scope': 'openid email profile'}
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, email, name):
        self.id = id
        self.email = email
        self.name = name
        self.student_id = None
        self.is_professor = (email.lower() == PROFESSOR_EMAIL)

users = {}

@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id)

def get_current_user():
    return current_user if current_user.is_authenticated else None

# ========================
# DATABASE
# ========================
DB_FILE = "attendance.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Create users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT,
                    name TEXT,
                    student_id TEXT
                )''')
    
    # Create courses table
    c.execute('''CREATE TABLE IF NOT EXISTS courses (
                    id TEXT PRIMARY KEY,
                    name TEXT
                )''')
    
    # Create attendance table
    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                student_name TEXT,
                course_id TEXT,
                checkin_time TEXT
            )''')

    
    # Create manual_checkin table
    c.execute('''CREATE TABLE IF NOT EXISTS manual_checkin (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id TEXT,
                    student_name TEXT,
                    student_surname TEXT,
                    student_id TEXT,
                    checkin_time TEXT,
                    status TEXT DEFAULT 'pending'
                )''')
    
    # Create professor_data table
    c.execute('''CREATE TABLE IF NOT EXISTS professor_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id TEXT,
                    student_id TEXT,
                    student_name TEXT,
                    checkin_time TEXT,
                    status TEXT
                )''')
    
    # Insert courses if not exists
    for cid, cname in courses.items():
        c.execute("INSERT OR IGNORE INTO courses (id, name) VALUES (?, ?)", (cid, cname))
    
    conn.commit()
    conn.close()

def add_user(user_id, email, name, student_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""INSERT OR IGNORE INTO users (id, email, name, student_id) 
                 VALUES (?, ?, ?, ?)""", 
              (user_id, email, name, student_id))
    conn.commit()
    conn.close()

def add_attendance(user_id, course_id, checkin_time, student_name=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO attendance (user_id, course_id, checkin_time, student_name) VALUES (?, ?, ?, ?)",
        (user_id, course_id, checkin_time, student_name)
    )
    conn.commit()
    conn.close()


def add_to_professor_db(course_id, student_id, student_name, checkin_time, status):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO professor_data (course_id, student_id, student_name, checkin_time, status) VALUES (?, ?, ?, ?, ?)",
        (course_id, student_id, student_name, checkin_time, status)
    )
    conn.commit()
    conn.close()

def add_manual_checkin(course_id, student_name, student_surname, student_id, checkin_time):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO manual_checkin (course_id, student_name, student_surname, student_id, checkin_time) VALUES (?, ?, ?, ?, ?)",
        (course_id, student_name, student_surname, student_id, checkin_time)
    )
    conn.commit()
    conn.close()

def get_professor_data():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT course_id, student_id, student_name, checkin_time, status 
        FROM professor_data
        ORDER BY checkin_time DESC
    """)
    data = c.fetchall()
    conn.close()
    
    professor_data = []
    for row in data:
        course_id, student_id, student_name, checkin_time, status = row
        course_name = courses.get(course_id, f"Unknown Course ({course_id})")
        professor_data.append({
            'course_id': course_id,
            'course_name': course_name,
            'student_id': student_id,
            'student_name': student_name,
            'checkin_time': checkin_time,
            'status': status
        })
    
    return professor_data

def get_pending_checkins():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT id, course_id, student_name, student_surname, student_id, checkin_time 
        FROM manual_checkin 
        WHERE status='pending'
    """)
    pending = c.fetchall()
    conn.close()
    return pending

def get_attendance_by_course(course_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Fetch regular attendance
    c.execute("""
        SELECT a.id, u.name, u.student_id, a.checkin_time
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        WHERE a.course_id = ?
    """, (course_id,))
    regular_attendance = c.fetchall()

    # Fetch approved manual check-ins
    c.execute("""
        SELECT id, student_name || ' ' || student_surname AS full_name, student_id, checkin_time
        FROM manual_checkin
        WHERE course_id = ? AND status='approved'
    """, (course_id,))
    manual_attendance = c.fetchall()

    conn.close()

    # Combine both lists
    combined = list(regular_attendance) + list(manual_attendance)

    # Sort by check-in time descending
    combined.sort(key=lambda x: x[3], reverse=True)

    return combined



def get_student_attendance(student_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT a.course_id, c.name, a.checkin_time
        FROM attendance a
        JOIN courses c ON a.course_id = c.id
        WHERE a.user_id = ?
        ORDER BY a.checkin_time DESC
    """, (student_id,))
    attendance = c.fetchall()
    conn.close()
    
    # Group by course
    attendance_by_course = defaultdict(list)
    for course_id, course_name, checkin_time in attendance:
        attendance_by_course[course_id].append({
            'course_name': course_name,
            'checkin_time': checkin_time
        })
    
    return attendance_by_course

# ========================
# ROUTES
# ========================
@app.route('/')
@app.route('/login')
def login():
    if current_user.is_authenticated:
        if current_user.is_professor:
            return redirect(url_for('professor_dashboard'))
        return redirect(url_for('dashboard_courses'))
    return render_template('login.html')

@app.route('/auth/google')
def google_login():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/callback')
def google_callback():
    token = google.authorize_access_token()
    resp = google.get('https://www.googleapis.com/oauth2/v1/userinfo', token=token)
    user_info = resp.json()

    if user_info:
        user_id = user_info['id']
        email = user_info['email'].lower()
        name = user_info['name']
        
        if not email.endswith('@uklo.edu.mk'):
            flash('Access denied: Unauthorized email domain.', 'error')
            return redirect(url_for('login'))

        user = User(user_id, email, name)
        user.is_professor = (email == PROFESSOR_EMAIL)
        
        if not user.is_professor:
            user.student_id = email.split('@')[0].lower()
        
        users[user_id] = user
        add_user(user_id, email, name, user.student_id if hasattr(user, 'student_id') else None)
        login_user(user)
        
        if user.is_professor:
            return redirect(url_for('professor_dashboard'))
        return redirect(url_for('dashboard_courses'))

    flash('Login failed. Please try again.', 'error')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return redirect(url_for('dashboard_courses'))

@app.route('/dashboard/courses')
@login_required
def dashboard_courses():
    if current_user.is_professor:
        # Professor sees all courses
        courses_list = [{'id': cid, 'name': cname} for cid, cname in courses.items()]
    else:
        # Student sees courses they've attended
        attendance = get_student_attendance(current_user.id)
        courses_list = []
        for course_id, records in attendance.items():
            if records:
                courses_list.append({
                    'id': course_id,
                    'name': records[0]['course_name']
                })
    
    return render_template('dashboard.html', 
                          user=current_user, 
                          courses=courses_list,
                          section='courses')

@app.route('/course/<course_id>')
@login_required
def course_attendance(course_id):
    if course_id not in courses:
        abort(404, description="Course not found")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    if current_user.is_professor:
        # Professor sees all attendance for the course (regular + approved manual)
        c.execute("""
            SELECT a.id, u.name, u.student_id, a.checkin_time
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            WHERE a.course_id = ?
            ORDER BY a.checkin_time DESC
        """, (course_id,))
        regular = c.fetchall()

        # Include approved manual check-ins
        c.execute("""
            SELECT id, student_name || ' ' || student_surname AS name, student_id, checkin_time
            FROM manual_checkin
            WHERE course_id = ? AND status='approved'
            ORDER BY checkin_time DESC
        """, (course_id,))
        manual = c.fetchall()

        # Combine both
        attendance = regular + manual

        conn.close()
        return render_template('course_attendance.html',
                               user=current_user,
                               course_id=course_id,
                               course_name=courses[course_id],
                               attendance=attendance)
    else:
        # Student sees only their own attendance (regular + approved manual)
        c.execute("""
            SELECT a.id, u.name, u.student_id, a.checkin_time
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            WHERE a.user_id = ? AND a.course_id = ?
            ORDER BY a.checkin_time DESC
        """, (current_user.id, course_id))
        regular = c.fetchall()

        c.execute("""
            SELECT id, student_name || ' ' || student_surname AS name, student_id, checkin_time
            FROM manual_checkin
            WHERE student_id = ? AND course_id = ? AND status='approved'
            ORDER BY checkin_time DESC
        """, (current_user.student_id, course_id))
        manual = c.fetchall()

        attendance = regular + manual

        conn.close()
        return render_template('course_attendance_student.html',
                               user=current_user,
                               course_id=course_id,
                               course_name=courses[course_id],
                               attendance=attendance)



@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ========================
# PROFESSOR ROUTES
# ========================
@app.route('/professor')
@login_required
def professor_dashboard():
    if not current_user.is_professor:
        abort(403)
    
    pending = get_pending_checkins()
    
    return render_template('professor_dashboard.html', 
                          user=current_user,
                          pending=pending,
                          courses=courses)

@app.route('/professor/manual_checkins/<course_id>')
@login_required
def professor_manual_checkins(course_id):
    if not current_user.is_professor:
        abort(403)
    
    if course_id not in courses:
        abort(404, description="Course not found")
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT id, student_name, student_surname, student_id, checkin_time 
        FROM manual_checkin 
        WHERE course_id = ? AND status='pending'
    """, (course_id,))
    pending = c.fetchall()
    conn.close()
    
    return render_template('manual_checkins.html',
                           user=current_user,
                           course_id=course_id,
                           course_name=courses[course_id],
                           pending=pending)

# ========================
# QR CODE & CHECK-IN ROUTES
# ========================
@app.route('/generate_qr/<course_id>')
@login_required
def generate_qr(course_id):
    if not current_user.is_professor:
        abort(403)
        
    if course_id not in courses:
        return f"Invalid course ID: {course_id}", 404

    check_in_url = f"{BASE_URL}/checkin/{course_id}"

    img = qrcode.make(check_in_url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/checkin/<course_id>')
@login_required
def checkin(course_id):
    if current_user.is_professor:
        return "Professors cannot check-in", 403
    
    now = datetime.now()
    
    # Check cooldown
    key = (current_user.id, course_id)
    last_checkin = checkin_cooldowns.get(key)
    if last_checkin and (now - last_checkin).total_seconds() < 60:  # 60s cooldown
        return "Please wait before checking in again", 429
    
    checkin_time = now.strftime("%Y-%m-%d %H:%M:%S")
    add_attendance(current_user.id, course_id, checkin_time, student_name=current_user.name)
    checkin_cooldowns[key] = now
    
    return f"Checked in successfully at {checkin_time}!"

# ========================
# MANUAL CHECK-IN ACTION
# ========================
@app.route('/manual_checkin_action/<int:checkin_id>/<action>')
@login_required
def manual_checkin_action(checkin_id, action):
    if not current_user.is_professor:
        abort(403)
        
    if action not in ['approve', 'reject']:
        return "Invalid action", 400

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT course_id, student_name, student_surname, student_id, checkin_time 
        FROM manual_checkin 
        WHERE id=?
    """, (checkin_id,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        return "Check-in record not found", 404
        
    course_id, student_name, student_surname, student_id, checkin_time = row
    full_name = f"{student_name} {student_surname}"
    
    if action == 'approve':
        # Add to attendance table **with full name**
        add_attendance(student_id, course_id, checkin_time, student_name=full_name)
        add_to_professor_db(course_id, student_id, full_name, checkin_time, "approved")
        c.execute("UPDATE manual_checkin SET status='approved' WHERE id=?", (checkin_id,))
    else:
        add_to_professor_db(course_id, student_id, full_name, checkin_time, "rejected")
        c.execute("UPDATE manual_checkin SET status='rejected' WHERE id=?", (checkin_id,))

    conn.commit()
    conn.close()
    
    return redirect(url_for('course_attendance', course_id=course_id))


# ========================
# INIT
# ========================
if __name__ == "__main__":
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
