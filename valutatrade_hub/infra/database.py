"""DatabaseManager — доступ к JSON-хранилищу (Singleton)."""

import json
import os

from valutatrade_hub.infra.settings import SettingsLoader

TEMP_SUFFIX = ".tmp"


class DatabaseManager:
    """Абстракция над JSON-файлами: чтение, атомарная запись, обновление.

    Singleton через __new__ (как и SettingsLoader): одна точка доступа к данным.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.settings = SettingsLoader()
        return cls._instance

    def _path(self, key):
        """Путь к файлу по ключу настроек, например 'users_file'."""
        return self.settings.get(key)

    def read(self, key, default):
        """Читает JSON-файл; при отсутствии или ошибке формата — default."""
        try:
            with open(self._path(key), encoding="utf-8") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return default

    def write(self, key, data):
        """Атомарно записывает JSON: сначала во временный файл, затем rename."""
        path = self._path(key)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        temp_path = path + TEMP_SUFFIX
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)

    def update(self, key, default, modifier):
        """Безопасная операция: чтение → изменение функцией → запись."""
        data = self.read(key, default)
        data = modifier(data)
        self.write(key, data)
        return data
