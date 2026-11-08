"""Декоратор @log_action для логирования доменных операций."""

import functools
import inspect
import logging

from valutatrade_hub.logging_config import ACTIONS_LOGGER

logger = logging.getLogger(ACTIONS_LOGGER)


def _describe_user(arguments):
    """Достаёт имя пользователя из аргументов функции."""
    user = arguments.get("user")
    if user is not None:
        return user.username
    return arguments.get("username", "-")


def log_action(action, verbose=False):
    """Фабрика декораторов: логирует операцию action (BUY, SELL, ...).

    Пишет в лог пользователя, валюту, сумму, курс, результат OK/ERROR.
    Исключения не глотает — после записи в лог пробрасывает дальше.
    При verbose=True добавляет изменение баланса «было → стало».
    """

    def decorator(func):
        signature = inspect.signature(func)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            arguments = signature.bind(*args, **kwargs).arguments
            parts = [action, f"user='{_describe_user(arguments)}'"]
            if "currency_code" in arguments:
                parts.append(f"currency='{str(arguments['currency_code']).upper()}'")
            if "amount" in arguments:
                parts.append(f"amount={arguments['amount']:.4f}")
            try:
                result = func(*args, **kwargs)
            except Exception as error:
                parts.append("result=ERROR")
                parts.append(f"error_type={type(error).__name__}")
                parts.append(f"error_message='{error}'")
                logger.info(" ".join(parts))
                raise
            if isinstance(result, dict):
                if "rate" in result:
                    parts.append(f"rate={result['rate']:.2f}")
                    parts.append(f"base='{result.get('base', 'USD')}'")
                if verbose and "old" in result:
                    parts.append(f"balance={result['old']:.4f}->{result['new']:.4f}")
            parts.append("result=OK")
            logger.info(" ".join(parts))
            return result

        return wrapper

    return decorator
