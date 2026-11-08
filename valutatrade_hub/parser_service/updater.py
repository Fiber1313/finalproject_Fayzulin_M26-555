"""RatesUpdater — опрос всех API-клиентов, объединение и сохранение курсов."""

import logging
from datetime import datetime, timezone

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.logging_config import PARSER_LOGGER
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage

logger = logging.getLogger(PARSER_LOGGER)

# Значения флага --source команды update-rates
SOURCE_ALIASES = {
    "coingecko": CoinGeckoClient,
    "exchangerate": ExchangeRateApiClient,
}


def utc_now_iso():
    """Текущее время UTC в формате 2025-10-10T12:00:00Z."""
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


class RatesUpdater:
    """Координирует обновление: клиенты → объединение → хранилище."""

    def __init__(self, clients, storage):
        self.clients = clients
        self.storage = storage

    def run_update(self):
        """Опрашивает всех клиентов; падение одного не останавливает остальных.

        Возвращает отчёт: сколько курсов записано, время обновления, ошибки.
        Если не ответил ни один источник — бросает ApiRequestError.
        """
        logger.info("Starting rates update...")
        timestamp = utc_now_iso()
        pairs = {}
        history = []
        errors = []

        for client in self.clients:
            name = client.source_name
            try:
                rates = client.fetch_rates()
            except ApiRequestError as error:
                errors.append(str(error))
                reason = error.reason.removeprefix(f"{name}: ")
                logger.error(f"Failed to fetch from {name}: {reason}")
                continue
            logger.info(f"Fetching from {name}... OK ({len(rates)} rates)")
            for pair, rate in rates.items():
                pairs[pair] = {"rate": rate, "updated_at": timestamp, "source": name}
                history.append(self._make_record(pair, rate, timestamp, client))

        if not pairs:
            raise ApiRequestError("не удалось получить курсы ни из одного источника")

        logger.info(f"Writing {len(pairs)} rates to {self.storage.rates_path}...")
        self.storage.save_snapshot(pairs, timestamp)
        self.storage.append_history(history)
        return {"total": len(pairs), "last_refresh": timestamp, "errors": errors}

    @staticmethod
    def _make_record(pair, rate, timestamp, client):
        """Запись истории: id = <FROM>_<TO>_<время>, плюс метаданные запроса."""
        from_code, to_code = pair.split("_")
        meta = dict(client.last_meta)
        raw_ids = meta.pop("raw_ids", {})
        if from_code in raw_ids:
            meta["raw_id"] = raw_ids[from_code]
        return {
            "id": f"{pair}_{timestamp}",
            "from_currency": from_code,
            "to_currency": to_code,
            "rate": rate,
            "timestamp": timestamp,
            "source": client.source_name,
            "meta": meta,
        }


def build_updater(source=None):
    """Создаёт RatesUpdater со всеми клиентами или только с одним (source)."""
    config = ParserConfig()
    if source is None:
        client_classes = list(SOURCE_ALIASES.values())
    else:
        client_class = SOURCE_ALIASES.get(source.lower())
        if client_class is None:
            raise ValueError(
                f"Неизвестный источник '{source}'. "
                f"Доступны: {', '.join(SOURCE_ALIASES)}"
            )
        client_classes = [client_class]
    clients = [client_class(config) for client_class in client_classes]
    return RatesUpdater(clients, RatesStorage(config))
