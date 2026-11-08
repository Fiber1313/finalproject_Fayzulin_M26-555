"""Настройка логирования: строковый формат и ротация файлов."""

import logging
import os
from logging.handlers import RotatingFileHandler

from valutatrade_hub.infra.settings import SettingsLoader

ACTIONS_LOGGER = "valutatrade.actions"
PARSER_LOGGER = "valutatrade.parser"
CONSOLE_FORMAT = "%(levelname)s: %(message)s"


def _make_file_handler(path, settings):
    """Создаёт обработчик с ротацией по размеру файла."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    handler = RotatingFileHandler(
        path,
        maxBytes=settings.get("log_max_bytes"),
        backupCount=settings.get("log_backup_count"),
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(settings.get("log_format"), settings.get("log_date_format"))
    )
    return handler


def setup_logging():
    """Настраивает логгеры действий (actions.log) и парсера (parser.log)."""
    settings = SettingsLoader()
    level = settings.get("log_level")
    for name, file_key in (
        (ACTIONS_LOGGER, "actions_log_file"),
        (PARSER_LOGGER, "parser_log_file"),
    ):
        logger = logging.getLogger(name)
        if logger.handlers:
            continue
        logger.setLevel(level)
        logger.addHandler(_make_file_handler(settings.get(file_key), settings))
        logger.propagate = False

    # Шаги парсера дублируются в консоль, чтобы пользователь видел прогресс
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(CONSOLE_FORMAT))
    parser_logger = logging.getLogger(PARSER_LOGGER)
    if len(parser_logger.handlers) == 1:
        parser_logger.addHandler(console)
