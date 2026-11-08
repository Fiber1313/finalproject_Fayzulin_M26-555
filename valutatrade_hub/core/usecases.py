"""Бизнес-логика: регистрация, вход, портфель, покупка, продажа, курсы."""

from valutatrade_hub.core.currencies import is_crypto
from valutatrade_hub.core.exceptions import ApiRequestError, CurrencyNotFoundError
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.core.utils import (
    BASE_CURRENCY,
    DEFAULT_EXCHANGE_RATES,
    convert,
    format_amount,
    get_usd_rate,
    seconds_since,
    validate_currency_code,
)
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.scheduler import RatesScheduler
from valutatrade_hub.parser_service.updater import build_updater

USERS = "users_file"
PORTFOLIOS = "portfolios_file"
RATES = "rates_file"
EMPTY_RATES_CACHE = {"pairs": {}, "last_refresh": None}

settings = SettingsLoader()
database = DatabaseManager()


# --- Пользователи ---


def load_users():
    """Загружает список пользователей из users.json."""
    return [User.from_dict(item) for item in database.read(USERS, [])]


def find_user(username):
    """Ищет пользователя по имени; возвращает User или None."""
    for user in load_users():
        if user.username == username:
            return user
    return None


@log_action("REGISTER")
def register_user(username, password):
    """Создаёт пользователя и его портфель со стартовым балансом в USD."""
    users = load_users()
    for user in users:
        if user.username == username:
            raise ValueError(f"Имя пользователя '{username}' уже занято")

    new_id = max((user.user_id for user in users), default=0) + 1
    user = User.create(new_id, username, password)
    database.update(USERS, [], lambda data: data + [user.to_dict()])

    portfolio = Portfolio(new_id, user=user)
    portfolio.add_currency(BASE_CURRENCY).deposit(settings.get("starting_balance"))
    database.update(PORTFOLIOS, [], lambda data: data + [portfolio.to_dict()])
    return user


@log_action("LOGIN")
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
    for item in database.read(PORTFOLIOS, []):
        if item["user_id"] == user.user_id:
            return Portfolio.from_dict(item, user)
    return Portfolio(user.user_id, user=user)


def save_portfolio(portfolio):
    """Сохраняет портфель: чтение → замена записи → атомарная запись."""

    def replace_record(portfolios):
        """Заменяет запись портфеля пользователя в списке."""
        others = [p for p in portfolios if p["user_id"] != portfolio.user_id]
        others.append(portfolio.to_dict())
        return sorted(others, key=lambda item: item["user_id"])

    database.update(PORTFOLIOS, [], replace_record)


# --- Курсы ---


def load_rates_cache():
    """Читает кеш курсов rates.json."""
    return database.read(RATES, dict(EMPTY_RATES_CACHE))


def is_fresh(timestamp):
    """Проверяет, что метка времени моложе TTL из настроек."""
    if not timestamp:
        return False
    return seconds_since(timestamp) < settings.get("rates_ttl_seconds")


def refresh_rates(source=None):
    """Запускает Parser Service и возвращает отчёт об обновлении."""
    return build_updater(source).run_update()


def scheduler_interval():
    """Интервал автообновления по умолчанию из конфигурации парсера."""
    return ParserConfig().SCHEDULER_INTERVAL


def run_scheduler(interval, times=None):
    """Запускает периодическое обновление курсов; возвращает число запусков."""
    return RatesScheduler(build_updater(), interval).run(times)


def get_current_rates():
    """Возвращает словарь {'BTC_USD': курс, ...}: кеш поверх резервных курсов."""
    rates = dict(DEFAULT_EXCHANGE_RATES)
    for pair, info in load_rates_cache().get("pairs", {}).items():
        rates[pair] = info["rate"]
    return rates


def get_rate(from_code, to_code):
    """Возвращает (курс, время обновления, устарел ли) с учётом TTL кеша.

    Если кеш старше TTL — пробуем обновить его через Parser Service.
    Не получилось и данных нет совсем — бросаем ApiRequestError.
    """
    from_code = validate_currency_code(from_code)
    to_code = validate_currency_code(to_code)

    cache = load_rates_cache()
    if not is_fresh(cache.get("last_refresh")):
        try:
            refresh_rates()
            cache = load_rates_cache()
        except ApiRequestError:
            pass

    rates = {pair: info["rate"] for pair, info in cache.get("pairs", {}).items()}
    rate = convert(1.0, from_code, to_code, rates)
    if rate is None:
        raise ApiRequestError(f"нет данных о курсе {from_code}→{to_code}")
    last_refresh = cache.get("last_refresh")
    return rate, last_refresh, not is_fresh(last_refresh)


