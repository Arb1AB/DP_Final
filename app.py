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
import socket

# ========================
# CONFIG
# ========================
MASTER_KEY = os.getenv("MASTER_KEY", "arbi123")
PROFESSOR_EMAIL = os.getenv("PROFESSOR_EMAIL", "abazi.arbisjan@uklo.edu.mk").lower()

# Automatically detect local IP
hostname = socket.gethostname()
local_ip = socket.gethostbyname(hostname)
BASE_URL = os.getenv("BASE_URL", f"http://{local_ip}:5000")

# Courses organized by year
courses_by_year = {
    '1st Year': {
        '1': 'Математика 1',
        '2': 'Дигитална логика и системи',
        '3': 'Структурирано програмирање',
        '4': 'Апликативен софтвер',
        '5': 'Математика 2',
        '6': 'Архитектура и организација на компјутери',
        '7': 'Веб технологии',
        '8': 'Напредно програмирање'
    },
    '2nd Year': {
        '9': 'Системски софтвер',
        '10': 'Податочни комуникации и мрежи',
        '11': 'Алгоритми и структури на податоци',
        '12': 'Објектно ориентирано програмирање',
        '13': 'Бази на податоци',
        '14': 'Компјутерска графика',
        '15': 'Проектирање и менаџмент на компјутерски мрежи',
        '16': 'Солид моделирање'
    },
    '3rd Year': {
        '17': 'Деловни информациски системи',
        '18': 'Математичко моделирање и компјутерски симулации',
        '19': 'Анализа и логички дизајн на информациски системи',
        '20': 'Принципи на мултимедиски системи',
        '21': 'Веб програмирање',
        '22': 'Основи на вештачка интелигенција',
        '23': 'Индустриска информатика',
        '24': 'Неструктурирани бази на податоци'
    },
    '4th Year': {
        '25': 'Безбедност на компјутерски системи и мрежи',
        '26': 'Роботика и автоматизација',
        '27': 'Податочно рударење и аналитика на големи количества на податоци',
        '28': 'Сервисно-ориентирани архитектури',
        '29': 'Безжични комуникации',
        '30': 'Бизнис интелигенција и системи за поддршка на одлучување',
        '31': 'Програмирање за мобилни платформи',
        '32': 'Системи базирани на знаење'
    },
    'Electives': {
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
}

# Flattened courses for other functions
all_courses = {}
for year_courses in courses_by_year.values():
    all_courses.update(year_courses)

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
    def __init__(self, id, email, name, student_id=None):
        self.id = id
        self.email = email
        self.name = name
        self.student_id = student_id
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

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Users table
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
    
    # Manual checkin table
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
    
    # Insert courses
    for cid, cname in all_courses.items():
        c.execute("INSERT OR IGNORE INTO courses (id, name) VALUES (?, ?)", (cid, cname))
    
    conn.commit()
    conn.close()

def add_user(user_id, email, name, student_id=None):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO users (id, email, name, student_id)
            VALUES (?, ?, ?, ?)
        """, (user_id, email, name, student_id))
        conn.commit()

def add_attendance(user_id, course_id, checkin_time):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO attendance (user_id, course_id, checkin_time)
            VALUES (?, ?, ?)
        """, (user_id, course_id, checkin_time))
        conn.commit()

def add_to_professor_db(course_id, student_id, student_name, checkin_time, status):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO professor_data (course_id, student_id, student_name, checkin_time, status)
            VALUES (?, ?, ?, ?, ?)
        """, (course_id, student_id, student_name, checkin_time, status))
        conn.commit()

def add_manual_checkin(course_id, student_name, student_surname, student_id, checkin_time):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO manual_checkin (course_id, student_name, student_surname, student_id, checkin_time)
            VALUES (?, ?, ?, ?, ?)
        """, (course_id, student_name, student_surname, student_id, checkin_time))
        conn.commit()

def get_pending_checkins():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, course_id, student_name, student_surname, student_id, checkin_time
            FROM manual_checkin
            WHERE status='pending'
        """)
        return c.fetchall()

# get_attendance_by_course function in app.py
def get_attendance_by_course(course_id):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT a.id, 
                   COALESCE(u.name, pd.student_name) as student_name,
                   COALESCE(u.student_id, pd.student_id) as student_id,
                   a.checkin_time
            FROM attendance a
            LEFT JOIN users u ON a.user_id = u.id
            LEFT JOIN professor_data pd ON a.user_id = pd.student_id AND a.course_id = pd.course_id
            WHERE a.course_id = ?
            ORDER BY a.checkin_time DESC
        """, (course_id,))
        return c.fetchall()

