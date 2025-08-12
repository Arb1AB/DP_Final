from flask import Flask, render_template, redirect, url_for, session, request, send_file, abort, flash, get_flashed_messages
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from authlib.integrations.flask_client import OAuth
import os
from dotenv import load_dotenv
import qrcode
import io
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# Load environment variables
load_dotenv()

MASTER_KEY = os.getenv("MASTER_KEY")

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

checkin_cooldowns = {}

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
    client_kwargs={
        'scope': 'openid email profile'
    }
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

def get_user_courses(user_id):
    return [{'id': key, 'name': value} for key, value in courses.items()]

def get_current_user():
    return current_user if current_user.is_authenticated else None

@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id)

attendance_records = defaultdict(lambda: defaultdict(list))

@app.route('/')
@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard_courses'))
    messages = get_flashed_messages(with_categories=True)
    return render_template('login.html', messages=messages)

# <-- THIS IS THE FIX: add prompt='select_account' to force account chooser -->
@app.route('/auth/google')
def google_login():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri, prompt='select_account')

@app.route('/callback')
def google_callback():
    token = google.authorize_access_token()
    resp = google.get('https://www.googleapis.com/oauth2/v1/userinfo', token=token)
    user_info = resp.json()

    if user_info:
        user_id = user_info['id']
        email = user_info['email']
        name = user_info.get('name', '')

        allowed_domains = [d.strip().lower() for d in os.getenv('ALLOWED_EMAIL_DOMAINS', '').split(',') if d.strip()]
        allowed_emails = [e.strip().lower() for e in os.getenv('ALLOWED_EMAILS', '').split(',') if e.strip()]

        email_lower = email.lower()

        domain_allowed = any(email_lower.endswith(domain) for domain in allowed_domains)
        email_allowed = email_lower in allowed_emails

        if not (domain_allowed or email_allowed):
            flash('Access denied: Unauthorized email domain or email.', 'error')
            return redirect(url_for('login'))

        user = User(user_id, email, name)
        users[user_id] = user
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

PRESENCE_ACCESS_CODE = 'letmein123'

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

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/generate_qr/<course_id>')
def generate_qr(course_id):
    key = request.args.get('key')
    if key != MASTER_KEY:
        abort(403)

    if course_id not in courses:
        return f"Invalid course ID: {course_id}", 404

    public_url = os.getenv('PUBLIC_URL')
    if not public_url:
        return "Error: PUBLIC_URL environment variable not set.", 500

    base_url = public_url.rstrip('/')
    check_in_url = f"{base_url}/checkin?course_id={course_id}"

    img = qrcode.make(check_in_url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/checkin')
@login_required
def checkin():
    course_id = request.args.get('course_id')

    if not course_id or course_id not in courses:
        return "Invalid or missing course ID", 400

    user_id = current_user.id
    now = datetime.now(timezone.utc)
    cooldown_key = (user_id, course_id)
    last_checkin = checkin_cooldowns.get(cooldown_key)

    if last_checkin and now - last_checkin < timedelta(minutes=10):
        remaining = timedelta(minutes=10) - (now - last_checkin)
        return f"You’ve already checked in. Try again in {int(remaining.total_seconds() // 60) + 1} minutes.", 429

    checkin_cooldowns[cooldown_key] = now
    attendance_records[user_id][course_id].append(now)

    return f"✅ Successfully checked in to course {courses[course_id]} at {now.strftime('%H:%M:%S UTC')}!"

@app.route('/test-redirect-uri')
def test_redirect_uri():
    return url_for('google_callback', _external=True)


if __name__ == "__main__":
    from waitress import serve
    port = int(os.environ.get("PORT", 5000))
    serve(app, host="0.0.0.0", port=port)
