# ValutaTrade Hub

Консольная платформа для отслеживания и симуляции торговли фиатными валютами
и криптовалютами. Пользователь регистрируется, получает стартовый баланс
10 000 USD, покупает и продаёт валюты в виртуальном портфеле и смотрит
актуальные курсы, которые загружаются из публичных API.

Итоговый проект курса «Программирование на Python», МИФИ.

Система состоит из двух частей:

- **Core Service** — пользователи, портфели, сделки, командный интерфейс (CLI);
- **Parser Service** — загрузка курсов из CoinGecko (криптовалюты)
  и ExchangeRate-API (фиатные валюты), кеш и история курсов.

## Структура проекта

```
finalproject_Fayzulin_M26-555/
├── data/
│   ├── users.json            # пользователи (хеш пароля + соль)
│   ├── portfolios.json       # портфели и кошельки
│   ├── rates.json            # кеш последних курсов для Core Service
│   └── exchange_rates.json   # история всех замеров курсов
├── valutatrade_hub/
│   ├── logging_config.py     # настройка логов (формат, ротация)
│   ├── decorators.py         # @log_action
│   ├── core/
│   │   ├── currencies.py     # Currency, FiatCurrency, CryptoCurrency, реестр
│   │   ├── exceptions.py     # пользовательские исключения
│   │   ├── models.py         # User, Wallet, Portfolio
│   │   ├── usecases.py       # бизнес-логика
│   │   └── utils.py          # валидация, форматирование, конвертация
│   ├── infra/
│   │   ├── settings.py       # SettingsLoader (Singleton)
│   │   └── database.py       # DatabaseManager (Singleton)
│   ├── parser_service/
│   │   ├── config.py         # ParserConfig: API, валюты, пути, таймауты
│   │   ├── api_clients.py    # BaseApiClient, CoinGeckoClient, ExchangeRateApiClient
│   │   ├── updater.py        # RatesUpdater
│   │   ├── storage.py        # запись rates.json и exchange_rates.json
│   │   └── scheduler.py      # периодическое обновление
│   └── cli/
│       └── interface.py      # команды
├── main.py
├── Makefile
├── pyproject.toml
└── uv.lock
```

## Установка

