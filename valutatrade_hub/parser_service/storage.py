"""Хранилище Parser Service: снимок rates.json и история exchange_rates.json."""

import json
import os

TEMP_SUFFIX = ".tmp"


def read_json(path, default):
    """Читает JSON-файл; при отсутствии или повреждении возвращает default."""
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json_atomic(path, data):
    """Атомарная запись: пишем во временный файл, затем переименовываем."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    temp_path = path + TEMP_SUFFIX
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)


class RatesStorage:
    """Чтение и запись файлов курсов."""

    def __init__(self, config):
        self.rates_path = config.RATES_FILE_PATH
        self.history_path = config.HISTORY_FILE_PATH

    def read_snapshot(self):
        """Текущий снимок курсов {'pairs': {...}, 'last_refresh': ...}."""
        snapshot = read_json(self.rates_path, {})
        snapshot.setdefault("pairs", {})
        snapshot.setdefault("last_refresh", None)
        return snapshot

    def save_snapshot(self, pairs, last_refresh):
        """Обновляет снимок: пара перезаписывается, только если данные свежее."""
        snapshot = self.read_snapshot()
        for pair, info in pairs.items():
            current = snapshot["pairs"].get(pair)
            if current is None or info["updated_at"] >= current["updated_at"]:
                snapshot["pairs"][pair] = info
        snapshot["last_refresh"] = last_refresh
        write_json_atomic(self.rates_path, snapshot)
        return snapshot

    def append_history(self, records):
        """Дописывает замеры в историю, пропуская записи с уже известным id."""
        history = read_json(self.history_path, [])
        known_ids = {record["id"] for record in history}
        added = 0
        for record in records:
            if record["id"] not in known_ids:
                history.append(record)
                known_ids.add(record["id"])
                added += 1
        write_json_atomic(self.history_path, history)
        return added
