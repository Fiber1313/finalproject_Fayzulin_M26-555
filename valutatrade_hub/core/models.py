"""Классы предметной области: пользователь, кошелёк, портфель."""

import hashlib
import secrets
from datetime import datetime

from valutatrade_hub.core.exceptions import InsufficientFundsError
from valutatrade_hub.core.utils import (
    BASE_CURRENCY,
    DEFAULT_EXCHANGE_RATES,
    convert,
    format_amount,
)

MIN_PASSWORD_LENGTH = 4
SALT_BYTES = 4


class User:
    """Пользователь системы. Пароль хранится только в виде хеша с солью."""

    def __init__(self, user_id, username, hashed_password, salt, registration_date):
        self._user_id = user_id
        self.username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    @staticmethod
    def hash_password(password, salt):
        """Возвращает SHA-256 от пароля, склеенного с солью."""
        return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

    @staticmethod
    def validate_password(password):
        """Проверяет, что пароль — строка не короче 4 символов."""
        if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов"
            )

    @classmethod
    def create(cls, user_id, username, password):
        """Создаёт нового пользователя: генерирует соль и хеширует пароль."""
        cls.validate_password(password)
        salt = secrets.token_hex(SALT_BYTES)
        return cls(
            user_id=user_id,
            username=username,
            hashed_password=cls.hash_password(password, salt),
            salt=salt,
            registration_date=datetime.now().replace(microsecond=0),
        )

    @property
    def user_id(self):
        """Уникальный идентификатор пользователя."""
        return self._user_id

    @property
    def username(self):
        """Имя пользователя."""
        return self._username

    @username.setter
    def username(self, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value.strip()

    @property
    def hashed_password(self):
        """Хеш пароля."""
        return self._hashed_password

    @property
    def salt(self):
        """Соль пользователя."""
        return self._salt

    @property
    def registration_date(self):
        """Дата регистрации (datetime)."""
        return self._registration_date

    def get_user_info(self):
        """Возвращает информацию о пользователе без пароля."""
        return (
            f"ID: {self._user_id}, имя: {self._username}, "
            f"зарегистрирован: {self._registration_date.isoformat()}"
        )

    def change_password(self, new_password):
        """Меняет пароль: генерирует новую соль и сохраняет новый хеш."""
        self.validate_password(new_password)
        self._salt = secrets.token_hex(SALT_BYTES)
        self._hashed_password = self.hash_password(new_password, self._salt)

    def verify_password(self, password):
        """Проверяет, совпадает ли введённый пароль с сохранённым."""
        return self.hash_password(password, self._salt) == self._hashed_password

    def to_dict(self):
        """Преобразует пользователя в словарь для users.json."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data):
        """Создаёт пользователя из словаря users.json."""
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            hashed_password=data["hashed_password"],
            salt=data["salt"],
            registration_date=datetime.fromisoformat(data["registration_date"]),
        )


class Wallet:
    """Кошелёк пользователя для одной валюты."""

    def __init__(self, currency_code, balance=0.0):
        self.currency_code = currency_code
        self.balance = balance

    @staticmethod
    def validate_amount(amount):
        """Проверяет, что сумма — положительное число."""
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise ValueError("'amount' должен быть положительным числом")
        if amount <= 0:
            raise ValueError("'amount' должен быть положительным числом")

    @property
    def balance(self):
        """Текущий баланс кошелька."""
        return self._balance

    @balance.setter
    def balance(self, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    def deposit(self, amount):
        """Пополняет баланс на указанную сумму."""
        self.validate_amount(amount)
        self.balance = self._balance + amount

    def withdraw(self, amount):
        """Снимает сумму, если на балансе достаточно средств."""
        self.validate_amount(amount)
        if amount > self._balance:
            code = self.currency_code
            raise InsufficientFundsError(
                format_amount(code, self._balance), format_amount(code, amount), code
            )
        self.balance = self._balance - amount

    def get_balance_info(self):
        """Возвращает строку с текущим балансом, например 'BTC: 0.0500'."""
        amount_text = format_amount(self.currency_code, self._balance)
        return f"{self.currency_code}: {amount_text}"

    def to_dict(self):
        """Преобразует кошелёк в словарь для portfolios.json."""
        return {"currency_code": self.currency_code, "balance": self._balance}


class Portfolio:
    """Все кошельки одного пользователя."""

    def __init__(self, user_id, wallets=None, user=None):
        self._user_id = user_id
        self._wallets = wallets if wallets is not None else {}
        self._user = user

    @property
    def user_id(self):
        """Идентификатор владельца портфеля."""
        return self._user_id

    @property
    def user(self):
        """Владелец портфеля (только чтение)."""
        return self._user

    @property
    def wallets(self):
        """Копия словаря кошельков: изменить портфель через неё нельзя."""
        return dict(self._wallets)

    def add_currency(self, currency_code):
        """Добавляет новый пустой кошелёк, если такой валюты ещё нет."""
        if currency_code in self._wallets:
            raise ValueError(f"Кошелёк '{currency_code}' уже есть в портфеле")
        wallet = Wallet(currency_code)
        self._wallets[currency_code] = wallet
        return wallet

    def get_wallet(self, currency_code):
        """Возвращает кошелёк по коду валюты или None."""
        return self._wallets.get(currency_code)

    def get_total_value(self, base_currency=BASE_CURRENCY, exchange_rates=None):
        """Считает общую стоимость всех кошельков в базовой валюте."""
        rates = exchange_rates if exchange_rates is not None else DEFAULT_EXCHANGE_RATES
        total = 0.0
        for code, wallet in self._wallets.items():
            value = convert(wallet.balance, code, base_currency, rates)
            if value is not None:
                total += value
        return total

    def to_dict(self):
        """Преобразует портфель в словарь для portfolios.json."""
        wallets = {}
        for code, wallet in self._wallets.items():
            wallets[code] = {"balance": wallet.balance}
        return {"user_id": self._user_id, "wallets": wallets}

    @classmethod
    def from_dict(cls, data, user=None):
        """Создаёт портфель из словаря portfolios.json."""
        wallets = {}
        for code, wallet_data in data.get("wallets", {}).items():
            wallets[code] = Wallet(code, wallet_data["balance"])
        return cls(data["user_id"], wallets, user)
