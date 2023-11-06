import logging
from rpm_spec_language_server.server import create_rpm_lang_server

logging.basicConfig(format='%(levelname)s:%(funcName)s:%(message)s',
                    level=logging.INFO)
log = logging.getLogger()

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verbose", action="count", help="Verbose logging"
    )
    parser.add_argument(
        "--log_file", type=str, help="File to log in"
    )
    parser.add_argument(
        "--tcp", action="store_true", help="Use TCP server instead of stdio"
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Bind to this address"
    )
    parser.add_argument("--port", type=int, default=2087, help="Bind to this port")

    args = parser.parse_args()

    if args.log_file:
        args.verbose = 1 if args.verbose <= 1 else args.verbose
        log.removeHandler(log.handlers[0])
        log.addHandler(logging.FileHandler(args.log_file))

    if args.verbose > 0:
       log.setLevel = logging.DEBUG

    server = create_rpm_lang_server()

    if args.tcp:
        server.start_tcp(args.host, args.port)
    else:
        server.start_io()