Нужны Python 3.12+ и [uv](https://docs.astral.sh/uv/).

```bash
uv sync          # или: make install
```

## Запуск

```bash
uv run project   # или: make project, или: python main.py
```

Откроется интерактивный режим с приглашением `valuta> `.

Другие команды Makefile: `make build` (сборка пакета), `make publish`
(сборка и проверка метаданных через twine), `make package-install`
(установка собранного пакета), `make lint` (проверка Ruff).

## Команды

| Команда | Описание |
|---|---|
| `register --username <имя> --password <пароль>` | регистрация (пароль от 4 символов) |
| `login --username <имя> --password <пароль>` | вход |
| `logout` | выход из аккаунта |
| `show-portfolio [--base <валюта>]` | кошельки и итоговая стоимость |
| `buy --currency <код> --amount <количество>` | купить валюту за USD |
| `sell --currency <код> --amount <количество>` | продать валюту, выручка в USD |
| `get-rate --from <код> --to <код>` | курс одной валюты к другой |
| `list-currencies` | поддерживаемые валюты |
| `update-rates [--source coingecko\|exchangerate]` | обновить курсы из API |
| `show-rates [--currency <код>] [--top <N>] [--base <код>]` | курсы из кеша |
| `schedule-updates [--interval <сек>] [--times <N>]` | автообновление курсов |
| `help`, `exit` | справка, выход |

Поддерживаемые валюты: фиатные `USD`, `EUR`, `GBP`, `RUB`, `CNY`;
криптовалюты `BTC`, `ETH`, `SOL`, `TON`.

### Пример сессии

```
valuta> register --username emperor --password 1234
Пользователь 'emperor' зарегистрирован (id=1). Войдите: login --username emperor --password ****
valuta> login --username emperor --password 1234
Вы вошли как 'emperor'
valuta> buy --currency BTC --amount 0.05
Покупка выполнена: 0.0500 BTC по курсу 75960.00 USD/BTC
Изменения в портфеле:
- BTC: было 0.0000 → стало 0.0500
- USD: было 10000.00 → стало 6202.00
Оценочная стоимость покупки: 3,798.00 USD
valuta> sell --currency BTC --amount 0.01
Продажа выполнена: 0.0100 BTC по курсу 75960.00 USD/BTC
Изменения в портфеле:
- BTC: было 0.0500 → стало 0.0400
- USD: было 6202.00 → стало 6961.60
Оценочная выручка: 759.60 USD
valuta> show-portfolio
Портфель пользователя 'emperor' (база: USD):
- USD: 6961.60  → 6,961.60 USD
- BTC: 0.0400  → 3,038.40 USD
---------------------------------
ИТОГО: 10,000.00 USD
valuta> get-rate --from USD --to RUB
Курс USD→RUB: 81.7445 (обновлено: 2026-11-08 14:54:19)
Обратный курс RUB→USD: 0.01223324
```

### Обработка ошибок

```
valuta> sell --currency BTC --amount 1
Недостаточно средств: доступно 0.0400 BTC, требуется 1.0000 BTC
valuta> buy --currency XYZ --amount 1
Неизвестная валюта 'XYZ'
Поддерживаемые валюты: USD, EUR, GBP, RUB, CNY, BTC, ETH, SOL, TON
valuta> buy --currency BTC --amount -5
'amount' должен быть положительным числом
```

## Parser Service и ключ API

Криптовалюты загружаются из [CoinGecko](https://www.coingecko.com/en/api)
без ключа. Для фиатных валют нужен бесплатный ключ
[ExchangeRate-API](https://www.exchangerate-api.com/).

Ключ **не хранится в коде**. Задайте его одним из способов:

- файл `.env` в корне проекта (он в `.gitignore`):

  ```
  EXCHANGERATE_API_KEY=ваш_ключ
  ```

- или переменная окружения `EXCHANGERATE_API_KEY`.

Обновление курсов:

```
valuta> update-rates
INFO: Starting rates update...
INFO: Fetching from CoinGecko... OK (4 rates)
INFO: Fetching from ExchangeRate-API... OK (5 rates)
INFO: Writing 9 rates to data/rates.json...
Update successful. Total rates updated: 9. Last refresh: 2026-11-08T14:54:19Z
```

Если один источник недоступен, данные второго всё равно сохраняются,
а ошибка пишется в `logs/parser.log`.

## Кеш и TTL курсов

- `data/rates.json` — снимок последних курсов: для каждой пары
  (`BTC_USD`, `EUR_USD`, ...) хранятся курс, время обновления и источник.
  Пара `RUB_USD = 0.0122` означает «1 рубль = 0.0122 доллара»;
  для удобства хранится и обратная пара `USD_RUB`.
- `data/exchange_rates.json` — история всех замеров с уникальным
  `id = <FROM>_<TO>_<время>`.
- Запись файлов атомарная: временный файл → переименование.
- Срок свежести кеша (TTL) — 300 секунд. Если кеш устарел, `get-rate`
  пытается обновить курсы через Parser Service; если это не удалось,
  программа сообщает, что данные устарели, и предлагает `update-rates`.

## Конфигурация

Настройки Core Service — в `pyproject.toml`, секция `[tool.valutatrade]`
(пути к файлам, TTL курсов, базовая валюта, стартовый баланс, логи).
Их читает `SettingsLoader` — Singleton, реализованный через `__new__`.

Настройки Parser Service (адреса API, списки валют, таймаут, пути) —
в `valutatrade_hub/parser_service/config.py` (`ParserConfig`).

## Логи

- `logs/actions.log` — операции `REGISTER`, `LOGIN`, `BUY`, `SELL`
  (декоратор `@log_action`);
- `logs/parser.log` — шаги обновления курсов.

Формат — строка, ротация по 1 МБ (3 архивных файла). Пример:

```
INFO 2026-11-08T17:36:55 BUY user='emperor' currency='BTC' amount=0.0500 rate=75960.00 base='USD' balance=0.0000->0.0500 result=OK
```
