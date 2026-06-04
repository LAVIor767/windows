from pathlib import Path
import os
import secrets

# === BASE PROJECT FOLDER ===
# נתיב הבסיס של הפרויקט – כאן נשמרים קבצים כמו CSV, cache וכו'
PROJECT_FOLDER = os.environ.get("PROJECT_FOLDER") or str(Path(__file__).parent.resolve())

# === ALPHA VANTAGE API KEY ===
# הכנס את המפתח שלך מ-Alpha Vantage כאן או ב-ENV
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "d75bl4pr01qk56kc5jr0d75bl4pr01qk56kc5jrg")
# === FLASK SECRET KEY ===
# מפתח סודי ל-Flask sessions
# אם לא מוגדר ב-ENV, ניצור אחד אוטומטית
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)

# === PRODUCTION FLAG ===
# True אם הקוד רץ בשרת HTTPS/Production, False אם מקומי
IS_PRODUCTION = os.environ.get("IS_PRODUCTION", "0") == "1"
