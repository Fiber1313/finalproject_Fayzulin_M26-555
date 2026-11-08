"""Командный интерфейс ValutaTrade Hub: разбор команд и вывод результатов."""

import shlex

from valutatrade_hub.core import usecases
from valutatrade_hub.core.utils import (
    BASE_CURRENCY,
    format_amount,
    format_money,
    format_rate,
    parse_amount,
)

PROMPT = "valuta> "
OPTION_PREFIX = "--"

HELP_TEXT = """
***ValutaTrade Hub***
Команды:
  register --username <имя> --password <пароль>   регистрация
  login --username <имя> --password <пароль>      вход
  logout                                          выход из аккаунта
  show-portfolio [--base <валюта>]                портфель и его стоимость
  buy --currency <код> --amount <количество>      купить валюту
  sell --currency <код> --amount <количество>     продать валюту
  get-rate --from <код> --to <код>                курс валюты
  help                                            эта справка
  exit                                            выход из программы
"""

# Текущая сессия: залогиненный пользователь (или None).
session = {"user": None}


def parse_options(tokens):
    """Превращает ['--username', 'alice'] в словарь {'username': 'alice'}."""
    options = {}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith(OPTION_PREFIX):
            raise ValueError(f"Неожиданный аргумент '{token}'")
        name = token[len(OPTION_PREFIX):]
        if index + 1 >= len(tokens) or tokens[index + 1].startswith(OPTION_PREFIX):
            raise ValueError(f"Для --{name} не указано значение")
        options[name] = tokens[index + 1]
        index += 2
    return options


def require(options, *names):
    """Проверяет, что обязательные аргументы указаны, и возвращает их значения."""
    values = []
    for name in names:
        if name not in options:
            raise ValueError(f"Не указан обязательный аргумент --{name}")
        values.append(options[name])
    return values


def current_user():
    """Возвращает залогиненного пользователя или бросает ошибку."""
    if session["user"] is None:
        raise ValueError("Сначала выполните login")
    return session["user"]


def cmd_register(options):
    """Команда register."""
    username, password = require(options, "username", "password")
    user = usecases.register_user(username, password)
    print(
        f"Пользователь '{user.username}' зарегистрирован (id={user.user_id}). "
        f"Войдите: login --username {user.username} --password ****"
    )


def cmd_login(options):
    """Команда login."""
    username, password = require(options, "username", "password")
    session["user"] = usecases.login_user(username, password)
    print(f"Вы вошли как '{session['user'].username}'")


def cmd_logout(options):
    """Команда logout."""
    user = current_user()
    session["user"] = None
    print(f"Пользователь '{user.username}' вышел из системы")


def cmd_show_portfolio(options):
    """Команда show-portfolio."""
    user = current_user()
    base, rows, total = usecases.portfolio_report(
        user, options.get("base", BASE_CURRENCY)
    )
    if not rows:
        print(f"Портфель пользователя '{user.username}' пуст")
        return
    print(f"Портфель пользователя '{user.username}' (база: {base}):")
    for code, balance, value in rows:
        value_text = format_money(value) if value is not None else "нет курса"
        print(f"- {code}: {format_amount(code, balance)}  → {value_text} {base}")
    print("---------------------------------")
    print(f"ИТОГО: {format_money(total)} {base}")


def cmd_buy(options):
    """Команда buy."""
    user = current_user()
    code, amount_text = require(options, "currency", "amount")
    result = usecases.buy(user, code, parse_amount(amount_text))
    code = result["code"]
    print(
        f"Покупка выполнена: {format_amount(code, result['amount'])} {code} "
        f"по курсу {format_rate(result['rate'])} {BASE_CURRENCY}/{code}"
    )
    print("Изменения в портфеле:")
    print(usecases.describe_change(code, result["old"], result["new"]))
    print(
        usecases.describe_change(BASE_CURRENCY, result["old_usd"], result["new_usd"])
    )
    print(f"Оценочная стоимость покупки: {format_money(result['cost'])} USD")


def cmd_sell(options):
    """Команда sell."""
    user = current_user()
    code, amount_text = require(options, "currency", "amount")
    result = usecases.sell(user, code, parse_amount(amount_text))
    code = result["code"]
    print(
        f"Продажа выполнена: {format_amount(code, result['amount'])} {code} "
        f"по курсу {format_rate(result['rate'])} {BASE_CURRENCY}/{code}"
    )
    print("Изменения в портфеле:")
    print(usecases.describe_change(code, result["old"], result["new"]))
    print(
        usecases.describe_change(BASE_CURRENCY, result["old_usd"], result["new_usd"])
    )
    print(f"Оценочная выручка: {format_money(result['revenue'])} USD")


def cmd_get_rate(options):
    """Команда get-rate."""
    from_code, to_code = require(options, "from", "to")
    rate, updated_at = usecases.get_rate(from_code, to_code)
    from_code, to_code = from_code.upper(), to_code.upper()
    updated_text = updated_at.replace("T", " ") if updated_at else "неизвестно"
    print(
        f"Курс {from_code}→{to_code}: {format_rate(rate)} "
        f"(обновлено: {updated_text})"
    )
    if rate:
        print(f"Обратный курс {to_code}→{from_code}: {format_rate(1 / rate)}")


COMMANDS = {
    "register": cmd_register,
    "login": cmd_login,
    "logout": cmd_logout,
    "show-portfolio": cmd_show_portfolio,
    "buy": cmd_buy,
    "sell": cmd_sell,
    "get-rate": cmd_get_rate,
}


def execute(line):
    """Разбирает и выполняет одну строку ввода. Возвращает False для exit."""
    try:
        tokens = shlex.split(line)
    except ValueError:
        print("Некорректный ввод: проверьте кавычки")
        return True
    if not tokens:
        return True

    command, args = tokens[0], tokens[1:]
    if command == "exit":
        return False
    if command == "help":
        print(HELP_TEXT)
        return True
    handler = COMMANDS.get(command)
    if handler is None:
        print(f"Неизвестная команда '{command}'. Введите help для справки.")
        return True

    try:
        handler(parse_options(args))
    except ValueError as error:
        print(error)
    return True


def main():
    """Запускает интерактивный режим приложения."""
    print(HELP_TEXT)
    while True:
        try:
            line = input(PROMPT)
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not execute(line):
            break
