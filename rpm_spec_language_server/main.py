import logging


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
    parser.add_argument(
        "--runtime-type-checks",
        action="store_true",
        help="Add typeguard runtime type checking",
    )

    args = parser.parse_args()

    if args.runtime_type_checks:
        from typeguard import install_import_hook

        install_import_hook("rpm_spec_language_server")

    from rpm_spec_language_server.logging import LOG_LEVELS, LOGGER
    from rpm_spec_language_server.server import create_rpm_lang_server

    log_level = LOG_LEVELS[min(args.verbose or 0, len(LOG_LEVELS) - 1)]

    if args.log_file:
        LOGGER.removeHandler(LOGGER.handlers[0])
        LOGGER.addHandler(logging.FileHandler(args.log_file[0]))

    LOGGER.setLevel(log_level)

    server = create_rpm_lang_server()

    if args.stdio:
        server.start_io()
    else:
        server.start_tcp(args.host, args.port)
