"""SettingsLoader — единая точка конфигурации проекта (Singleton)."""

import os
import tomllib

PYPROJECT_FILE = "pyproject.toml"
SETTINGS_SECTION = "valutatrade"

DEFAULT_SETTINGS = {
    "data_dir": "data",
    "users_file": "data/users.json",
    "portfolios_file": "data/portfolios.json",
    "rates_file": "data/rates.json",
    "exchange_rates_file": "data/exchange_rates.json",
    "rates_ttl_seconds": 300,
    "default_base_currency": "USD",
    "starting_balance": 10000.0,
    "log_dir": "logs",
    "actions_log_file": "logs/actions.log",
    "parser_log_file": "logs/parser.log",
    "log_level": "INFO",
    "log_format": "%(levelname)s %(asctime)s %(message)s",
    "log_date_format": "%Y-%m-%dT%H:%M:%S",
    "log_max_bytes": 1_000_000,
    "log_backup_count": 3,
}


class SettingsLoader:
    """Загружает настройки из pyproject.toml ([tool.valutatrade]).

    Singleton реализован через __new__: это самый простой и читаемый способ —
    при любом вызове SettingsLoader() возвращается один и тот же объект,
    а настройки читаются только при первом создании.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._settings = {}
            cls._instance.reload()
        return cls._instance

    def reload(self):
        """Перечитывает конфигурацию: значения по умолчанию + pyproject.toml."""
        settings = dict(DEFAULT_SETTINGS)
        if os.path.exists(PYPROJECT_FILE):
            with open(PYPROJECT_FILE, "rb") as file:
                data = tomllib.load(file)
            settings.update(data.get("tool", {}).get(SETTINGS_SECTION, {}))
        self._settings = settings

    def get(self, key, default=None):
        """Возвращает значение настройки или default, если ключа нет."""
        return self._settings.get(key, default)
