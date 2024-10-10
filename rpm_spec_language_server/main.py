import asyncio
import logging
import socket
import socketserver
import sys
from typing import NoReturn, Tuple

_DEFAULT_PORT = 2087
_MACROS_COPY_DIR = "/rpmmacros/"


class PortForwardingHandler(socketserver.BaseRequestHandler):
    _forward_to: Tuple[str, int]

    def handle(self):
        self.forward_connection(self._forward_to)

    def forward_connection(self, forward_to: Tuple[str, int]) -> None:
        sock = self.request
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        forward_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        forward_sock.connect(forward_to)

        while True:
            data = sock.recv(1024)
            print(data, file=sys.stderr)
            if not data:
                break
            forward_sock.sendall(data)


async def forward_data(
    loop: asyncio.AbstractEventLoop,
    receiving_socket: socket.socket,
    sending_socket: socket.socket,
) -> NoReturn:
    while True:
        data, _ = await loop.sock_recvfrom(receiving_socket, 1024)
        await loop.sock_sendall(sending_socket, data)


async def create_forwarder(lsp_port: int, ctr_addr: str, ctr_port: int) -> NoReturn:
    loop = asyncio.get_event_loop()

    lsp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lsp_sock.bind(("", lsp_port))
    lsp_sock.listen(8)
    lsp_sock.setblocking(False)

    while True:
        client_sock, _ = await loop.sock_accept(lsp_sock)

        ctr_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ctr_sock.setblocking(False)

        await loop.sock_connect(ctr_sock, (ctr_addr, ctr_port))

        await asyncio.gather(
            forward_data(loop, client_sock, ctr_sock),
            forward_data(loop, ctr_sock, client_sock),
        )


def forward(source, destination):
    data = ""
    while data:
        data = source.recv(1024)
        if data:
            destination.sendall(data)
        else:
            source.shutdown(socket.SHUT_RD)
            destination.shutdown(socket.SHUT_WR)


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
    parser.add_argument(
        "--port", type=int, default=_DEFAULT_PORT, help="Bind to this port"
    )
    parser.add_argument(
        "--runtime-type-checks",
        action="store_true",
        help="Add typeguard runtime type checking",
    )

    parser.add_argument(
        "--container-mode",
        action="store_true",
        help="Run the language server in a container",
    )
    parser.add_argument(
        "--distribution",
        type=str,
        nargs=1,
        choices=["fedora", "centos", "tumbleweed", "leap-15.6", "leap-15.5"],
        help="The distribution to use for container-mode",
    )
    parser.add_argument(
        "--container-runtime",
        type=str,
        nargs=1,
        choices=["docker", "podman"],
        help="The container runtime to use in container-mode",
    )
    parser.add_argument(
        "--container-image",
        type=str,
        nargs=1,
        help=(
            "The container image to use to run the language server in (the "
            " server MUST be pre-installed)"
        ),
        default=["ghcr.io/dcermak/rpm-spec-language-server"],
    )
    parser.add_argument(
        "--ctr-mount-path",
        type=str,
        nargs=1,
        help=(
            "Directory in on the container where the directory with the spec is "
            "mounted into the container (internal flag)"
        ),
        default=[""],
    )
    parser.add_argument(
        "--ctr-macros-mount-path",
        type=str,
        nargs=1,
        help=(
            "Path where the rpm macros directory from the container is mounted "
            " on the host (internal flag)"
        ),
        default=[None],
    )

    args = parser.parse_args()

    if args.container_mode:
        import subprocess
        import tempfile
        from time import sleep

        with tempfile.TemporaryDirectory() as tmp_dir:
            _ctr_mount_path = "/src/"

            launch_args = (
                (ctr_runtime := args.container_runtime[0]),
                "run",
                "--rm",
                "-d",
                # mount the cwd
                "-v",
                f".:{_ctr_mount_path}:z",
                # mount the directory where the container copies the contents of
                # /usr/lib/rpm/
                "-v",
                f"{tmp_dir}:{_MACROS_COPY_DIR}:z",
                # expose the TCP port
                "-p",
                (private_port := f"{_DEFAULT_PORT}/tcp"),
                # container image
                f"{args.container_image[0]}:{args.distribution[0]}",
                # pass the macros path as
                f"--ctr-macros-mount-path={tmp_dir}",
            )

            # FIXME: what to do with logfiles?

            # if not args.stdio:
            # launch_args += ()

            # typeguard is not in the container!
            # if args.runtime_type_checks:
            #     launch_args += ("--runtime-type-checks",)

            # if args.stdio:
            #     launch_args += ("--stdio",)

            if args.verbose:
                launch_args += ("-" + ("v" * args.verbose),)

            launch_res = subprocess.check_output(launch_args)
            ctr_id = launch_res.decode("utf-8").strip().splitlines()[-1]

            # run $ctr port $id 2087/tcp
            # returns:
            # 0.0.0.0:32768
            # [::]:32768
            #
            # take first entry => split by rightmost :
            addr, _, port = (
                subprocess.check_output((ctr_runtime, "port", ctr_id, private_port))
                .decode()
                .strip()
                .splitlines()[0]
                .rpartition(":")
            )

            # poor man's healthcheck: wait for the container to be up and running
            while True:
                log_output = (
                    subprocess.check_output(
                        (ctr_runtime, "logs", ctr_id), stderr=subprocess.STDOUT
                    )
                    .decode()
                    .strip()
                )

                if (
                    log_lines := log_output.splitlines()
                ) and "INFO:start_tcp:Starting TCP server on" in log_lines[-1]:
                    break

                sleep(1)

            # import _thread

            try:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(create_forwarder(args.port, addr, int(port)))

            # PortForwardingHandler._forward_to = (addr, int(port))

            # server = socketserver.TCPServer(("", args.port), PortForwardingHandler)

            # try:
            #     server.serve_forever()
            finally:
                subprocess.run((ctr_runtime, "rm", "-f", ctr_id))

            return

    if args.runtime_type_checks:
        from typeguard import install_import_hook

        install_import_hook("rpm_spec_language_server")

    import os.path

    from rpm_spec_language_server.logging import LOG_LEVELS, LOGGER
    from rpm_spec_language_server.server import create_rpm_lang_server

    log_level = LOG_LEVELS[min(args.verbose or 0, len(LOG_LEVELS) - 1)]

    if args.log_file:
        LOGGER.removeHandler(LOGGER.handlers[0])
        LOGGER.addHandler(logging.FileHandler(args.log_file[0]))

    LOGGER.setLevel(log_level)

    if args.ctr_macros_mount_path[0] and os.path.exists(_MACROS_COPY_DIR):
        import shutil

        shutil.copytree(
            "/usr/lib/rpm/",
            os.path.join(_MACROS_COPY_DIR, "usr/lib/rpm"),
            # need to ignore dangling symlinks as some scripts are symlinked
            # into /usr/lib/rpm/ from directories outside of that
            ignore_dangling_symlinks=True,
        )

    server = create_rpm_lang_server(
        args.ctr_mount_path[0], args.ctr_macros_mount_path[0]
    )

    if args.stdio:
        server.start_io()
    else:
        server.start_tcp(args.host, args.port)