def show_rates(currency=None, top=None, base=None):
    """Курсы из кеша с фильтрами: валюта, топ-N криптовалют, другая база.

    Возвращает (время обновления, список (пара, курс, обновлено, источник)).
    """
    cache = load_rates_cache()
    pairs = cache.get("pairs", {})
    if not pairs:
        raise ValueError(
            "Локальный кеш курсов пуст. Выполните 'update-rates', "
            "чтобы загрузить данные."
        )

    rows = []
    for pair, info in pairs.items():
        rows.append((pair, info["rate"], info["updated_at"], info["source"]))

    if base:
        base = validate_currency_code(base)
        if base != BASE_CURRENCY:
            base_rate = get_usd_rate(base, {p: r for p, r, _, _ in rows})
            if base_rate is None:
                raise ValueError(f"Курс для '{base}' не найден в кеше.")
            rows = [
                (f"{pair.split('_')[0]}_{base}", rate / base_rate, updated, source)
                for pair, rate, updated, source in rows
                if pair.endswith(f"_{BASE_CURRENCY}")
                and not pair.startswith(f"{base}_")
            ]

    if currency:
        code = currency.strip().upper()
        rows = [row for row in rows if code in row[0].split("_")]
        if not rows:
            raise ValueError(f"Курс для '{code}' не найден в кеше.")

    if top is not None:
        rows = [row for row in rows if is_crypto(row[0].split("_")[0])]
        rows.sort(key=lambda row: row[1], reverse=True)
        rows = rows[:top]
    else:
        rows.sort(key=lambda row: row[0])
    return cache.get("last_refresh"), rows


def get_rate_to_usd(code, rates):
    """Курс валюты к USD или ApiRequestError, если курса нет."""
    rate = get_usd_rate(code, rates)
    if rate is None:
        raise ApiRequestError(f"Не удалось получить курс для {code}→{BASE_CURRENCY}")
    return rate


# --- Портфель: отчёт, покупка, продажа ---


def portfolio_report(user, base=None):
    """Считает стоимость каждого кошелька и итог в базовой валюте."""
    base = base or settings.get("default_base_currency")
    try:
        base = validate_currency_code(base)
    except CurrencyNotFoundError:
        raise ValueError(f"Неизвестная базовая валюта '{base}'") from None

    rates = get_current_rates()
    portfolio = load_portfolio(user)
    rows = []
    for code, wallet in portfolio.wallets.items():
        rows.append((code, wallet.balance, convert(wallet.balance, code, base, rates)))
    return base, rows, portfolio.get_total_value(base, rates)


def _get_or_create_wallet(portfolio, code):
    """Возвращает кошелёк валюты, создавая его при отсутствии."""
    wallet = portfolio.get_wallet(code)
    if wallet is None:
        wallet = portfolio.add_currency(code)
    return wallet


@log_action("BUY", verbose=True)
def buy(user, currency_code, amount):
    """Покупает валюту за USD; возвращает словарь с итогами операции."""
    code = validate_currency_code(currency_code)
    if code == BASE_CURRENCY:
        raise ValueError(f"{BASE_CURRENCY} — базовая валюта, её нельзя купить")
    rate = get_rate_to_usd(code, get_current_rates())
    cost = amount * rate

    portfolio = load_portfolio(user)
    usd_wallet = _get_or_create_wallet(portfolio, BASE_CURRENCY)
    wallet = _get_or_create_wallet(portfolio, code)
    old_usd, old_balance = usd_wallet.balance, wallet.balance

    usd_wallet.withdraw(cost)
    wallet.deposit(amount)
    save_portfolio(portfolio)
    return {
        "code": code,
        "amount": amount,
        "rate": rate,
        "base": BASE_CURRENCY,
        "cost": cost,
        "old": old_balance,
        "new": wallet.balance,
        "old_usd": old_usd,
        "new_usd": usd_wallet.balance,
    }


@log_action("SELL", verbose=True)
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
    rate = get_rate_to_usd(code, get_current_rates())
    revenue = amount * rate
    usd_wallet = _get_or_create_wallet(portfolio, BASE_CURRENCY)
    old_balance, old_usd = wallet.balance, usd_wallet.balance

    wallet.withdraw(amount)
    usd_wallet.deposit(revenue)
    save_portfolio(portfolio)
    return {
        "code": code,
        "amount": amount,
        "rate": rate,
        "base": BASE_CURRENCY,
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
