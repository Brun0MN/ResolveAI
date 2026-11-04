"""Environment configuration; load .env locally without leaking secrets."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv
load_dotenv()

@dataclass(frozen=True)
class Config:
    gemini_key: str = os.getenv('GEMINI_API_KEY', '').strip()
    gemini_model: str = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash').strip()
    lab_url: str = os.getenv('LAB_URL', 'http://127.0.0.1:8001').rstrip('/')
    real_lab_url: str = os.getenv('REAL_LAB_URL', '').rstrip('/')
    lab_token: str = os.getenv('LAB_TOKEN', 'resolveai-local-demo-token-change-this')
    database_path: str = os.getenv('DATABASE_PATH', './data/resolveai.sqlite3')
    lab_database_path: str = os.getenv('LAB_DATABASE_PATH', './data/lab.sqlite3')
    auto_min_confidence: float = float(os.getenv('AUTO_MIN_CONFIDENCE', '0.70'))
    # Maximum duration of each individual Gemini HTTP request (seconds).
    gemini_request_timeout_s: int = int(os.getenv('GEMINI_REQUEST_TIMEOUT_S', '20'))

config = Config()
