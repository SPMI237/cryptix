import os
import json

APP_DATA_DIR = os.path.join(
    os.environ.get("APPDATA") or os.path.expanduser("~"),
    "Cryptix"
)
os.makedirs(APP_DATA_DIR, exist_ok=True)

SETTINGS_FILE = os.path.join(APP_DATA_DIR, "settings.json")


def load_settings():
    if not os.path.isfile(SETTINGS_FILE):
        return {}

    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(data: dict):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass