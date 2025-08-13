from flask import Flask, render_template, redirect, url_for, session, request, send_file, abort, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from authlib.integrations.flask_client import OAuth
import os
from dotenv import load_dotenv
load_dotenv()
import qrcode
import io
from datetime import datetime, timedelta
import sqlite3
from collections import defaultdict
import socket

# ========================
# CONFIG
# ========================
MASTER_KEY = os.getenv("MASTER_KEY")

# Automatically detect local IP
hostname = socket.gethostname()
local_ip = socket.gethostbyname(hostname)
BASE_URL = "http://192.168.1.100:5000" 

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
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
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

users = {}

@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id)

def get_user_courses(user_id):
    return [{'id': key, 'name': value} for key, value in courses.items()]

def get_current_user():
    return current_user if current_user.is_authenticated else None

# ========================
# DATABASE
# ========================
DB_FILE = "attendance.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT,
                    name TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    course_id TEXT,
                    checkin_time TEXT
                )''')
    # manual_checkin table for pending check-ins
    c.execute('''CREATE TABLE IF NOT EXISTS manual_checkin (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id TEXT,
                    student_name TEXT,
                    student_surname TEXT,
                    student_id TEXT,
                    checkin_time TEXT,
                    status TEXT DEFAULT 'pending'
                )''')
    conn.commit()
    conn.close()

def add_user(user_id, email, name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (id, email, name) VALUES (?, ?, ?)", (user_id, email, name))
    conn.commit()
    conn.close()

def add_attendance(user_id, course_id, checkin_time):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO attendance (user_id, course_id, checkin_time) VALUES (?, ?, ?)",
              (user_id, course_id, checkin_time))
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

def get_attendance(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT course_id, checkin_time FROM attendance WHERE user_id=?", (user_id,))
    data = c.fetchall()
    conn.close()
    return data

# ========================
# ROUTES
# ========================
@app.route('/')
@app.route('/login')
def login():
    if current_user.is_authenticated:
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
        email = user_info['email']
        name = user_info['name']

        if not email.lower().endswith('@uklo.edu.mk'):
            flash('Access denied: Unauthorized email domain.', 'error')
            return redirect(url_for('login'))

        user = User(user_id, email, name)
        users[user_id] = user
        add_user(user_id, email, name)
        login_user(user)
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
    return render_template('dashboard.html', user=current_user, section='courses')

@app.route('/presence_auth', methods=['GET', 'POST'])
@login_required
def presence_auth():
    error = None
    if request.method == 'POST':
        entered_key = request.form.get('access_code')
        if entered_key == MASTER_KEY:
            session['presence_access_granted'] = True
            return redirect(url_for('dashboard_presence'))
        else:
            error = "Invalid master key. Please try again."
    return render_template('presence_auth.html', error=error)

@app.route('/dashboard/presence')
@login_required
def dashboard_presence():
    if not session.get('presence_access_granted'):
        return redirect(url_for('presence_auth'))

    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    courses_list = get_user_courses(user.id)
    raw_records = get_attendance(user.id)

    user_attendance = {}
    has_any_attendance = False
    for course in courses_list:
        course_id = course['id']
        formatted_records = [r[1] for r in raw_records if r[0] == course_id]
        user_attendance[course_id] = formatted_records
        if formatted_records:
            has_any_attendance = True

    return render_template(
        'dashboard_presence.html',
        user=user,
        courses=courses_list,
        attendance=user_attendance,
        has_any_attendance=has_any_attendance
    )

@app.route('/subject_attendance')
@login_required
def subject_attendance():
    subject = request.args.get('subject')
    if not subject:
        return "Subject not specified", 400
    return render_template('subject_attendance.html', subject=subject, user=current_user)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ========================
# QR CODE GENERATION
# ========================
@app.route('/generate_qr/<course_id>')
def generate_qr(course_id):
    key = request.args.get('key')
    if key != MASTER_KEY:
        abort(403)
    if course_id not in courses:
        return f"Invalid course ID: {course_id}", 404

    check_in_url = f"{BASE_URL}/checkin_manual/{course_id}"

    img = qrcode.make(check_in_url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

# ========================
# MANUAL CHECK-IN ROUTE (STUDENT)
# ========================
@app.route('/checkin_manual/<course_id>', methods=['GET', 'POST'])
def checkin_manual(course_id):
    if course_id not in courses:
        return "Invalid course ID", 400

    if request.method == 'POST':
        student_name = request.form.get('student_name')
        student_surname = request.form.get('student_surname')
        student_id = request.form.get('student_id')

        if not all([student_name, student_surname, student_id]):
            flash("Please fill in all fields.", "error")
            return redirect(request.url)

        now = datetime.now()
        add_manual_checkin(course_id, student_name, student_surname, student_id, now.strftime('%Y-%m-%d %H:%M:%S'))
        return f"✅ Your presence has been recorded and is pending professor approval."

    return render_template('manual_checkin.html', course_name=courses[course_id], course_id=course_id)

# ========================
# MANUAL CHECK-IN APPROVAL (PROFESSOR)
# ========================
@app.route('/manual_checkins/<course_id>')
@login_required
def manual_checkins(course_id):
    if course_id not in courses:
        return "Invalid course ID", 400

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, student_name, student_surname, student_id, checkin_time, status FROM manual_checkin WHERE course_id=? AND status='pending'", 
              (course_id,))
    pending = c.fetchall()
    conn.close()

    return render_template('manual_checkins.html', course_id=course_id, course_name=courses[course_id], pending=pending)

@app.route('/manual_checkin_action/<int:checkin_id>/<action>')
@login_required
def manual_checkin_action(checkin_id, action):
    if action not in ['approve', 'reject']:
        return "Invalid action", 400

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    if action == 'approve':
        c.execute("SELECT course_id, student_name, student_surname, student_id, checkin_time FROM manual_checkin WHERE id=?", (checkin_id,))
        row = c.fetchone()
        if row:
            course_id, student_name, student_surname, student_id, checkin_time = row
            # Add to attendance with manual identifier
            c.execute("INSERT INTO attendance (user_id, course_id, checkin_time) VALUES (?, ?, ?)",
                      ('manual:' + student_id, course_id, checkin_time))
            c.execute("UPDATE manual_checkin SET status='approved' WHERE id=?", (checkin_id,))
    else:
        c.execute("UPDATE manual_checkin SET status='rejected' WHERE id=?", (checkin_id,))

    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('dashboard_courses'))

# ========================
# RUN
# ========================
if __name__ == '__main__':
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)