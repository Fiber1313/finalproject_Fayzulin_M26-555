"""Планировщик периодического обновления курсов."""

import logging
import time

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.logging_config import PARSER_LOGGER

logger = logging.getLogger(PARSER_LOGGER)


class RatesScheduler:
    """Запускает RatesUpdater каждые interval секунд."""

    def __init__(self, updater, interval):
        if interval <= 0:
            raise ValueError("Интервал должен быть положительным числом секунд")
        self.updater = updater
        self.interval = interval

    def run(self, times=None):
        """Выполняет обновления times раз (None — пока не нажат Ctrl+C)."""
        done = 0
        try:
            while times is None or done < times:
                try:
                    self.updater.run_update()
                except ApiRequestError as error:
                    logger.error(f"Scheduled update failed: {error.reason}")
                done += 1
                if times is None or done < times:
                    logger.info(f"Next update in {self.interval} seconds...")
                    time.sleep(self.interval)
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
        return done
