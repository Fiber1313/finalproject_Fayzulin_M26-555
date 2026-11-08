"""Иерархия валют: абстрактная Currency и наследники FiatCurrency/CryptoCurrency."""

from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError

MIN_CODE_LENGTH = 2
MAX_CODE_LENGTH = 5


class Currency(ABC):
    """Базовая валюта: человекочитаемое имя и код (тикер)."""

    def __init__(self, name, code):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Название валюты не может быть пустым")
        if (
            not isinstance(code, str)
            or code != code.upper()
            or " " in code
            or not MIN_CODE_LENGTH <= len(code) <= MAX_CODE_LENGTH
        ):
            raise ValueError(f"Некорректный код валюты '{code}'")
        self.name = name
        self.code = code

    @abstractmethod
    def get_display_info(self):
        """Строковое представление валюты для интерфейса и логов."""


class FiatCurrency(Currency):
    """Фиатная валюта, выпускаемая государством или союзом."""

    def __init__(self, name, code, issuing_country):
        super().__init__(name, code)
        self.issuing_country = issuing_country

    def get_display_info(self):
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Криптовалюта с алгоритмом консенсуса и рыночной капитализацией."""

    def __init__(self, name, code, algorithm, market_cap):
        super().__init__(name, code)
        self.algorithm = algorithm
        self.market_cap = market_cap

    def get_display_info(self):
        market_cap = f"{self.market_cap:.2e}".replace("e+", "e")
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {market_cap})"
        )


# Реестр поддерживаемых валют: код -> объект валюты.
_REGISTRY = {
    currency.code: currency
    for currency in (
        FiatCurrency("US Dollar", "USD", "United States"),
        FiatCurrency("Euro", "EUR", "Eurozone"),
        FiatCurrency("British Pound", "GBP", "United Kingdom"),
        FiatCurrency("Russian Ruble", "RUB", "Russia"),
        FiatCurrency("Chinese Yuan", "CNY", "China"),
        CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
        CryptoCurrency("Ethereum", "ETH", "Ethash", 4.47e11),
        CryptoCurrency("Solana", "SOL", "Proof of History", 6.5e10),
        CryptoCurrency("Toncoin", "TON", "Catchain", 1.4e10),
    )
}


def get_currency(code):
    """Возвращает валюту по коду или бросает CurrencyNotFoundError."""
    if not isinstance(code, str) or not code.strip():
        raise CurrencyNotFoundError(code)
    currency = _REGISTRY.get(code.strip().upper())
    if currency is None:
        raise CurrencyNotFoundError(code.strip().upper())
    return currency


def get_supported_codes():
    """Список кодов всех поддерживаемых валют."""
    return list(_REGISTRY)


def get_all_currencies():
    """Список всех поддерживаемых валют."""
    return list(_REGISTRY.values())


def is_crypto(code):
    """Проверяет, является ли валюта криптовалютой."""
    return isinstance(_REGISTRY.get(code), CryptoCurrency)
