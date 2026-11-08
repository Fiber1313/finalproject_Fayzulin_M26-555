"""Бизнес-логика: регистрация, вход, портфель, покупка, продажа, курсы."""

from datetime import datetime

from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.core.utils import (
    BASE_CURRENCY,
    DEFAULT_EXCHANGE_RATES,
    PORTFOLIOS_FILE,
    RATES_FILE,
    RATES_TTL_SECONDS,
    STUB_SOURCE,
    USERS_FILE,
    convert,
    format_amount,
    get_usd_rate,
    load_json,
    now_iso,
    save_json,
    validate_currency_code,
)

STARTING_BALANCE = 10_000.0


# --- Пользователи ---


def load_users():
    """Загружает список пользователей из users.json."""
    return [User.from_dict(item) for item in load_json(USERS_FILE, [])]


def save_users(users):
    """Сохраняет список пользователей в users.json."""
    save_json(USERS_FILE, [user.to_dict() for user in users])


def find_user(username):
    """Ищет пользователя по имени; возвращает User или None."""
    for user in load_users():
        if user.username == username:
            return user
    return None


def register_user(username, password):
    """Создаёт пользователя и его портфель со стартовым балансом в USD."""
    users = load_users()
    for user in users:
        if user.username == username:
            raise ValueError(f"Имя пользователя '{username}' уже занято")

    new_id = max((user.user_id for user in users), default=0) + 1
    user = User.create(new_id, username, password)
    users.append(user)
    save_users(users)

    portfolio = Portfolio(new_id, user=user)
    portfolio.add_currency(BASE_CURRENCY).deposit(STARTING_BALANCE)
    portfolios = load_json(PORTFOLIOS_FILE, [])
    portfolios.append(portfolio.to_dict())
    save_json(PORTFOLIOS_FILE, portfolios)
    return user


def login_user(username, password):
    """Проверяет имя и пароль; возвращает пользователя при успехе."""
    user = find_user(username)
    if user is None:
        raise ValueError(f"Пользователь '{username}' не найден")
    if not user.verify_password(password):
        raise ValueError("Неверный пароль")
    return user


# --- Портфели ---


def load_portfolio(user):
    """Загружает портфель пользователя (или пустой, если записи нет)."""
    for item in load_json(PORTFOLIOS_FILE, []):
        if item["user_id"] == user.user_id:
            return Portfolio.from_dict(item, user)
    return Portfolio(user.user_id, user=user)


def save_portfolio(portfolio):
    """Сохраняет портфель: читает файл, заменяет запись, записывает обратно."""
    portfolios = load_json(PORTFOLIOS_FILE, [])
    portfolios = [p for p in portfolios if p["user_id"] != portfolio.user_id]
    portfolios.append(portfolio.to_dict())
    portfolios.sort(key=lambda item: item["user_id"])
    save_json(PORTFOLIOS_FILE, portfolios)


# --- Курсы ---


def load_rates_cache():
    """Читает кеш курсов rates.json."""
    return load_json(RATES_FILE, {"pairs": {}, "last_refresh": None})


def is_fresh(updated_at):
    """Проверяет, что курс обновлён не раньше, чем TTL секунд назад."""
    if not updated_at:
        return False
    updated = datetime.fromisoformat(updated_at.replace("Z", ""))
    age = (datetime.now() - updated).total_seconds()
    return age < RATES_TTL_SECONDS


def refresh_from_stub():
    """Обновляет кеш значениями из заглушки (пока нет Parser Service)."""
    cache = load_rates_cache()
    timestamp = now_iso()
    for pair, rate in DEFAULT_EXCHANGE_RATES.items():
        cache["pairs"][pair] = {
            "rate": rate,
            "updated_at": timestamp,
            "source": STUB_SOURCE,
        }
    cache["last_refresh"] = timestamp
    save_json(RATES_FILE, cache)
    return cache


def get_current_rates():
    """Возвращает словарь {'BTC_USD': курс, ...}; при пустом кеше — заглушку."""
    pairs = load_rates_cache()["pairs"]
    if not pairs:
        return dict(DEFAULT_EXCHANGE_RATES)
    rates = dict(DEFAULT_EXCHANGE_RATES)
    for pair, info in pairs.items():
        rates[pair] = info["rate"]
    return rates


