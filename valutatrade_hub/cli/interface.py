"""Командный интерфейс ValutaTrade Hub: разбор команд и вывод результатов."""

import shlex

from prettytable import PrettyTable

from valutatrade_hub.core import usecases
from valutatrade_hub.core.currencies import get_all_currencies, get_supported_codes
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.core.utils import (
    BASE_CURRENCY,
    format_amount,
    format_money,
    format_rate,
    parse_amount,
)
from valutatrade_hub.logging_config import setup_logging

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
  list-currencies                                 поддерживаемые валюты
  update-rates [--source coingecko|exchangerate]  обновить курсы из API
  show-rates [--currency <код>] [--top <N>] [--base <код>]
                                                  курсы из локального кеша
  schedule-updates [--interval <сек>] [--times <N>]
                                                  автообновление курсов
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
    base, rows, total = usecases.portfolio_report(user, options.get("base"))
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
    from_upper, to_upper = from_code.upper(), to_code.upper()
    try:
        rate, updated_at, is_stale = usecases.get_rate(from_code, to_code)
    except ApiRequestError as error:
        print(f"Курс {from_upper}→{to_upper} недоступен. Повторите попытку позже.")
        print(f"Причина: {error.reason}")
        return
    updated_text = updated_at.replace("T", " ").rstrip("Z") if updated_at else "-"
    print(
        f"Курс {from_upper}→{to_upper}: {format_rate(rate)} "
        f"(обновлено: {updated_text})"
    )
    if rate:
        print(f"Обратный курс {to_upper}→{from_upper}: {format_rate(1 / rate)}")
    if is_stale:
        print("Внимание: данные устарели. Выполните 'update-rates'.")


def cmd_update_rates(options):
    """Команда update-rates: немедленно обновить курсы из внешних API."""
    try:
        report = usecases.refresh_rates(options.get("source"))
    except ApiRequestError as error:
        print(f"Update failed: {error.reason}. Check logs/parser.log for details.")
        return
    summary = (
        f"Total rates updated: {report['total']}. "
        f"Last refresh: {report['last_refresh']}"
    )
    if report["errors"]:
        print(
            "Update completed with errors. Check logs/parser.log for details. "
            + summary
        )
    else:
        print(f"Update successful. {summary}")


def cmd_show_rates(options):
    """Команда show-rates: курсы из локального кеша в виде таблицы."""
    top = options.get("top")
    if top is not None:
        if not top.isdigit() or int(top) <= 0:
            raise ValueError("'top' должен быть положительным целым числом")
        top = int(top)
    last_refresh, rows = usecases.show_rates(
        options.get("currency"), top, options.get("base")
    )
    print(f"Rates from cache (updated at {last_refresh}):")
    table = PrettyTable(["Pair", "Rate", "Updated at", "Source"])
    table.align = "l"
    for pair, rate, updated_at, source in rows:
        table.add_row([pair, format_rate(rate), updated_at, source])
    print(table)


def cmd_schedule_updates(options):
    """Команда schedule-updates: периодическое обновление курсов."""
    interval = int(options.get("interval", usecases.scheduler_interval()))
    times = options.get("times")
    print(f"Автообновление каждые {interval} с. Остановить: Ctrl+C")
    done = usecases.run_scheduler(interval, int(times) if times else None)
    print(f"Выполнено обновлений: {done}")


def cmd_list_currencies(options):
    """Команда list-currencies: показывает все поддерживаемые валюты."""
    table = PrettyTable(["Валюта"])
    table.align = "l"
    for currency in get_all_currencies():
        table.add_row([currency.get_display_info()])
    print(table)


COMMANDS = {
    "register": cmd_register,
    "login": cmd_login,
    "logout": cmd_logout,
    "show-portfolio": cmd_show_portfolio,
    "buy": cmd_buy,
    "sell": cmd_sell,
    "get-rate": cmd_get_rate,
    "list-currencies": cmd_list_currencies,
    "update-rates": cmd_update_rates,
    "show-rates": cmd_show_rates,
    "schedule-updates": cmd_schedule_updates,
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
    except InsufficientFundsError as error:
        print(error)
    except CurrencyNotFoundError as error:
        print(error)
        print(f"Поддерживаемые валюты: {', '.join(get_supported_codes())}")
        print("Подсказка: help — список команд, list-currencies — все валюты.")
    except ApiRequestError as error:
        print(error)
        print("Повторите попытку позже или проверьте подключение к сети.")
    except ValueError as error:
        print(error)
    return True


def main():
    """Запускает интерактивный режим приложения."""
    setup_logging()
    print(HELP_TEXT)
    while True:
        try:
            line = input(PROMPT)
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not execute(line):
            break
