"""Конфигурация Parser Service: API, списки валют, пути, таймауты."""

import os
from dataclasses import dataclass, field

ENV_FILE = ".env"
API_KEY_ENV_NAME = "EXCHANGERATE_API_KEY"


def load_env_file(path=ENV_FILE):
    """Читает файл .env (KEY=VALUE) и кладёт значения в переменные окружения.

    Файл .env не отслеживается git — в нём хранится секретный API-ключ.
    Уже заданные переменные окружения не перезаписываются.
    """
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


def _read_api_key():
    """Берёт API-ключ ExchangeRate-API из окружения (или из .env)."""
    load_env_file()
    return os.getenv(API_KEY_ENV_NAME, "")


@dataclass
class ParserConfig:
    """Все изменяемые параметры Parser Service в одном месте."""

    # Ключ загружается из переменной окружения или файла .env
    EXCHANGERATE_API_KEY: str = field(default_factory=_read_api_key)

    # Эндпоинты
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    # Списки валют
    BASE_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple = ("EUR", "GBP", "RUB", "CNY")
    CRYPTO_CURRENCIES: tuple = ("BTC", "ETH", "SOL", "TON")
    # Для этих валют дополнительно храним обратную пару: USD_RUB = рублей за 1 USD
    INVERSE_PAIR_CURRENCIES: tuple = ("RUB",)
    CRYPTO_ID_MAP: dict = field(
        default_factory=lambda: {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
            "TON": "the-open-network",
        }
    )

    # Пути
    RATES_FILE_PATH: str = "data/rates.json"
    HISTORY_FILE_PATH: str = "data/exchange_rates.json"

    # Сетевые параметры
    REQUEST_TIMEOUT: int = 10

    # Планировщик: интервал автообновления по умолчанию (секунды)
    SCHEDULER_INTERVAL: int = 300

    # Имена источников (для полей source и флага --source)
    COINGECKO_SOURCE: str = "CoinGecko"
    EXCHANGERATE_SOURCE: str = "ExchangeRate-API"
