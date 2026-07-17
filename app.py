import os
import json
import hashlib
import logging
from datetime import datetime
from flask import Flask, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor

# ========================= CONFIG =========================
app = Flask(__name__)

# Railway Postgres (use these env vars set in Railway)
DATABASE_URL = os.getenv("DATABASE_URL")  # Preferred
# Or individual vars:
DB_HOST = os.getenv("PGHOST")
DB_PORT = os.getenv("PGPORT", "5432")
DB_NAME = os.getenv("PGDATABASE")
DB_USER = os.getenv("PGUSER")
DB_PASSWORD = os.getenv("PGPASSWORD")

# eBay verification token (you set this when creating the Destination)
# EBAY_VERIFICATION_TOKEN = os.getenv("EBAY_VERIFICATION_TOKEN")  # 32-80 chars
EBAY_VERIFICATION_TOKEN = "MiDwEsT_dIeSeL_Kyle_kRaEmEr_ThisIsWild"

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================= DB CONNECTION =========================
def get_db_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    else:
        return psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )

# Create table if it doesn't exist (run once or on startup)
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ebay_notifications (
            id SERIAL PRIMARY KEY,
            notification_id TEXT UNIQUE NOT NULL,
            topic TEXT NOT NULL,
            event_date TIMESTAMPTZ,
            publish_date TIMESTAMPTZ,
            payload JSONB NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    logger.info("Database initialized.")

# ========================= WEBHOOK ENDPOINT =========================
@app.route('/ebay-webhook', methods=['GET', 'POST'])
def ebay_webhook():
    logger.info("=" * 60)
    logger.info(f"🚀 EBAY WEBHOOK HIT at {datetime.now()}")
    logger.info(f"Method: {request.method}")
    logger.info(f"Full URL: {request.url}")

    # Log all headers (important for eBay)
    for key, value in request.headers.items():
        logger.info(f"Header {key}: {value}")

    challenge_code = request.args.get('challenge_code')
    if challenge_code:
        logger.info("🔑 Challenge verification request received")
        # ... your existing challenge code ...
        return jsonify({"challengeResponse": challenge_response}), 200

    # Log the body
    if request.data:
        try:
            payload = request.get_json(force=True)
            logger.info(f"Payload: {json.dumps(payload, indent=2)[:800]}...")
        except:
            logger.info(f"Raw body: {request.data[:500]}")
    else:
        logger.info("No body received")

    logger.info("=" * 60)
    return jsonify({"status": "received"}), 200

    # ... rest of your normal notification code ...

@app.route('/ping', methods=['GET'])
def ping():
    logger.info(f"PING received at {datetime.now()}")
    return jsonify({
        "status": "alive",
        "time": datetime.now().isoformat(),
        "message": "Webhook is reachable"
    }), 200

@app.route('/debug-challenge', methods=['GET'])
def debug_challenge():
    return jsonify({
        "full_url": request.url,
        "url_root": request.url_root,
        "path": request.path,
        "args": dict(request.args)
    })
    # Normal notification handling below...
    # (keep your existing payload code here)

    # Normal Notification
    try:
        payload = request.get_json()
        if not payload:
            return jsonify({"error": "Invalid JSON"}), 400

        # Basic extraction
        metadata = payload.get("metadata", {})
        notification = payload.get("notification", {})
        
        topic = metadata.get("topic")
        notification_id = notification.get("notificationId")
        event_date = notification.get("eventDate")
        publish_date = notification.get("publishDate")

        logger.info(f"Received eBay notification: {topic} - ID: {notification_id}")

        # Insert into DB
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO ebay_notifications 
            (notification_id, topic, event_date, publish_date, payload)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (notification_id) DO NOTHING
        """, (
            notification_id,
            topic,
            event_date,
            publish_date,
            json.dumps(payload)
        ))
        
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"Error processing notification: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200


if __name__ == '__main__':
    init_db()
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
