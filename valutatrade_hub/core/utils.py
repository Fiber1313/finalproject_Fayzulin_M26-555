"""Вспомогательные функции: валидация, форматирование, конвертация валют."""

from datetime import datetime, timezone

from valutatrade_hub.core.currencies import get_currency, is_crypto

BASE_CURRENCY = "USD"
FIAT_PRECISION = 2
CRYPTO_PRECISION = 4

# Резервные курсы: стоимость 1 единицы валюты в USD.
# Используются для оценки портфеля, если в кеше rates.json ещё нет пары.
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


def parse_utc(timestamp):
    """Превращает '2025-10-10T12:00:00Z' в datetime с часовым поясом UTC."""
    moment = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def seconds_since(timestamp):
    """Сколько секунд прошло с момента timestamp (UTC)."""
    return (datetime.now(timezone.utc) - parse_utc(timestamp)).total_seconds()


def validate_currency_code(code):
    """Проверяет код валюты по реестру и возвращает его в верхнем регистре."""
    return get_currency(code).code


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
    if is_crypto(currency_code):
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
