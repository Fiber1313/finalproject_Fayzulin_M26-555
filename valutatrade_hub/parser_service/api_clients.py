"""Клиенты внешних API курсов: CoinGecko (крипта) и ExchangeRate-API (фиат)."""

import time
from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError

HTTP_OK = 200
MS_IN_SECOND = 1000

# Понятные причины для частых HTTP-ошибок
HTTP_ERROR_REASONS = {
    401: "неверный или отсутствующий API-ключ (401)",
    403: "доступ запрещён, проверьте API-ключ (403)",
    404: "неверный адрес запроса (404)",
    429: "превышен лимит запросов, попробуйте позже (429)",
}


class BaseApiClient(ABC):
    """Единый интерфейс клиента: fetch_rates() -> {'BTC_USD': 59337.21, ...}."""

    source_name = "BaseApi"

    def __init__(self, config):
        self.config = config
        self.last_meta = {}

    def _get(self, url, params=None):
        """GET-запрос с таймаутом; ошибки сети и HTTP → ApiRequestError."""
        started = time.monotonic()
        try:
            response = requests.get(
                url, params=params, timeout=self.config.REQUEST_TIMEOUT
            )
        except requests.exceptions.Timeout:
            raise ApiRequestError(f"{self.source_name}: превышено время ожидания")
        except requests.exceptions.RequestException as error:
            raise ApiRequestError(f"{self.source_name}: ошибка сети ({error})")

        if response.status_code != HTTP_OK:
            reason = HTTP_ERROR_REASONS.get(
                response.status_code, f"HTTP {response.status_code}"
            )
            raise ApiRequestError(f"{self.source_name}: {reason}")

        self.last_meta = {
            "request_ms": round((time.monotonic() - started) * MS_IN_SECOND),
            "status_code": response.status_code,
            "etag": response.headers.get("ETag"),
        }
        try:
            return response.json()
        except ValueError:
            raise ApiRequestError(f"{self.source_name}: ответ не является JSON")

    @abstractmethod
    def fetch_rates(self):
        """Возвращает словарь курсов к базовой валюте: {'BTC_USD': 59337.21}."""


class CoinGeckoClient(BaseApiClient):
    """Курсы криптовалют через CoinGecko (по ID монет, а не тикерам)."""

    source_name = "CoinGecko"

    def fetch_rates(self):
        """Запрашивает цены монет в USD и возвращает {'BTC_USD': ..., ...}."""
        base = self.config.BASE_CURRENCY
        id_map = self.config.CRYPTO_ID_MAP
        ids = [id_map[code] for code in self.config.CRYPTO_CURRENCIES]
        data = self._get(
            self.config.COINGECKO_URL,
            params={"ids": ",".join(ids), "vs_currencies": base.lower()},
        )

        rates = {}
        for code in self.config.CRYPTO_CURRENCIES:
            price = data.get(id_map[code], {}).get(base.lower())
            if isinstance(price, (int, float)) and price > 0:
                rates[f"{code}_{base}"] = float(price)
        if not rates:
            raise ApiRequestError(f"{self.source_name}: в ответе нет курсов")
        self.last_meta["raw_ids"] = {
            pair.split("_")[0]: id_map[pair.split("_")[0]] for pair in rates
        }
        return rates


class ExchangeRateApiClient(BaseApiClient):
    """Курсы фиатных валют через ExchangeRate-API (нужен ключ)."""

    source_name = "ExchangeRate-API"

    def fetch_rates(self):
        """Запрашивает курсы фиата к USD и возвращает {'EUR_USD': ..., ...}."""
        if not self.config.EXCHANGERATE_API_KEY:
            raise ApiRequestError(
                f"{self.source_name}: не задан ключ EXCHANGERATE_API_KEY"
            )
        base = self.config.BASE_CURRENCY
        url = (
            f"{self.config.EXCHANGERATE_API_URL}/"
            f"{self.config.EXCHANGERATE_API_KEY}/latest/{base}"
        )
        data = self._get(url)
        if data.get("result") != "success":
            raise ApiRequestError(
                f"{self.source_name}: {data.get('error-type', 'неизвестная ошибка')}"
            )

        # API v6 кладёт курсы в conversion_rates (в старых версиях — rates).
        api_rates = data.get("conversion_rates") or data.get("rates") or {}

        # API отдаёт «сколько EUR за 1 USD», а нам нужно «сколько USD за 1 EUR»,
        # поэтому берём обратное значение.
        rates = {}
        for code in self.config.FIAT_CURRENCIES:
            value = api_rates.get(code)
            if isinstance(value, (int, float)) and value > 0:
                rates[f"{code}_{base}"] = 1 / value
                if code in self.config.INVERSE_PAIR_CURRENCIES:
                    rates[f"{base}_{code}"] = float(value)
        if not rates:
            raise ApiRequestError(f"{self.source_name}: в ответе нет курсов")
        return rates
