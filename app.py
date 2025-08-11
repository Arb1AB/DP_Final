from flask import Flask, render_template, redirect, url_for, session, request, send_file, abort, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from authlib.integrations.flask_client import OAuth
import os
from dotenv import load_dotenv
load_dotenv()
import qrcode
import io
from datetime import datetime, timedelta
from collections import defaultdict
import socket  # Added for dynamic IP detection

# Master key for professors to generate QR codes
MASTER_KEY = os.getenv("MASTER_KEY")

# Define courses with IDs matching what we'll use in the dropdown and QR generation
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

# Cooldown tracking dictionary
checkin_cooldowns = {}  # Format: {(user_id, course_id): datetime}

# Load environment variables
load_dotenv()

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

# Initialize OAuth
oauth = OAuth(app)

# Configure Google OAuth
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    authorization_endpoint='https://accounts.google.com/o/oauth2/auth',
    token_endpoint='https://oauth2.googleapis.com/token',
    userinfo_endpoint='https://www.googleapis.com/oauth2/v1/userinfo',
    jwks_uri='https://www.googleapis.com/oauth2/v3/certs',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Simple User class
class User(UserMixin):
    def __init__(self, id, email, name):
        self.id = id
        self.email = email
        self.name = name

# Store users in memory (in production, use a database)
users = {}

# Return all courses as list of dicts for presence dropdown
def get_user_courses(user_id):
    return [{'id': key, 'name': value} for key, value in courses.items()]

# Dummy function to get the current user
def get_current_user():
    return current_user if current_user.is_authenticated else None

# User loader function
@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id)

# Store attendance records: user_id -> course_id -> list of datetime
attendance_records = defaultdict(lambda: defaultdict(list))

# Helper function to get local IP dynamically
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))  # arbitrary IP, no real connection made
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

# Login page route
@app.route('/')
@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard_courses'))
    return render_template('login.html')

# Google OAuth login
@app.route('/auth/google')
def google_login():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

# Google OAuth callback with email domain restriction
@app.route('/callback')
def google_callback():
    token = google.authorize_access_token()
    resp = google.get('https://www.googleapis.com/oauth2/v1/userinfo', token=token)
    user_info = resp.json()
    
    if user_info:
        user_id = user_info['id']
        email = user_info['email']
        name = user_info['name']

        # Restrict login to emails ending with '@uklo.edu.mk'
        if not email.lower().endswith('@uklo.edu.mk'):
            flash('Access denied: Unauthorized email domain.', 'error')
            return redirect(url_for('login'))

        user = User(user_id, email, name)
        users[user_id] = user
        login_user(user)
        return redirect(url_for('dashboard_courses'))
    
    flash('Login failed. Please try again.', 'error')
    return redirect(url_for('login'))

# Redirect /dashboard to courses by default
@app.route('/dashboard')
@login_required
def dashboard():
    return redirect(url_for('dashboard_courses'))

# Dashboard - courses view
@app.route('/dashboard/courses')
@login_required
def dashboard_courses():
    return render_template('dashboard.html', user=current_user, section='courses')

# Access code for presence page
PRESENCE_ACCESS_CODE = 'letmein123'  # change this to your preferred secret code

# Presence authorization page for entering the master key
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

    # Get user's courses
    courses_list = get_user_courses(user.id)

    # Prepare attendance data for this user:
    user_attendance = {}
    has_any_attendance = False
    for course in courses_list:
        course_id = course['id']
        records = attendance_records[user.id].get(course_id, [])
        formatted_records = [dt.strftime('%Y-%m-%d %H:%M') for dt in records]
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

# Subject attendance detail view
@app.route('/subject_attendance')
@login_required
def subject_attendance():
    subject = request.args.get('subject')
    if not subject:
        return "Subject not specified", 400

    attendance_data = [
        {'date': '2025-01-20', 'status': 'Present'},
        {'date': '2025-01-22', 'status': 'Absent'},
        {'date': '2025-01-25', 'status': 'Present'},
    ]

    return render_template('subject_attendance.html', subject=subject, attendance=attendance_data, user=current_user)

# Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# QR Code Generation route WITHOUT login requirement — only checks master key
@app.route('/generate_qr/<course_id>')
def generate_qr(course_id):
    key = request.args.get('key')

    if key != MASTER_KEY:
        abort(403)  # Forbidden if key doesn't match

    if course_id not in courses:
        return f"Invalid course ID: {course_id}", 404

    # Use PUBLIC_URL from environment (your ngrok URL), else fallback to local IP
    public_url = os.getenv('PUBLIC_URL')
    if public_url:
        base_url = public_url.rstrip('/')
    else:
        local_ip = get_local_ip()
        base_url = f"http://{local_ip}:5000"

    check_in_url = f"{base_url}/checkin?course_id={course_id}"

    img = qrcode.make(check_in_url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

# Check-in route now requires login and uses current_user.id
@app.route('/checkin')
@login_required
def checkin():
    course_id = request.args.get('course_id')

    if not course_id or course_id not in courses:
        return "Invalid or missing course ID", 400

    user_id = current_user.id
    now = datetime.now()
    cooldown_key = (user_id, course_id)
    last_checkin = checkin_cooldowns.get(cooldown_key)

    if last_checkin and now - last_checkin < timedelta(minutes=10):
        remaining = timedelta(minutes=10) - (now - last_checkin)
        return f"You’ve already checked in. Try again in {int(remaining.total_seconds() // 60) + 1} minutes.", 429

    # Record check-in time
    checkin_cooldowns[cooldown_key] = now
    attendance_records[user_id][course_id].append(now)

    return f"✅ Successfully checked in to course {courses[course_id]} at {now.strftime('%H:%M:%S')}!"

# Run the app
if __name__ == "__main__":
    from waitress import serve
    import os
    port = int(os.environ.get("PORT", 5000))
    serve(app, host="0.0.0.0", port=port)
