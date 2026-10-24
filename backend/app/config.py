# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

# --- Общие ---
DB_PATH = os.getenv("DB_PATH", "game.db")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

# --- Игра ---
MAX_SESSIONS = 10
MAX_PLAYERS = 10
MIN_PLAYERS = 1

ROUNDS_TOTAL = 6
ROUND_DURATION_SEC = 600
DISCUSSION_PAUSE_SEC = 0   # обсуждения оффлайн, пауза не нужна

START_MONEY = 1000
START_DEV = 60
START_LIFE = 55
START_ANOMALY = 5
START_LIFE_IS_FIXED = True   # life=55 на старте, не пересчитывается

# Стоимость действий
COST_DEV = 150
COST_SHIELD = 300
COST_TECH = 500
COST_MISSILES = [150, 150, 150]   # 1-й, 2-й, 3-й метеорит

DEV_GAIN = 20
MAX_MISSILES_PER_ROUND = 3
MAX_MISSILES_PER_TARGET_CITY_PER_PLAYER = 1
MAX_MISSILE_TO_ANOMALY_PER_ROUND = 1

# Аномалия
ANOMALY_ON_TECH = 5
ANOMALY_ON_BUY = 2
ANOMALY_ON_SEND = 3
ANOMALY_ON_DROP = -20
ANOMALY_LIMIT = 100

# Санкции
SANCTION_PENALTY = 0.10
SANCTION_PENALTY_MAX = 0.70

# Планеты и города
PLANETS = [
    "Татуин", "Мандалор", "Джакку", "Корусант",
    "Альдераан", "Мустафар", "Набу", "Эндор",
    "Хот", "Дагоба",
]

CITY_NAMES = {
    "Татуин":    ["Таскен", "Эспа", "Анкор", "Эйсли"],
    "Мандалор":  ["Санари", "Киримо", "Кедабе", "Энцери"],
    "Джакку":    ["Ниима", "Шир", "Айрон", "Туанул"],
    "Корусант":  ["Талус", "Эгела", "Кору", "Селония"],
    "Альдераан": ["Кревасс", "Альдера", "Олденфорт", "Белоа"],
    "Мустафар":  ["Фралидеджа", "Джестефад", "Игнис", "Лефрани"],
    "Набу":      ["Авендор", "Тид", "Гунга", "Рабан"],
    "Эндор":     ["Брайттри", "Три-Хаус", "Хэппи-Гроув", "Мун-Форест"],
    "Хот":       ["Эхо-База", "Айс-Плейн", "Фростхолл", "Сноу-Ридж"],
    "Дагоба":    ["Бог-Холлоу", "Мшистая Топь", "Туманная Хижина", "Зелёный Пруд"],
}

# --- Сводки ---
import os as _os
BASE_DIR = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
STATIC_DIR = _os.path.join(BASE_DIR, "static")
SUMMARY_DIR = _os.path.join(STATIC_DIR, "summary")
_os.makedirs(SUMMARY_DIR, exist_ok=True)