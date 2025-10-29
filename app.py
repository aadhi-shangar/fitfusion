import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from datetime import datetime, timedelta
import bcrypt
import os
from recommendation.diet_recommendation import DietRecommendationSystem
from recommendation.workout_recommendation import WorkoutRecommendationSystem
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, BadSignature
from werkzeug.utils import secure_filename
from chatbot.chatbot import process_user_input
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import logging

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
app.permanent_session_lifetime = timedelta(days=7)
app.config['SESSION_COOKIE_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Email configuration
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=os.environ.get('MAIL_USERNAME', 'fitfusion327@gmail.com'),
    MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD')
)
mail = Mail(app)

# Initialize recommendation systems and store in app.config
with app.app_context():
    try:
        app.config['DIET_RECOMMENDER'] = DietRecommendationSystem('static/datasets/diet_dataset.csv')
        app.config['WORKOUT_RECOMMENDER'] = WorkoutRecommendationSystem('static/datasets/workout_dataset.csv')
        logger.info("Recommendation systems initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing recommenders: {e}")
        raise

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    conn = sqlite3.connect('fitfusion.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_user_data_dict(user_data, email):
    """Helper function to create user_data_dict with defaults."""
    user_data_dict = dict(user_data) if user_data else {}
    defaults = {
        'avatar_url': 'https://storage.googleapis.com/a1aa/image/19fc3159-a7a4-40ea-5271-319739d2642a.jpg',
        'phone': '',
        'email': email,
        'dob': '',
        'goal': 'No Program Selected',
        'theme': 'light',
        'language': 'en',
        'notification_frequency': 'daily',
        'units': 'metric',
        'data_sharing': False,
        'auto_sync': False,
        'notifications': True,
        'water_intake': 1.9,
        'water_goal': 3.0,
        'steps_count': 0,
        'steps_goal': 10000,
        'workout_calories': 0,
        'workout_goal': 500,
        'sleep_duration': 0,
        'sleep_goal': 8.0,
        'exercise_hours': 0,
        'mood': 'Neutral'
    }
    for key, value in defaults.items():
        user_data_dict.setdefault(key, value)
    return user_data_dict

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'name' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN name TEXT NOT NULL DEFAULT ""')
    
    # Create user_data table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            gender TEXT NOT NULL,
            age INTEGER NOT NULL,
            weight REAL NOT NULL,
            height REAL NOT NULL,
            water_intake REAL DEFAULT 1.9,
            water_goal REAL DEFAULT 3.0,
            steps_count INTEGER DEFAULT 0,
            steps_goal INTEGER DEFAULT 10000,
            workout_calories REAL DEFAULT 0,
            workout_goal REAL DEFAULT 500,
            sleep_duration REAL DEFAULT 0,
            sleep_goal REAL DEFAULT 8.0,
            exercise_hours REAL DEFAULT 0,
            mood TEXT DEFAULT 'Neutral',
            avatar_url TEXT,
            phone TEXT,
            email TEXT,
            dob TEXT,
            goal TEXT,
            theme TEXT DEFAULT 'light',
            language TEXT DEFAULT 'en',
            notification_frequency TEXT DEFAULT 'daily',
            units TEXT DEFAULT 'metric',
            data_sharing BOOLEAN DEFAULT FALSE,
            auto_sync BOOLEAN DEFAULT FALSE,
            notifications BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Check and add missing columns to user_data
    cursor.execute("PRAGMA table_info(user_data)")
    columns = {col[1]: col for col in cursor.fetchall()}
    required_columns = {
        'water_intake': 'REAL DEFAULT 1.9',
        'water_goal': 'REAL DEFAULT 3.0',
        'steps_count': 'INTEGER DEFAULT 0',
        'steps_goal': 'INTEGER DEFAULT 10000',
        'workout_calories': 'REAL DEFAULT 0',
        'workout_goal': 'REAL DEFAULT 500',
        'sleep_duration': 'REAL DEFAULT 0',
        'sleep_goal': 'REAL DEFAULT 8.0',
        'exercise_hours': 'REAL DEFAULT 0',
        'mood': 'TEXT DEFAULT "Neutral"',
        'avatar_url': 'TEXT',
        'phone': 'TEXT',
        'email': 'TEXT',
        'dob': 'TEXT',
        'goal': 'TEXT',
        'theme': 'TEXT DEFAULT "light"',
        'language': 'TEXT DEFAULT "en"',
        'notification_frequency': 'TEXT DEFAULT "daily"',
        'units': 'TEXT DEFAULT "metric"',
        'data_sharing': 'BOOLEAN DEFAULT FALSE',
        'auto_sync': 'BOOLEAN DEFAULT FALSE',
        'notifications': 'BOOLEAN DEFAULT TRUE'
    }
    for col, col_type in required_columns.items():
        if col not in columns:
            cursor.execute(f'ALTER TABLE user_data ADD COLUMN {col} {col_type}')
    
    # Handle column renaming or dropping
    if 'water_max' in columns and 'water_goal' not in columns:
        cursor.execute('ALTER TABLE user_data RENAME COLUMN water_max TO water_goal')
    if 'workout_duration' in columns:
        cursor.execute('ALTER TABLE user_data DROP COLUMN workout_duration')
    
    # Create other tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tracking_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            value TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task TEXT NOT NULL,
            completed BOOLEAN DEFAULT FALSE,
            date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Create uploads directory
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    conn.commit()
    conn.close()

def clear_old_todos():
    with app.app_context():
        conn = get_db_connection()
        today = datetime.now().strftime('%Y-%m-%d')
        conn.execute('DELETE FROM todos WHERE date < ?', (today,))
        conn.commit()
        conn.close()

scheduler = BackgroundScheduler()
scheduler.add_job(func=clear_old_todos, trigger='interval', days=1)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# Initialize database
with app.app_context():
    init_db()

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password').encode('utf-8')
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if user and bcrypt.checkpw(password, user['password_hash']):
            session.permanent = True
            session['user_id'] = user['id']
            session['email'] = user['email']
            session['name'] = user['name'] if 'name' in user else ''
            conn.execute('UPDATE users SET last_login = ? WHERE id = ?', (datetime.now(), user['id']))
            conn.commit()
            user_data = conn.execute('SELECT * FROM user_data WHERE user_id = ?', (user['id'],)).fetchone()
            conn.close()
            logger.info(f"User {email} logged in successfully")
            if user_data:
                return redirect(url_for('home'))
            else:
                return redirect(url_for('user_data'))
        else:
            conn.close()
            flash('Invalid email or password', 'error')
            logger.warning(f"Failed login attempt for email: {email}")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password').encode('utf-8')
        confirm_password = request.form.get('confirmPassword').encode('utf-8')
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            logger.warning(f"Registration failed: Passwords do not match for email {email}")
            return render_template('register.html')
        if len(password) < 8:
            flash('Password must be at least 8 characters long', 'error')
            logger.warning(f"Registration failed: Password too short for email {email}")
            return render_template('register.html')
        conn = get_db_connection()
        existing_user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if existing_user:
            conn.close()
            flash('Email already exists', 'error')
            logger.warning(f"Registration failed: Email {email} already exists")
            return render_template('register.html')
        password_hash = bcrypt.hashpw(password, bcrypt.gensalt())
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)', ('', email, password_hash))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        session.permanent = True
        session['user_id'] = user_id
        session['email'] = email
        session['name'] = ''
        logger.info(f"User {email} registered successfully")
        return redirect(url_for('user_data'))
    return render_template('register.html')

