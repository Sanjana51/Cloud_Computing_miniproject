import os
import paho.mqtt.client as mqtt
import ssl
from dotenv import load_dotenv
import boto3

# ✅ Load environment variables
load_dotenv()

# ✅ Fetch AWS and MQTT credentials from .env
AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

MQTT_BROKER = os.getenv("MQTT_BROKER")
PORT = 8883  

CA_CERT = "AmazonRootCA1.pem"
CERT_FILE = "Smart_Home.cert.pem"
KEY_FILE = "Smart_Home.private.key"

DEVICE_ID = "light_1"

# ✅ Setup MQTT Client
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("✅ Connected to AWS IoT Core!")
        client.subscribe(f"home/device/{DEVICE_ID}")
    else:
        print(f"❌ Connection failed with return code {rc}")

def on_message(client, userdata, message):
    command = message.payload.decode("utf-8")
    print(f"📩 Received command: {command}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.tls_set(CA_CERT, certfile=CERT_FILE, keyfile=KEY_FILE, tls_version=ssl.PROTOCOL_TLSv1_2)
client.on_connect = on_connect
client.on_message = on_message

# ✅ Securely Connect to DynamoDB (Only if Needed)
try:
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )
    print("✅ Successfully connected to DynamoDB!")
except Exception as e:
    print(f"❌ Error Connecting to DynamoDB: {e}")

# ✅ Connect to MQTT Broker
try:
    if not MQTT_BROKER:
        raise ValueError("❌ MQTT_BROKER not set in .env file!")

    client.connect(MQTT_BROKER, PORT, keepalive=60)
    print("🔗 Connecting to MQTT Broker...")
    client.loop_forever()
except Exception as e:
    print(f"❌ Connection Error: {e}")
