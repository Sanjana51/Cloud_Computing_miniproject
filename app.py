import os
import ssl
import sqlite3
import boto3
import paho.mqtt.client as mqtt
from flask import Flask, request, jsonify, render_template, redirect, url_for, g
from dotenv import load_dotenv
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

# ✅ Load Environment Variables
load_dotenv()

# ✅ Initialize Flask App
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)
bcrypt = Bcrypt(app)
app.secret_key = os.getenv("SECRET_KEY", "your_secret_key")

# ✅ SQLite3 Database Setup
DATABASE = "users.db"

def get_db():
    """Get a connection to the SQLite database."""
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  # Return results as dictionaries
    return db

@app.teardown_appcontext
def close_connection(exception):
    """Close the SQLite connection after each request."""
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def create_user_table():
    """Create the users table in SQLite if it doesn't exist."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)
        conn.commit()

# ✅ Initialize Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class User(UserMixin):
    """User class for Flask-Login."""
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

@login_manager.user_loader
def load_user(user_id):
    """Load user from SQLite database by ID."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if user:
        return User(user["id"], user["username"], user["password"])
    return None

# ✅ AWS Credentials (Loaded from .env)
AWS_REGION = os.getenv("AWS_REGION")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE")

# ✅ Connect to DynamoDB
if AWS_REGION and AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and DYNAMODB_TABLE:
    try:
        dynamodb = boto3.resource(
            'dynamodb',
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )
        table = dynamodb.Table(DYNAMODB_TABLE)
        print("✅ Connected to DynamoDB")
    except Exception as e:
        print(f"❌ DynamoDB Connection Failed: {e}")

# ✅ MQTT Configuration (Loaded from .env)
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", 8883))

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

try:
    client.tls_set("AmazonRootCA1.pem",
                   certfile="Smart_Home.cert.pem",
                   keyfile="Smart_Home.private.key",
                   tls_version=ssl.PROTOCOL_TLSv1_2)

    def on_connect(client, userdata, flags, rc, properties=None):
        print("✅ MQTT Connected!" if rc == 0 else f"❌ MQTT Connection failed: {rc}")

    client.on_connect = on_connect
    client.connect(MQTT_BROKER, MQTT_PORT)
    client.loop_start()
    print("✅ MQTT Client Started")
except Exception as e:
    print(f"❌ MQTT Connection Failed: {e}")

# ✅ Route: Homepage -> Redirects to login if not authenticated
@app.route('/')
def home():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    return render_template('home.html')

# ✅ Route: Login Page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()

        if user and bcrypt.check_password_hash(user["password"], password):
            login_user(User(user["id"], user["username"], user["password"]))
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid username or password")

    return render_template('login.html')

# ✅ Route: Signup Page
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('signup.html', error="Username already exists")

    return render_template('signup.html')

# ✅ Route: Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ✅ Route: Smart Home Dashboard (Protected)
@app.route('/index')
@login_required
def index():
    return render_template('index.html')

# ✅ Fetch all devices from DynamoDB
@app.route('/devices', methods=['GET'])
@login_required
def get_devices():
    try:
        response = table.scan()
        devices = response.get('Items', [])
        return jsonify({"devices": devices})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Control a device via MQTT
@app.route('/device/<device_id>', methods=['POST'])
@login_required
def control_device(device_id):
    data = request.get_json()
    status = data.get('status')

    if not status:
        return jsonify({"error": "Missing 'status' parameter"}), 400

    try:
        topic = f"home/device/{device_id}"
        client.publish(topic, status)
        return jsonify({"message": f"Device {device_id} turned {status}", "topic": topic})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Save user preferences to DynamoDB
@app.route('/preferences', methods=['POST'])
@login_required
def save_preferences():
    data = request.get_json()
    
    if not data or 'user_id' not in data or 'preferences' not in data:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        table.put_item(Item=data)
        return jsonify({"message": "Preferences saved"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Run Flask App
if __name__ == '__main__':
    with app.app_context(): 
        create_user_table()  # Ensure the SQLite user table exists before starting the app
    app.run(debug=True)