@app.route('/user_data', methods=['GET', 'POST'])
def user_data():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    existing_data = conn.execute('SELECT * FROM user_data WHERE user_id = ?', (session['user_id'],)).fetchone()
    if existing_data:
        conn.close()
        return redirect(url_for('home'))
    if request.method == 'POST':
        name = request.form.get('name-input')
        gender = request.form.get('gender-select')
        age = request.form.get('age-input')
        weight = request.form.get('weight')
        height = request.form.get('height')
        goal = request.form.get('goal')
        if not name:
            flash('Name is required', 'error')
            logger.warning(f"User data submission failed: Name missing")
        elif len(name) > 100:
            flash('Name must be 100 characters or less', 'error')
            logger.warning(f"User data submission failed: Name too long")
        elif not gender:
            flash('Please select a gender', 'error')
            logger.warning(f"User data submission failed: Gender missing")
        else:
            try:
                age = int(age)
                weight = float(weight)
                height = float(height)
                if age < 1 or age > 120:
                    flash('Age must be between 1 and 120', 'error')
                    logger.warning(f"User data submission failed: Invalid age {age}")
                elif weight < 0.1 or weight > 500:
                    flash('Weight must be between 0.1 and 500 kg', 'error')
                    logger.warning(f"User data submission failed: Invalid weight {weight}")
                elif height < 0.1 or height > 300:
                    flash('Height must be between 0.1 and 300 cm', 'error')
                    logger.warning(f"User data submission failed: Invalid height {height}")
                else:
                    conn.execute('UPDATE users SET name = ? WHERE id = ?', (name, session['user_id']))
                    conn.execute('''
                        INSERT INTO user_data (user_id, gender, age, weight, height, goal)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (session['user_id'], gender, age, weight, height, goal))
                    conn.commit()
                    session['name'] = name
                    conn.close()
                    logger.info(f"User {session['email']} submitted user data successfully")
                    return redirect(url_for('welcome'))
            except ValueError:
                flash('Invalid input for age, weight, or height', 'error')
                logger.warning(f"User data submission failed: Invalid input format")
    conn.close()
    return render_template('userData.html')

@app.route('/welcome')
def welcome():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('welcome.html')

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    user_data = conn.execute('SELECT * FROM user_data WHERE user_id = ?', (session['user_id'],)).fetchone()
    conn.close()
    if not user_data:
        return redirect(url_for('user_data'))
    user_data_dict = get_user_data_dict(user_data, session['email'])
    return render_template('profile.html', name=user['name'], user_data=user_data_dict)

@app.route('/update_avatar', methods=['POST'])
def update_avatar():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if 'avatar' not in request.files:
        flash('No file selected', 'error')
        logger.warning(f"Avatar update failed: No file selected")
        return redirect(url_for('profile'))
    file = request.files['avatar']
    if file.filename == '':
        flash('No file selected', 'error')
        logger.warning(f"Avatar update failed: Empty filename")
        return redirect(url_for('profile'))
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{session['user_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        avatar_url = url_for('static', filename=f'uploads/{unique_filename}')
        conn = get_db_connection()
        conn.execute('UPDATE user_data SET avatar_url = ? WHERE user_id = ?', (avatar_url, session['user_id']))
        conn.commit()
        conn.close()
        flash('Avatar updated successfully', 'success')
        logger.info(f"Avatar updated for user {session['email']}")
        return redirect(url_for('profile'))
    else:
        flash('Invalid file format. Allowed: png, jpg, jpeg, gif', 'error')
        logger.warning(f"Avatar update failed: Invalid file format")
        return redirect(url_for('profile'))

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    name = request.form.get('name')
    height = request.form.get('height')
    weight = request.form.get('weight')
    age = request.form.get('age')
    phone = request.form.get('phone')
    email = request.form.get('email')
    dob = request.form.get('dob')
    
    if not name:
        flash('Name is required', 'error')
        logger.warning(f"Profile update failed: Name missing")
        return redirect(url_for('profile'))
    if len(name) > 100:
        flash('Name must be 100 characters or less', 'error')
        logger.warning(f"Profile update failed: Name too long")
        return redirect(url_for('profile'))
    
    try:
        height = float(height) if height else None
        weight = float(weight) if weight else None
        age = int(age) if age else None
        if height and (height < 0.1 or height > 300):
            flash('Height must be between 0.1 and 300 cm', 'error')
            logger.warning(f"Profile update failed: Invalid height {height}")
            return redirect(url_for('profile'))
        if weight and (weight < 0.1 or weight > 500):
            flash('Weight must be between 0.1 and 500 kg', 'error')
            logger.warning(f"Profile update failed: Invalid weight {weight}")
            return redirect(url_for('profile'))
        if age and (age < 1 or age > 120):
            flash('Age must be between 1 and 120', 'error')
            logger.warning(f"Profile update failed: Invalid age {age}")
            return redirect(url_for('profile'))
    except ValueError:
        flash('Invalid input for height, weight, or age', 'error')
        logger.warning(f"Profile update failed: Invalid input format")
        return redirect(url_for('profile'))
    
    conn = get_db_connection()
    conn.execute('UPDATE users SET name = ? WHERE id = ?', (name, session['user_id']))
    update_fields = []
    update_values = []
    if height is not None:
        update_fields.append('height = ?')
        update_values.append(height)
    if weight is not None:
        update_fields.append('weight = ?')
        update_values.append(weight)
    if age is not None:
        update_fields.append('age = ?')
        update_values.append(age)
    update_fields.append('phone = ?')
    update_values.append(phone or '')
    update_fields.append('email = ?')
    update_values.append(email or session['email'])
    update_fields.append('dob = ?')
    update_values.append(dob or '')
    
    if update_fields:
        query = f'UPDATE user_data SET {", ".join(update_fields)} WHERE user_id = ?'
        update_values.append(session['user_id'])
        conn.execute(query, update_values)
    
    conn.commit()
    conn.close()
    session['name'] = name
    flash('Profile updated successfully', 'success')
    logger.info(f"Profile updated for user {session['email']}")
    return redirect(url_for('profile'))

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    theme = request.form.get('theme')
    language = request.form.get('language')
    notification_frequency = request.form.get('notification_frequency')
    units = request.form.get('units')
    data_sharing = 'data_sharing' in request.form
    auto_sync = 'auto_sync' in request.form
    notifications = 'notifications' in request.form
    
    if not theme or theme not in ['light', 'dark']:
        flash('Invalid theme selected', 'error')
        logger.warning(f"Settings update failed: Invalid theme {theme}")
        return redirect(url_for('profile'))
    if not language or language not in ['en', 'es', 'fr']:
        flash('Invalid language selected', 'error')
        logger.warning(f"Settings update failed: Invalid language {language}")
        return redirect(url_for('profile'))
    if not notification_frequency or notification_frequency not in ['daily', 'weekly', 'none']:
        flash('Invalid notification frequency selected', 'error')
        logger.warning(f"Settings update failed: Invalid notification frequency {notification_frequency}")
        return redirect(url_for('profile'))
    if not units or units not in ['metric', 'imperial']:
        flash('Invalid units selected', 'error')
        logger.warning(f"Settings update failed: Invalid units {units}")
        return redirect(url_for('profile'))
    
    conn = get_db_connection()
    conn.execute('''
        UPDATE user_data SET
            theme = ?,
            language = ?,
            notification_frequency = ?,
            units = ?,
            data_sharing = ?,
            auto_sync = ?,
            notifications = ?
        WHERE user_id = ?
    ''', (theme, language, notification_frequency, units, data_sharing, auto_sync, notifications, session['user_id']))
    conn.commit()
    conn.close()
    flash('Settings updated successfully', 'success')
    logger.info(f"Settings updated for user {session['email']}")
    return redirect(url_for('profile'))

@app.route('/progress')
def progress():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    user_data = conn.execute('SELECT * FROM user_data WHERE user_id = ?', (session['user_id'],)).fetchone()
    history = {}
    metrics = ['weight', 'water', 'steps', 'workout', 'sleep', 'mood']
    for metric in metrics:
        rows = conn.execute(
            'SELECT value, timestamp FROM tracking_history WHERE user_id = ? AND type = ? ORDER BY timestamp DESC LIMIT 7',
            (session['user_id'], metric)
        ).fetchall()
        history[metric] = [{'value': row['value'], 'date': row['timestamp']} for row in rows]
    conn.close()
    if not user_data:
        return redirect(url_for('user_data'))
    user_data_dict = get_user_data_dict(user_data, session['email'])
    return render_template('progress.html', user=user, user_data=user_data_dict, history=history, name=user['name'])

@app.route('/api/update_progress', methods=['POST'])
def update_progress():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    action = data.get('action')
    user_id = session['user_id']
    conn = get_db_connection()
    tracking = conn.execute('SELECT water_intake, water_goal, steps_count, steps_goal, mood FROM user_data WHERE user_id = ?', (user_id,)).fetchone()
    water_intake = float(tracking['water_intake']) if tracking else 1.9
    water_goal = float(tracking['water_goal']) if tracking else 3.0
    steps_count = tracking['steps_count'] if tracking else 0
    steps_goal = tracking['steps_goal'] if tracking else 10000
    mood = tracking['mood'] if tracking else 'Neutral'
    timestamp = data.get('timestamp', datetime.now().isoformat())
    try:
        timestamp_dt = datetime.fromisoformat(timestamp)
    except ValueError:
        logger.warning(f"Progress update failed: Invalid timestamp {timestamp}")
        return jsonify({'error': 'Invalid timestamp format'}), 400
    if action == 'set_water_intake':
        water_intake = float(data.get('value', water_intake))
        if water_intake < 0 or water_intake > water_goal:
            logger.warning(f"Progress update failed: Invalid water intake {water_intake}")
            return jsonify({'error': f'Water intake must be between 0 and {water_goal} liters'}), 400
        conn.execute('INSERT INTO tracking_history (user_id, type, value, timestamp) VALUES (?, ?, ?, ?)', 
                     (user_id, 'water', water_intake, timestamp))
        conn.execute('UPDATE user_data SET water_intake = ? WHERE user_id = ?', (water_intake, user_id))
    elif action == 'set_steps_goal':
        steps_goal = int(data.get('value', steps_goal))
        steps_goal = max(min(steps_goal, 100000), 1000)
        conn.execute('UPDATE user_data SET steps_goal = ? WHERE user_id = ?', (steps_goal, user_id))
    elif action == 'set_mood':
        mood = data.get('value', mood)
        if mood not in ['Happy', 'Neutral', 'Sad']:
            logger.warning(f"Progress update failed: Invalid mood {mood}")
            return jsonify({'error': 'Invalid mood value'}), 400
        conn.execute('INSERT INTO tracking_history (user_id, type, value, timestamp) VALUES (?, ?, ?, ?)', 
                     (user_id, 'mood', mood, timestamp))
        conn.execute('UPDATE user_data SET mood = ? WHERE user_id = ?', (mood, user_id))
    else:
        logger.warning(f"Progress update failed: Invalid action {action}")
        return jsonify({'error': 'Invalid action'}), 400
    conn.commit()
    conn.close()
    logger.info(f"Progress updated for user {session['email']}: action={action}")
    return jsonify({
        'intake': water_intake,
        'goal': water_goal,
        'steps_count': steps_count,
        'steps_goal': steps_goal,
        'mood': mood,
        'last_updated': timestamp
    })

@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    user_data = conn.execute('SELECT * FROM user_data WHERE user_id = ?', (session['user_id'],)).fetchone()
    today = datetime.now().strftime('%Y-%m-%d')
    todos = conn.execute('SELECT * FROM todos WHERE user_id = ? AND date = ?', 
                        (session['user_id'], today)).fetchall()
    notifications = conn.execute('SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC', 
                               (session['user_id'],)).fetchall()
    conn.close()
    if not user_data:
        return redirect(url_for('user_data'))
    user_data_dict = get_user_data_dict(user_data, session['email'])
    bmi = round(user_data_dict['weight'] / ((user_data_dict['height'] / 100) ** 2), 1)
    bmi_status = 'Underweight' if bmi < 18.5 else 'Normal' if bmi < 25 else 'Overweight' if bmi < 30 else 'Obese'
    return render_template('home.html', user=user, user_data=user_data_dict, bmi=bmi, bmi_status=bmi_status, 
                          todos=todos, notifications=notifications)

@app.route('/weight')
def weight():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    user_row = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    user_data = conn.execute('SELECT * FROM user_data WHERE user_id = ?', (session['user_id'],)).fetchone()
    conn.close()
    if not user_data:
        return redirect(url_for('user_data'))
    user = dict(user_row) if user_row else {'id': session['user_id'], 'name': session['name'], 'email': session['email']}
    user_data_dict = get_user_data_dict(user_data, session['email'])
    return render_template('weight.html', user=user, user_data=user_data_dict)

@app.route('/workout')
def workout():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    user_data = conn.execute('SELECT * FROM user_data WHERE user_id = ?', (session['user_id'],)).fetchone()
    conn.close()
    if not user_data:
        return redirect(url_for('user_data'))
    user_data_dict = get_user_data_dict(user_data, session['email'])
    return render_template('workout.html', user=user, user_data=user_data_dict, recommendation=None, email=session['email'], name=session['name'])

@app.route('/steps')
def steps():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    user_data = conn.execute('SELECT * FROM user_data WHERE user_id = ?', (session['user_id'],)).fetchone()
    conn.close()
    if not user_data:
        return redirect(url_for('user_data'))
    user_data_dict = get_user_data_dict(user_data, session['email'])
    return render_template('steps.html', user=user, user_data=user_data_dict)

@app.route('/sleep')
def sleep():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    user_data = conn.execute('SELECT * FROM user_data WHERE user_id = ?', (session['user_id'],)).fetchone()
    conn.close()
    if not user_data:
        return redirect(url_for('user_data'))
    user_data_dict = get_user_data_dict(user_data, session['email'])
    return render_template('sleep.html', user=user, user_data=user_data_dict)

@app.route('/water')
def water():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    user_data = conn.execute('SELECT * FROM user_data WHERE user_id = ?', (session['user_id'],)).fetchone()
    conn.close()
    if not user_data:
        return redirect(url_for('user_data'))
    user_data_dict = get_user_data_dict(user_data, session['email'])
    return render_template('water.html', user=user, user_data=user_data_dict)

@app.route('/chatbot')
def chatbot():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('chatbot.html')

@app.route('/api/chatbot', methods=['POST'])
def api_chatbot():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    user_input = data.get('message', '').strip()
    if not user_input:
        logger.warning(f"Chatbot request failed: Empty message")
        return jsonify({'response': 'Please enter a message.'}), 400
    try:
        conn = get_db_connection()
        user_data = conn.execute('SELECT age, gender, goal FROM user_data WHERE user_id = ?', (session['user_id'],)).fetchone()
        conn.close()
        user_data_dict = dict(user_data) if user_data else {}
        recommendation_data = session.get('last_recommendation')
        response = process_user_input(user_input, user_data=user_data_dict, recommendation_data=recommendation_data)
        logger.info(f"Chatbot response generated for user {session['email']}: {response}")
        return jsonify({'response': response})
    except Exception as e:
        logger.error(f"Chatbot API error for input '{user_input}': {str(e)}")
        return jsonify({'response': 'Sorry, I encountered an error. Try asking something else!'}), 500

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if 'user_id' in session:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email = request.form.get('email')
        if not email:
            flash('Please enter your email', 'error')
            logger.warning(f"Password reset failed: Email missing")
            return render_template('forgot_password.html')
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if user:
            s = URLSafeTimedSerializer(app.secret_key)
            token = s.dumps(email, salt='password-reset-salt')
            msg = Message('Password Reset Request', recipients=[email])
            msg.body = f'Click this link to reset your password: {url_for("reset_password", token=token, _external=True)}'
            try:
                mail.send(msg)
                flash(f'A password reset link has been sent to {email}', 'success')
                logger.info(f"Password reset email sent to {email}")
            except Exception as e:
                flash(f'Failed to send email: {str(e)}', 'error')
                logger.error(f"Failed to send password reset email to {email}: {str(e)}")
        else:
            flash('Email not found', 'error')
            logger.warning(f"Password reset failed: Email {email} not found")
        conn.close()
    return render_template('forgot_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password():
    if 'user_id' in session:
        return redirect(url_for('home'))
    s = URLSafeTimedSerializer(app.secret_key)
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except BadSignature:
        flash('Invalid or expired token', 'error')
        logger.warning(f"Password reset failed: Invalid or expired token")
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        new_password = request.form.get('new_password').encode('utf-8')
        confirm_password = request.form.get('confirm_password').encode('utf-8')
        if new_password != confirm_password:
            flash('Passwords do not match', 'error')
            logger.warning(f"Password reset failed: Passwords do not match for email {email}")
            return render_template('reset_password.html', token=token)
        if len(new_password) < 8:
            flash('Password must be at least 8 characters long', 'error')
            logger.warning(f"Password reset failed: Password too short for email {email}")
            return render_template('reset_password.html', token=token)
        conn = get_db_connection()
        password_hash = bcrypt.hashpw(new_password, bcrypt.gensalt())
        conn.execute('UPDATE users SET password_hash = ? WHERE email = ?', (password_hash, email))
        conn.commit()
        conn.close()
        flash('Password has been reset. Please log in.', 'success')
        logger.info(f"Password reset successfully for email {email}")
        return redirect(url_for('login'))
    return render_template('reset_password.html', token=token)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('email', None)
    session.pop('name', None)
    session.pop('diet_recommendation', None)
    session.pop('workout_recommendation', None)
    session.pop('diet_error', None)
    session.pop('workout_error', None)
    flash('You have been logged out.', 'success')
    logger.info(f"User logged out: {session.get('email')}")
    return redirect(url_for('login'))

@app.route('/recommendations', methods=['GET'])
def recommendations():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    user_data = conn.execute('SELECT * FROM user_data WHERE user_id = ?', (session['user_id'],)).fetchone()
    conn.close()
    if not user_data:
        return redirect(url_for('user_data'))
    user_data_dict = get_user_data_dict(user_data, session['email'])
    return render_template(
        'recommendations.html',
        user=user,
        user_data=user_data_dict,
        diet_recommendation=session.get('diet_recommendation'),
        workout_recommendation=session.get('workout_recommendation'),
        diet_error=session.get('diet_error'),
        workout_error=session.get('workout_error'),
        email=session['email'],
        name=session['name'],
        chatbot_diet_tips=session.get('chatbot_diet_tips'),
        chatbot_workout_tips=session.get('chatbot_workout_tips')
    )

@app.route('/recommend_diet', methods=['POST'])
def recommend_diet():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    user_data = conn.execute('SELECT * FROM user_data WHERE user_id = ?', (session['user_id'],)).fetchone()
    conn.close()
    if not user_data:
        return redirect(url_for('user_data'))
    user_data_dict = get_user_data_dict(user_data, session['email'])
    try:
        age = int(request.form.get('age', user_data_dict['age']))
        if age < 1 or age > 120:
            raise ValueError("Age must be between 1 and 120")
        gender = request.form.get('gender', user_data_dict['gender'])
        if gender not in ['Male', 'Female']:
            raise ValueError("Invalid gender")
        goal = request.form.get('goal')
        if goal not in ['Lose Weight', 'Gain Muscle', 'Maintain Weight']:
            raise ValueError("Invalid goal")
        diet_type = request.form.get('diet_type')
        if diet_type not in ['Vegan', 'Vegetarian', 'Non-Vegetarian', 'Eggetarian']:
            raise ValueError("Invalid diet type")
        activity_level = request.form.get('activity_level')
        if activity_level not in ['Sedentary', 'Lightly Active', 'Moderately Active', 'Very Active', 'Super Active']:
            raise ValueError("Invalid activity level")
        user_input = {
            'Age': age,
            'Gender': gender,
            'Goal': goal,
            'Diet_Type': diet_type,
            'Allergies': request.form.get('allergies', 'None'),
            'Medical_Conditions': request.form.get('medical_conditions', 'None'),
            'Activity_Level': activity_level
        }
        logger.info(f"Diet recommendation input: {user_input}")
        diet_recommendation = app.config['DIET_RECOMMENDER'].recommend_diet(user_input)
        if diet_recommendation and all(key in diet_recommendation for key in ['Breakfast', 'Mid-Morning', 'Lunch', 'Evening Snack', 'Dinner', 'Post-Dinner', 'Total Calories']):
            session['diet_recommendation'] = diet_recommendation
            session['diet_error'] = None
            session['last_recommendation'] = {
                'type': 'diet',
                'user_input': user_input,
                'recommendation': diet_recommendation
            }
            # Create a string representation of the meal plan for the chatbot
            meal_plan_str = (
                f"Breakfast: {diet_recommendation['Breakfast']['Meal']} ({diet_recommendation['Breakfast']['Calories']} cal), "
                f"Mid-Morning: {diet_recommendation['Mid-Morning']['Meal']} ({diet_recommendation['Mid-Morning']['Calories']} cal), "
                f"Lunch: {diet_recommendation['Lunch']['Meal']} ({diet_recommendation['Lunch']['Calories']} cal), "
                f"Evening Snack: {diet_recommendation['Evening Snack']['Meal']} ({diet_recommendation['Evening Snack']['Calories']} cal), "
                f"Dinner: {diet_recommendation['Dinner']['Meal']} ({diet_recommendation['Dinner']['Calories']} cal), "
                f"Post-Dinner: {diet_recommendation['Post-Dinner']['Meal']} ({diet_recommendation['Post-Dinner']['Calories']} cal), "
                f"Total Calories: {diet_recommendation['Total Calories']} cal"
            )
            chatbot_prompt = f"Provide tips for a {diet_type} diet plan: {meal_plan_str}"
            chatbot_response = process_user_input(
                chatbot_prompt,
                user_data=user_input,
                recommendation_data=session['last_recommendation']
            )
            session['chatbot_diet_tips'] = chatbot_response
            logger.info(f"Returning diet recommendation: {diet_recommendation}")
        else:
            session['diet_error'] = 'No suitable diet plan found or invalid recommendation format.'
            session['diet_recommendation'] = None
            session['chatbot_diet_tips'] = None
            logger.warning(f"Diet recommendation failed: Invalid or no recommendation")
    except ValueError as e:
        session['diet_error'] = str(e)
        session['diet_recommendation'] = None
        session['chatbot_diet_tips'] = None
        logger.warning(f"Diet recommendation failed: {str(e)}")
    except Exception as e:
        session['diet_error'] = 'An unexpected error occurred while generating the diet recommendation.'
        session['diet_recommendation'] = None
        session['chatbot_diet_tips'] = None
        logger.error(f"Diet recommendation error: {str(e)}")
    return redirect(url_for('recommendations'))

@app.route('/recommend_workout', methods=['POST'])
def recommend_workout():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    user_data = conn.execute('SELECT * FROM user_data WHERE user_id = ?', (session['user_id'],)).fetchone()
    conn.close()
    if not user_data:
        return redirect(url_for('user_data'))
    user_data_dict = get_user_data_dict(user_data, session['email'])
    try:
        age = int(request.form.get('age', user_data_dict['age']))
        if age < 1 or age > 120:
            raise ValueError("Age must be between 1 and 120")
        gender = request.form.get('gender', user_data_dict['gender'])
        if gender not in ['Male', 'Female']:
            raise ValueError("Invalid gender")
        fitness_level = request.form.get('fitness_level')
        if fitness_level not in ['Beginner', 'Intermediate', 'Advanced']:
            raise ValueError("Invalid fitness level")
        goal = request.form.get('goal')
        if goal not in ['Strength', 'Endurance', 'Flexibility', 'Weight Loss']:
            raise ValueError("Invalid goal")
        preference = request.form.get('preference')
        if preference not in ['Home', 'Gym', 'Outdoor']:
            raise ValueError("Invalid workout preference")
        time = int(request.form.get('time', 60))
        if time < 10 or time > 240:
            raise ValueError("Workout time must be between 10 and 240 minutes")
        user_input = {
            'Age': age,
            'Gender': gender,
            'Fitness_Level': fitness_level,
            'Goal': goal,
            'Workout_Preference': preference,
            'Workout_Time_per_day_mins': time
        }
        logger.info(f"Workout recommendation input: {user_input}")
        workout_recommendation = app.config['WORKOUT_RECOMMENDER'].recommend_workout(user_input)
        if workout_recommendation and all(key in workout_recommendation for key in ['Workout_Type', 'Exercises', 'Duration']):
            session['workout_recommendation'] = workout_recommendation
            session['workout_error'] = None
            session['last_recommendation'] = {
                'type': 'workout',
                'user_input': user_input,
                'recommendation': workout_recommendation
            }
            chatbot_prompt = (
                f"Provide tips for a {fitness_level} {preference} workout plan: "
                f"{workout_recommendation['Workout_Type']} with exercises "
                f"{', '.join(workout_recommendation['Exercises'])} for {workout_recommendation['Duration']} minutes"
            )
            chatbot_response = process_user_input(
                chatbot_prompt,
                user_data=user_input,
                recommendation_data=session['last_recommendation']
            )
            session['chatbot_workout_tips'] = chatbot_response
            logger.info(f"Returning workout recommendation: {workout_recommendation}")
        else:
            session['workout_error'] = 'No suitable workout plan found or invalid recommendation format.'
            session['workout_recommendation'] = None
            session['chatbot_workout_tips'] = None
            logger.warning(f"Workout recommendation failed: Invalid or no recommendation")
    except ValueError as e:
        session['workout_error'] = str(e)
        session['workout_recommendation'] = None
        session['chatbot_workout_tips'] = None
        logger.warning(f"Workout recommendation failed: {str(e)}")
    except Exception as e:
        session['workout_error'] = 'An unexpected error occurred while generating the workout recommendation.'
        session['workout_recommendation'] = None
        session['chatbot_workout_tips'] = None
        logger.error(f"Workout recommendation error: {str(e)}")
    return redirect(url_for('recommendations'))

@app.route('/api/recommend_workout', methods=['POST'])
def api_recommend_workout():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    try:
        fitness_level = data.get('fitness_level', 'Intermediate')
        if fitness_level not in ['Beginner', 'Intermediate', 'Advanced']:
            raise ValueError("Invalid fitness level")
        goal = data.get('goal', 'Strength')
        if goal not in ['Strength', 'Endurance', 'Flexibility', 'Weight Loss']:
            raise ValueError("Invalid goal")
        preference = data.get('preference', 'Home')
        if preference not in ['Home', 'Gym', 'Outdoor']:
            raise ValueError("Invalid workout preference")
        time = int(data.get('time', 60))
        if time < 10 or time > 240:
            raise ValueError("Workout time must be between 10 and 240 minutes")
        user_input = {
            'Age': data.get('age', 30),  # Default age if not provided
            'Gender': data.get('gender', 'Male'),  # Default gender if not provided
            'Fitness_Level': fitness_level,
            'Goal': goal,
            'Workout_Preference': preference,
            'Workout_Time_per_day_mins': time
        }
        logger.info(f"API workout recommendation input: {user_input}")
        recommendation = app.config['WORKOUT_RECOMMENDER'].recommend_workout(user_input)
        if recommendation and all(key in recommendation for key in ['Workout_Type', 'Exercises', 'Duration']):
            logger.info(f"API returning workout recommendation: {recommendation}")
            return jsonify({
                'workout_type': recommendation['Workout_Type'],
                'exercises': recommendation['Exercises'],
                'duration': recommendation['Duration']
            })
        else:
            logger.warning(f"API workout recommendation failed: Invalid or no recommendation")
            return jsonify({'error': 'No suitable workout plan found or invalid recommendation format.'}), 400
    except ValueError as e:
        logger.warning(f"API workout recommendation failed: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"API workout recommendation error: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred.'}), 500

@app.route('/api/update_water', methods=['POST'])
def update_water():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    action = data.get('action')
    user_id = session['user_id']
    conn = get_db_connection()
    tracking = conn.execute('SELECT water_intake, water_goal FROM user_data WHERE user_id = ?', (user_id,)).fetchone()
    water_intake = float(tracking['water_intake']) if tracking else 1.9
    water_goal = float(tracking['water_goal']) if tracking else 3.0
    timestamp = data.get('timestamp', datetime.now().isoformat())
    try:
        timestamp_dt = datetime.fromisoformat(timestamp)
    except ValueError:
        logger.warning(f"Water update failed: Invalid timestamp {timestamp}")
        return jsonify({'error': 'Invalid timestamp format'}), 400
    
    # Round water_intake to 1 decimal place to avoid floating-point errors
    water_intake = round(water_intake, 1)
    
    if action == 'set':
        water_intake = float(data.get('value', water_intake))
        if water_intake < 0 or water_intake > water_goal:
            logger.warning(f"Water update failed: Invalid intake {water_intake}")
            return jsonify({'error': 'Water intake must be between 0 and goal liters'}), 400
        water_intake = round(water_intake, 1)  # Round after setting
        conn.execute('INSERT INTO tracking_history (user_id, type, value, timestamp) VALUES (?, ?, ?, ?)', 
                     (user_id, 'water', water_intake, timestamp))
    elif action == 'increase':
        water_intake = min(water_intake + 0.1, water_goal)
        water_intake = round(water_intake, 1)  # Round after increasing
        conn.execute('INSERT INTO tracking_history (user_id, type, value, timestamp) VALUES (?, ?, ?, ?)', 
                     (user_id, 'water', water_intake, timestamp))
    elif action == 'decrease':
        water_intake = max(water_intake - 0.1, 0)
        water_intake = round(water_intake, 1)  # Round after decreasing
        conn.execute('INSERT INTO tracking_history (user_id, type, value, timestamp) VALUES (?, ?, ?, ?)', 
                     (user_id, 'water', water_intake, timestamp))
    elif action == 'set_max':
        water_goal = float(data.get('max', water_goal))
        water_goal = max(min(water_goal, 10), 0.5)
        water_intake = min(water_intake, water_goal)
        water_intake = round(water_intake, 1)  # Round after adjustment
    
    conn.execute('UPDATE user_data SET water_intake = ?, water_goal = ? WHERE user_id = ?', 
                 (water_intake, water_goal, user_id))
    conn.commit()
    conn.close()
    logger.info(f"Water updated for user {session['email']}: action={action}, intake={water_intake}, goal={water_goal}")
    return jsonify({'intake': water_intake, 'max': water_goal, 'last_updated': timestamp})

@app.route('/api/update_weight', methods=['POST'])
def update_weight():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    action = data.get('action', 'set')
    user_id = session['user_id']
    conn = get_db_connection()
    tracking = conn.execute('SELECT weight FROM user_data WHERE user_id = ?', (user_id,)).fetchone()
    weight = tracking['weight'] if tracking else 0
    timestamp = data.get('timestamp', datetime.now().isoformat())
    try:
        timestamp_dt = datetime.fromisoformat(timestamp)
    except ValueError:
        logger.warning(f"Weight update failed: Invalid timestamp {timestamp}")
        return jsonify({'error': 'Invalid timestamp format'}), 400
    if action == 'set':
        weight = float(data.get('value', weight))
        if weight < 0.1 or weight > 500:
            logger.warning(f"Weight update failed: Invalid weight {weight}")
            return jsonify({'error': 'Weight must be between 0.1 and 500 kg'}), 400
        conn.execute('INSERT INTO tracking_history (user_id, type, value, timestamp) VALUES (?, ?, ?, ?)', 
                     (user_id, 'weight', weight, timestamp))
    elif action == 'increase':
        weight = min(weight + 0.1, 500)
        conn.execute('INSERT INTO tracking_history (user_id, type, value, timestamp) VALUES (?, ?, ?, ?)', 
                     (user_id, 'weight', weight, timestamp))
    elif action == 'decrease':
        weight = max(weight - 0.1, 0.1)
        conn.execute('INSERT INTO tracking_history (user_id, type, value, timestamp) VALUES (?, ?, ?, ?)', 
                     (user_id, 'weight', weight, timestamp))
    conn.execute('UPDATE user_data SET weight = ? WHERE user_id = ?', (weight, user_id))
    conn.commit()
    conn.close()
    logger.info(f"Weight updated for user {session['email']}: action={action}, weight={weight}")
    return jsonify({'value': weight, 'last_updated': timestamp})

@app.route('/api/update_workout', methods=['POST'])
def update_workout():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    action = data.get('action', 'set')
    user_id = session['user_id']
    conn = get_db_connection()
    tracking = conn.execute('SELECT workout_calories, workout_goal FROM user_data WHERE user_id = ?', (user_id,)).fetchone()
    calories = tracking['workout_calories'] if tracking else 0
    goal = tracking['workout_goal'] if tracking else 500
    timestamp = data.get('timestamp', datetime.now().isoformat())
    try:
        timestamp_dt = datetime.fromisoformat(timestamp)
    except ValueError:
        logger.warning(f"Workout update failed: Invalid timestamp {timestamp}")
        return jsonify({'error': 'Invalid timestamp format'}), 400
    if action == 'set':
        calories = float(data.get('value', calories))
        if calories < 0 or calories > 2000:
            logger.warning(f"Workout update failed: Invalid calories {calories}")
            return jsonify({'error': 'Calories must be between 0 and 2000'}), 400
        conn.execute('INSERT INTO tracking_history (user_id, type, value, timestamp) VALUES (?, ?, ?, ?)', 
                     (user_id, 'workout', calories, timestamp))
    elif action == 'increase':
        calories = min(calories + 10, 2000)
        conn.execute('INSERT INTO tracking_history (user_id, type, value, timestamp) VALUES (?, ?, ?, ?)', 
                     (user_id, 'workout', calories, timestamp))
    elif action == 'decrease':
        calories = max(calories - 10, 0)
        conn.execute('INSERT INTO tracking_history (user_id, type, value, timestamp) VALUES (?, ?, ?, ?)', 
                     (user_id, 'workout', calories, timestamp))
    elif action == 'set_goal':
        goal = float(data.get('goal', goal))
        goal = max(min(goal, 2000), 100)
    conn.execute('UPDATE user_data SET workout_calories = ?, workout_goal = ? WHERE user_id = ?', 
                 (calories, goal, user_id))
    conn.commit()
    conn.close()
    logger.info(f"Workout updated for user {session['email']}: action={action}, calories={calories}, goal={goal}")
    return jsonify({'calories': calories, 'goal': goal, 'last_updated': timestamp})

@app.route('/api/update_steps', methods=['POST'])
def update_steps():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    action = data.get('action', 'set')
    user_id = session['user_id']
    conn = get_db_connection()
    tracking = conn.execute('SELECT steps_count, steps_goal FROM user_data WHERE user_id = ?', (user_id,)).fetchone()
    count = tracking['steps_count'] if tracking else 0
    goal = tracking['steps_goal'] if tracking else 10000
    timestamp = data.get('timestamp', datetime.now().isoformat())
    try:
        timestamp_dt = datetime.fromisoformat(timestamp)
    except ValueError:
        logger.warning(f"Steps update failed: Invalid timestamp {timestamp}")
        return jsonify({'error': 'Invalid timestamp format'}), 400
    if action == 'set':
        count = int(data.get('value', count))
        if count < 0 or count > 100000:
            logger.warning(f"Steps update failed: Invalid steps {count}")
            return jsonify({'error': 'Steps must be between 0 and 100000'}), 400
        conn.execute('INSERT INTO tracking_history (user_id, type, value, timestamp) VALUES (?, ?, ?, ?)', 
                     (user_id, 'steps', count, timestamp))
    elif action == 'increase':
        count = min(count + 100, 100000)
        conn.execute('INSERT INTO tracking_history (user_id, type, value, timestamp) VALUES (?, ?, ?, ?)', 
                     (user_id, 'steps', count, timestamp))
    elif action == 'decrease':
        count = max(count - 100, 0)
        conn.execute('INSERT INTO tracking_history (user_id, type, value, timestamp) VALUES (?, ?, ?, ?)', 
                     (user_id, 'steps', count, timestamp))
    elif action == 'set_goal':
        goal = int(data.get('goal', goal))
        goal = max(min(goal, 100000), 1000)
    conn.execute('UPDATE user_data SET steps_count = ?, steps_goal = ? WHERE user_id = ?', 
                 (count, goal, user_id))
    conn.commit()
    conn.close()
    logger.info(f"Steps updated for user {session['email']}: action={action}, count={count}, goal={goal}")
    return jsonify({'count': count, 'goal': goal, 'last_updated': timestamp})

@app.route('/api/update_sleep', methods=['POST'])
def update_sleep():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    action = data.get('action')
    user_id = session['user_id']
    conn = get_db_connection()
    tracking = conn.execute('SELECT sleep_duration, sleep_goal FROM user_data WHERE user_id = ?', (user_id,)).fetchone()
    duration = tracking['sleep_duration'] if tracking else 0
    goal = tracking['sleep_goal'] if tracking else 8.0
    timestamp = data.get('timestamp', datetime.now().isoformat())
    try:
        timestamp_dt = datetime.fromisoformat(timestamp)
    except ValueError:
        logger.warning(f"Sleep update failed: Invalid timestamp {timestamp}")
        return jsonify({'error': 'Invalid timestamp format'}), 400
    if action == 'set':
        duration = float(data.get('duration', duration))
        if duration < 0 or duration > 12:
            logger.warning(f"Sleep update failed: Invalid duration {duration}")
            return jsonify({'error': 'Sleep duration must be between 0 and 12 hours'}), 400
        conn.execute('INSERT INTO tracking_history (user_id, type, value, timestamp) VALUES (?, ?, ?, ?)', 
                     (user_id, 'sleep', duration, timestamp))
    elif action == 'increase':
        duration = min(duration + 0.1, 12)
        conn.execute('INSERT INTO tracking_history (user_id, type, value, timestamp) VALUES (?, ?, ?, ?)', 
                     (user_id, 'sleep', duration, timestamp))
    elif action == 'decrease':
        duration = max(duration - 0.1, 0)
        conn.execute('INSERT INTO tracking_history (user_id, type, value, timestamp) VALUES (?, ?, ?, ?)', 
                     (user_id, 'sleep', duration, timestamp))
    elif action == 'set_goal':
        goal = float(data.get('goal', goal))
        goal = max(min(goal, 12), 4)
    conn.execute('UPDATE user_data SET sleep_duration = ?, sleep_goal = ? WHERE user_id = ?', 
                 (duration, goal, user_id))
    conn.commit()
    conn.close()
    logger.info(f"Sleep updated for user {session['email']}: action={action}, duration={duration}, goal={goal}")
    return jsonify({'duration': duration, 'goal': goal, 'last_updated': timestamp})

@app.route('/api/update_exercise', methods=['POST'])
def update_exercise():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    action = data.get('action', 'set')
    user_id = session['user_id']
    conn = get_db_connection()
    tracking = conn.execute('SELECT exercise_hours FROM user_data WHERE user_id = ?', (user_id,)).fetchone()
    exercise_hours = tracking['exercise_hours'] if tracking else 0
    timestamp = data.get('timestamp', datetime.now().isoformat())
    try:
        timestamp_dt = datetime.fromisoformat(timestamp)
    except ValueError:
        logger.warning(f"Exercise update failed: Invalid timestamp {timestamp}")
        return jsonify({'error': 'Invalid timestamp format'}), 400
    if action == 'set':
        exercise_hours = float(data.get('value', exercise_hours))
        if exercise_hours < 0 or exercise_hours > 24:
            logger.warning(f"Exercise update failed: Invalid hours {exercise_hours}")
            return jsonify({'error': 'Exercise hours must be between 0 and 24'}), 400
        conn.execute('INSERT INTO tracking_history (user_id, type, value, timestamp) VALUES (?, ?, ?, ?)', 
                     (user_id, 'exercise', exercise_hours, timestamp))
    elif action == 'increase':
        exercise_hours = min(exercise_hours + 0.1, 24)
        conn.execute('INSERT INTO tracking_history (user_id, type, value, timestamp) VALUES (?, ?, ?, ?)', 
                     (user_id, 'exercise', exercise_hours, timestamp))
    elif action == 'decrease':
        exercise_hours = max(exercise_hours - 0.1, 0)
        conn.execute('INSERT INTO tracking_history (user_id, type, value, timestamp) VALUES (?, ?, ?, ?)', 
                     (user_id, 'exercise', exercise_hours, timestamp))
    conn.execute('UPDATE user_data SET exercise_hours = ? WHERE user_id = ?', (exercise_hours, user_id))
    conn.commit()
    conn.close()
    logger.info(f"Exercise updated for user {session['email']}: action={action}, hours={exercise_hours}")
    return jsonify({'exercise_hours': exercise_hours, 'last_updated': timestamp})

@app.route('/api/todos', methods=['POST', 'PUT', 'DELETE'])
def manage_todos():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    user_id = session['user_id']
    conn = get_db_connection()
    today = datetime.now().strftime('%Y-%m-%d')
    
    if request.method == 'POST':
        data = request.get_json()
        task = data.get('task')
        if not task or len(task) > 200:
            conn.close()
            logger.warning(f"Todo creation failed: Invalid task length")
            return jsonify({'error': 'Task is required and must be 200 characters or less'}), 400
        cursor = conn.cursor()
        cursor.execute('INSERT INTO todos (user_id, task, date) VALUES (?, ?, ?)', 
                      (user_id, task, today))
        todo_id = cursor.lastrowid
        conn.commit()
        conn.close()
        logger.info(f"Todo created for user {session['email']}: {task}")
        return jsonify({'id': todo_id, 'task': task, 'completed': False, 'date': today})
    
    elif request.method == 'PUT':
        data = request.get_json()
        todo_id = data.get('id')
        completed = data.get('completed')
        conn.execute('UPDATE todos SET completed = ? WHERE id = ? AND user_id = ?', 
                    (completed, todo_id, user_id))
        conn.commit()
        conn.close()
        logger.info(f"Todo updated for user {session['email']}: id={todo_id}, completed={completed}")
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        data = request.get_json()
        todo_id = data.get('id')
        conn.execute('DELETE FROM todos WHERE id = ? AND user_id = ?', 
                    (todo_id, user_id))
        conn.commit()
        conn.close()
        logger.info(f"Todo deleted for user {session['email']}: id={todo_id}")
        return jsonify({'success': True})

@app.route('/api/notifications', methods=['DELETE'])
def manage_notifications():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    user_id = session['user_id']
    conn = get_db_connection()
    conn.execute('DELETE FROM notifications WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    logger.info(f"Notifications cleared for user {session['email']}")
    return jsonify({'success': True})

@app.route('/api/get_tracking', methods=['GET'])
def get_tracking():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    user_id = session['user_id']
    conn = get_db_connection()
    tracking = conn.execute('SELECT * FROM user_data WHERE user_id = ?', (user_id,)).fetchone()
    history = {}
    for t in ['weight', 'workout', 'steps', 'sleep', 'water', 'mood', 'exercise']:
        rows = conn.execute('SELECT value, timestamp FROM tracking_history WHERE user_id = ? AND type = ? ORDER BY timestamp DESC LIMIT 7', 
                           (user_id, t)).fetchall()
        history[t] = [{'value': row['value'], 'timestamp': row['timestamp']} for row in rows]
    conn.close()
    tracking_dict = get_user_data_dict(tracking, session['email'])
    return jsonify({
        'water': {
            'intake': float(tracking_dict['water_intake']),
            'goal': float(tracking_dict['water_goal']),
            'last_updated': history['water'][0]['timestamp'] if history['water'] else None,
            'history': history['water']
        },
        'weight': {
            'value': tracking_dict['weight'] if 'weight' in tracking_dict else 0,
            'last_updated': history['weight'][0]['timestamp'] if history['weight'] else None,
            'history': history['weight']
        },
        'workout': {
            'calories': tracking_dict['workout_calories'],
            'goal': tracking_dict['workout_goal'],
            'last_updated': history['workout'][0]['timestamp'] if history['workout'] else None,
            'history': history['workout']
        },
        'steps': {
            'count': tracking_dict['steps_count'],
            'goal': tracking_dict['steps_goal'],
            'last_updated': history['steps'][0]['timestamp'] if history['steps'] else None,
            'history': history['steps']
        },
        'sleep': {
            'duration': tracking_dict['sleep_duration'],
            'goal': tracking_dict['sleep_goal'],
            'last_updated': history['sleep'][0]['timestamp'] if history['sleep'] else None,
            'history': history['sleep']
        },
        'exercise': {
            'hours': tracking_dict['exercise_hours'],
            'last_updated': history['exercise'][0]['timestamp'] if history['exercise'] else None,
            'history': history['exercise']
        },
        'mood': {
            'value': tracking_dict['mood'],
            'last_updated': history['mood'][0]['timestamp'] if history['mood'] else None,
            'history': history['mood']
        }
    })

if __name__ == '__main__':
    app.run(debug=True)
