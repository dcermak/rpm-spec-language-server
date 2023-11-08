import logging
from rpm_spec_language_server.server import create_rpm_lang_server

logging.basicConfig(format="%(levelname)s:%(funcName)s:%(message)s", level=logging.INFO)
log = logging.getLogger()

_LOG_LEVELS = [
    logging.WARNING,
    logging.INFO,
    logging.DEBUG,
]


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        help="Set the logging verbosity, defaults to warning",
    )
    parser.add_argument("--log_file", type=str, help="File to log in", nargs=1)
    parser.add_argument(
        "--stdio", action="store_true", help="Use stdio instead of the TCP server"
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Bind to this address"
    )
    parser.add_argument("--port", type=int, default=2087, help="Bind to this port")

    args = parser.parse_args()

    log_level = _LOG_LEVELS[min(args.verbose or 0, len(_LOG_LEVELS) - 1)]

    if args.log_file:
        log.removeHandler(log.handlers[0])
        log.addHandler(logging.FileHandler(args.log_file))

    log.setLevel(log_level)

    server = create_rpm_lang_server()

    if args.stdio:
        server.start_io()
    else:
        server.start_tcp(args.host, args.port)