def get_rate(from_code, to_code):
    """Возвращает (курс from→to, время обновления) с учётом TTL кеша."""
    from_code = validate_currency_code(from_code)
    to_code = validate_currency_code(to_code)

    cache = load_rates_cache()
    if not is_fresh(cache.get("last_refresh")):
        cache = refresh_from_stub()

    rates = {pair: info["rate"] for pair, info in cache["pairs"].items()}
    rate = convert(1.0, from_code, to_code, rates)
    if rate is None:
        raise ValueError(
            f"Курс {from_code}→{to_code} недоступен. Повторите попытку позже."
        )
    return rate, cache["last_refresh"]


def check_known_currency(code, rates):
    """Проверяет, что для валюты есть курс к USD."""
    if get_usd_rate(code, rates) is None:
        raise ValueError(f"Не удалось получить курс для {code}→{BASE_CURRENCY}")


# --- Портфель: отчёт, покупка, продажа ---


def portfolio_report(user, base=BASE_CURRENCY):
    """Считает стоимость каждого кошелька и итог в базовой валюте."""
    base = validate_currency_code(base)
    rates = get_current_rates()
    if get_usd_rate(base, rates) is None:
        raise ValueError(f"Неизвестная базовая валюта '{base}'")

    portfolio = load_portfolio(user)
    rows = []
    for code, wallet in portfolio.wallets.items():
        value = convert(wallet.balance, code, base, rates)
        rows.append((code, wallet.balance, value))
    total = portfolio.get_total_value(base, rates)
    return base, rows, total


def buy(user, currency_code, amount):
    """Покупает валюту за USD; возвращает словарь с итогами операции."""
    code = validate_currency_code(currency_code)
    if code == BASE_CURRENCY:
        raise ValueError(f"{BASE_CURRENCY} — базовая валюта, её нельзя купить")
    rates = get_current_rates()
    check_known_currency(code, rates)

    rate = get_usd_rate(code, rates)
    cost = amount * rate
    portfolio = load_portfolio(user)

    usd_wallet = portfolio.get_wallet(BASE_CURRENCY)
    if usd_wallet is None:
        usd_wallet = portfolio.add_currency(BASE_CURRENCY)
    wallet = portfolio.get_wallet(code)
    if wallet is None:
        wallet = portfolio.add_currency(code)

    old_usd, old_balance = usd_wallet.balance, wallet.balance
    usd_wallet.withdraw(cost)
    wallet.deposit(amount)
    save_portfolio(portfolio)
    return {
        "code": code,
        "amount": amount,
        "rate": rate,
        "cost": cost,
        "old": old_balance,
        "new": wallet.balance,
        "old_usd": old_usd,
        "new_usd": usd_wallet.balance,
    }


def sell(user, currency_code, amount):
    """Продаёт валюту, выручка начисляется в USD; возвращает итоги."""
    code = validate_currency_code(currency_code)
    if code == BASE_CURRENCY:
        raise ValueError(f"{BASE_CURRENCY} — базовая валюта, её нельзя продать")
    portfolio = load_portfolio(user)
    wallet = portfolio.get_wallet(code)
    if wallet is None:
        raise ValueError(
            f"У вас нет кошелька '{code}'. Добавьте валюту: "
            "она создаётся автоматически при первой покупке."
        )
    rates = get_current_rates()
    check_known_currency(code, rates)

    rate = get_usd_rate(code, rates)
    revenue = amount * rate
    usd_wallet = portfolio.get_wallet(BASE_CURRENCY)
    if usd_wallet is None:
        usd_wallet = portfolio.add_currency(BASE_CURRENCY)

    old_balance, old_usd = wallet.balance, usd_wallet.balance
    wallet.withdraw(amount)
    usd_wallet.deposit(revenue)
    save_portfolio(portfolio)
    return {
        "code": code,
        "amount": amount,
        "rate": rate,
        "revenue": revenue,
        "old": old_balance,
        "new": wallet.balance,
        "old_usd": old_usd,
        "new_usd": usd_wallet.balance,
    }


def describe_change(code, old, new):
    """Строка вида '- BTC: было 0.0000 → стало 0.0500'."""
    return (
        f"- {code}: было {format_amount(code, old)} → "
        f"стало {format_amount(code, new)}"
    )
