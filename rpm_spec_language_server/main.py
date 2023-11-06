from rpm_spec_language_server.server import create_rpm_lang_server


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tcp", action="store_true", help="Use TCP server instead of stdio"
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Bind to this address"
    )
    parser.add_argument("--port", type=int, default=2087, help="Bind to this port")

    args = parser.parse_args()

    server = create_rpm_lang_server()

    if args.tcp:
        server.start_tcp(args.host, args.port)
    else:
        server.start_io()
