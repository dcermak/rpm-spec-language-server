import logging

logging.basicConfig(
    format="%(levelname)s:%(funcName)s:%(message)s", level=logging.WARNING
)

LOGGER = logging.getLogger()

LOG_LEVELS = [
    logging.WARNING,
    logging.INFO,
    logging.DEBUG,
]