# ========================
# ROUTES
# ========================
@app.route('/')
@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/auth/google')
def google_login():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/callback', methods=['GET'])
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
        
        users[user_id] = user
        add_user(user_id, email, name)
        login_user(user)
        
        return redirect(url_for('dashboard'))

    flash('Login failed. Please try again.', 'error')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', 
                          user=current_user,
                          courses_by_year=courses_by_year)

@app.route('/course/<course_id>')
@login_required
def course_attendance(course_id):
    if course_id not in all_courses:
        abort(404, description="Course not found")
    
    attendance = get_attendance_by_course(course_id)
    
   
    return render_template('course_attendance.html',
                           user=current_user,
                           course_id=course_id,
                           course_name=all_courses[course_id],
                           attendance=attendance)

@app.route('/presence')
@login_required
def presence():
    return render_template('presence.html',
                           user=current_user,
                           courses=all_courses)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ========================
# MANUAL CHECK-IN ROUTES
# ========================
@app.route('/checkin/<course_id>')
def checkin_redirect(course_id):
    return redirect(url_for('checkin_manual', course_id=course_id))

@app.route('/checkin_manual/<course_id>', methods=['GET', 'POST'])
def checkin_manual(course_id):
    if course_id not in all_courses:
        return "Invalid course ID", 400

    # STEP 1: Choice screen – first visit, no action yet
    if request.method == 'GET' and 'action' not in request.args:
        return render_template('manual_checkin.html',
                               course_name=all_courses[course_id],
                               course_id=course_id,
                               step="choose")

    # STEP 2: Manual form submission
    if request.method == 'POST':
        student_name = request.form.get('student_name')
        student_surname = request.form.get('student_surname')
        student_id = request.form.get('student_id')

        if not all([student_name, student_surname, student_id]):
            flash("Please fill in all fields.", "error")
            return redirect(request.url)

        now = datetime.now()
        if current_user.is_authenticated:
            add_user(current_user.id, current_user.email, current_user.name, student_id)
        else:
            temp_id = f"manual_{student_id}"
            add_user(temp_id, None, f"{student_name} {student_surname}", student_id)

        add_manual_checkin(course_id, student_name, student_surname, student_id, now.strftime('%Y-%m-%d %H:%M:%S'))

        session['last_manual_checkin'] = {'student_id': student_id, 'course_id': course_id}
        return redirect(url_for('checkin_manual', course_id=course_id, action="manual"))

    # STEP 3: Show success after form submission
    last = session.get('last_manual_checkin')
    success = last and last.get('course_id') == course_id
    if not success:
        session.pop('last_manual_checkin', None)

    return render_template('manual_checkin.html',
                           course_name=all_courses[course_id],
                           course_id=course_id,
                           step="manual_form",
                           success=success)


# ========================
# QR CODE & APPROVAL ROUTES
# ========================
@app.route('/generate_qr/<course_id>')
@login_required
def generate_qr(course_id):
    if course_id not in all_courses:
        return f"Invalid course ID: {course_id}", 404

    check_in_url = f"{BASE_URL}/checkin/{course_id}"

    img = qrcode.make(check_in_url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/manual_checkins')
@login_required
def manual_checkins():
    pending = get_pending_checkins()
    return render_template('manual_checkins.html',
                           user=current_user,
                           pending=pending,
                           courses=all_courses)

@app.route('/manual_checkin_action/<int:checkin_id>/<action>')
@login_required
def manual_checkin_action(checkin_id, action):
    if action not in ['approve', 'reject']:
        return "Invalid action", 400

    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT course_id, student_name, student_surname, student_id, checkin_time FROM manual_checkin WHERE id=?", (checkin_id,))
        row = c.fetchone()
        
        if not row:
            return "Check-in record not found", 404
            
        course_id, student_name, student_surname, student_id, checkin_time = row
        
        full_name = f"{student_name} {student_surname}"
        if action == 'approve':
            add_attendance(student_id, course_id, checkin_time)
            add_to_professor_db(course_id, student_id, full_name, checkin_time, "approved")
            c.execute("UPDATE manual_checkin SET status='approved' WHERE id=?", (checkin_id,))
        else:
            add_to_professor_db(course_id, student_id, full_name, checkin_time, "rejected")
            c.execute("UPDATE manual_checkin SET status='rejected' WHERE id=?", (checkin_id,))
        conn.commit()

    return redirect(url_for('manual_checkins'))

# ========================
# ERROR HANDLERS
# ========================
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

# ========================
# RUN
# ========================
if __name__ == '__main__':
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
