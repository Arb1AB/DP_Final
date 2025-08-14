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
PROFESSOR_EMAIL = os.getenv("PROFESSOR_EMAIL", "abazi.arbisjan@uklo.edu.mk").lower()  # Case-insensitive

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
        # Case-insensitive comparison for professor email
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

def add_attendance(student_id, course_id, checkin_time):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO attendance (user_id, course_id, checkin_time) VALUES (?, ?, ?)",
              (student_id, course_id, checkin_time))
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
    """Get all data for the professor"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT course_id, student_id, student_name, checkin_time, status 
        FROM professor_data
        ORDER BY checkin_time DESC
    """)
    data = c.fetchall()
    conn.close()
    
    # Format data
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
    """Get pending check-ins for professor"""
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

# ========================
# ROUTES
# ========================
@app.route('/')
@app.route('/login')
def login():
    if current_user.is_authenticated:
        if current_user.is_professor:
            return redirect(url_for('professor_dashboard'))
        return redirect(url_for('dashboard'))
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
        email = user_info['email'].lower()  # Normalize to lowercase
        name = user_info['name']
        
        if not email.endswith('@uklo.edu.mk'):
            flash('Access denied: Unauthorized email domain.', 'error')
            return redirect(url_for('login'))

        # Create user
        user = User(user_id, email, name)
        
        # Check if this is the professor
        user.is_professor = (email == PROFESSOR_EMAIL)
        
        # Extract student ID for students
        if not user.is_professor:
            user.student_id = email.split('@')[0].lower()
        
        users[user_id] = user
        
        # Save to DB
        add_user(user_id, email, name, user.student_id if hasattr(user, 'student_id') else None)
        
        login_user(user)
        
        if user.is_professor:
            return redirect(url_for('professor_dashboard'))
        return redirect(url_for('dashboard'))

    flash('Login failed. Please try again.', 'error')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Student dashboard"""
    return render_template('dashboard.html', user=current_user)

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
        abort(403)  # Forbidden for non-professors
    
    # Get professor's data
    professor_data = get_professor_data()
    
    # Get pending check-ins
    pending = get_pending_checkins()
    
    return render_template('professor_dashboard.html', 
                          user=current_user,
                          professor_data=professor_data,
                          pending=pending,
                          courses=courses)

# ========================
# QR CODE & CHECK-IN ROUTES
# ========================
@app.route('/generate_qr/<course_id>')
@login_required
def generate_qr(course_id):
    if not current_user.is_professor:
        abort(403)  # Only professor can generate QR codes
        
    if course_id not in courses:
        return f"Invalid course ID: {course_id}", 404

    check_in_url = f"{BASE_URL}/checkin/{course_id}"

    img = qrcode.make(check_in_url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/checkin/<course_id>')
def checkin_redirect(course_id):
    """Redirect students to manual check-in form"""
    return redirect(url_for('checkin_manual', course_id=course_id))

@app.route('/checkin_manual/<course_id>', methods=['GET', 'POST'])
def checkin_manual(course_id):
    if course_id not in courses:
        return "Invalid course ID", 400

    success = False
    
    if request.method == 'POST':
        student_name = request.form.get('student_name')
        student_surname = request.form.get('student_surname')
        student_id = request.form.get('student_id')

        if not all([student_name, student_surname, student_id]):
            flash("Please fill in all fields.", "error")
            return redirect(request.url)

        now = datetime.now()
        add_manual_checkin(course_id, student_name, student_surname, student_id, now.strftime('%Y-%m-%d %H:%M:%S'))
        success = True

    return render_template('manual_checkin.html', 
                           course_name=courses[course_id], 
                           course_id=course_id,
                           success=success)

# ========================
# MANUAL CHECK-IN APPROVAL (PROFESSOR)
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

    # Get the check-in record
    c.execute("SELECT course_id, student_name, student_surname, student_id, checkin_time FROM manual_checkin WHERE id=?", (checkin_id,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        return "Check-in record not found", 404
        
    course_id, student_name, student_surname, student_id, checkin_time = row
    
    # Update status in manual_checkin table
    if action == 'approve':
        # Add to attendance
        add_attendance(student_id, course_id, checkin_time)
        
        # Add to professor's database
        full_name = f"{student_name} {student_surname}"
        add_to_professor_db(course_id, student_id, full_name, checkin_time, "approved")
        
        # Update status
        c.execute("UPDATE manual_checkin SET status='approved' WHERE id=?", (checkin_id,))
    else:
        # Add to professor's database as rejected
        full_name = f"{student_name} {student_surname}"
        add_to_professor_db(course_id, student_id, full_name, checkin_time, "rejected")
        
        # Update status
        c.execute("UPDATE manual_checkin SET status='rejected' WHERE id=?", (checkin_id,))

    conn.commit()
    conn.close()
    return redirect(url_for('professor_dashboard'))

# ========================
# RUN
# ========================
if __name__ == '__main__':
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)