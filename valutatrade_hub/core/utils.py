"""Вспомогательные функции: форматирование сумм и конвертация по курсам."""

BASE_CURRENCY = "USD"
CRYPTO_CODES = ("BTC", "ETH", "SOL", "TON")
FIAT_PRECISION = 2
CRYPTO_PRECISION = 4

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


def make_pair(from_code, to_code):
    """Возвращает ключ пары курса, например 'BTC_USD'."""
    return f"{from_code}_{to_code}"


def format_amount(currency_code, amount):
    """Форматирует сумму: крипта с 4 знаками после запятой, фиат с 2."""
    if currency_code in CRYPTO_CODES:
        return f"{amount:.{CRYPTO_PRECISION}f}"
    return f"{amount:.{FIAT_PRECISION}f}"


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
