"""Вспомогательные функции: JSON-файлы, валидация, форматирование, конвертация."""

import json
import os
from datetime import datetime

DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
PORTFOLIOS_FILE = os.path.join(DATA_DIR, "portfolios.json")
RATES_FILE = os.path.join(DATA_DIR, "rates.json")

BASE_CURRENCY = "USD"
CRYPTO_CODES = ("BTC", "ETH", "SOL", "TON")
FIAT_PRECISION = 2
CRYPTO_PRECISION = 4
MIN_CODE_LENGTH = 2
MAX_CODE_LENGTH = 5
RATES_TTL_SECONDS = 300
STUB_SOURCE = "StubRates"

# Заглушка курсов: стоимость 1 единицы валюты в USD.
# Используется, пока не подключён Parser Service.
DEFAULT_EXCHANGE_RATES = {
    "EUR_USD": 1.0786,
    "GBP_USD": 1.2740,
    "RUB_USD": 0.01016,
    "CNY_USD": 0.1405,
    "BTC_USD": 59337.21,
    "ETH_USD": 3720.00,
    "SOL_USD": 145.12,
    "TON_USD": 5.42,
}


def load_json(path, default):
    """Читает JSON-файл; если файла нет или он пуст, возвращает default."""
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    """Сохраняет данные в JSON-файл, создавая папку при необходимости."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def now_iso():
    """Текущее время в ISO-формате без микросекунд."""
    return datetime.now().replace(microsecond=0).isoformat()


def validate_currency_code(code):
    """Проверяет код валюты и возвращает его в верхнем регистре."""
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Код валюты не может быть пустым")
    code = code.strip().upper()
    if not (MIN_CODE_LENGTH <= len(code) <= MAX_CODE_LENGTH) or not code.isalpha():
        raise ValueError(f"Некорректный код валюты '{code}'")
    return code


def parse_amount(text):
    """Превращает строку в положительное число или бросает ValueError."""
    try:
        amount = float(text)
    except (TypeError, ValueError):
        raise ValueError("'amount' должен быть положительным числом") from None
    if amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    return amount


def make_pair(from_code, to_code):
    """Возвращает ключ пары курса, например 'BTC_USD'."""
    return f"{from_code}_{to_code}"


def format_amount(currency_code, amount):
    """Форматирует сумму: крипта с 4 знаками после запятой, фиат с 2."""
    if currency_code in CRYPTO_CODES:
        return f"{amount:.{CRYPTO_PRECISION}f}"
    return f"{amount:.{FIAT_PRECISION}f}"


def format_money(amount):
    """Форматирует денежную сумму с разделителем тысяч: 3,329.00."""
    return f"{amount:,.2f}"


def format_rate(rate):
    """Форматирует курс: крупные числа с 2 знаками, мелкие — точнее."""
    if rate >= 100:
        return f"{rate:.2f}"
    if rate >= 1:
        return f"{rate:.4f}"
    return f"{rate:.8f}"


def get_usd_rate(currency_code, rates):
    """Возвращает стоимость 1 единицы валюты в USD или None, если курса нет."""
    if currency_code == BASE_CURRENCY:
        return 1.0
    return rates.get(make_pair(currency_code, BASE_CURRENCY))


def convert(amount, from_code, to_code, rates):
    """Переводит сумму из одной валюты в другую через USD (кросс-курс)."""
    from_usd = get_usd_rate(from_code, rates)
    to_usd = get_usd_rate(to_code, rates)
    if from_usd is None or to_usd is None:
        return None
    return amount * from_usd / to_usd
