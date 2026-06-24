"""This is the main entrypoint into the RPM spec language server, it provides
its CLI interface.

The default running mode is not in container mode, which is pretty much what
you'd expect: we collect the CLI arguments and launch the language server in the
requested mode (TCP or stdio).

The other running mode is container-mode. This is a hack/workaround for rpm
being pretty much tied to the OS you're running, which means that you cannot
really expand macros for a different distribution. To work around this, we
package the language server into container images of various popular RPM based
distributions and launch it in TCP mode.

Container mode requires various workarounds:

1. The container runtime (namely rootless podman) will open ports for
   communication way before the container is up and running. This causes a
   rather ugly problem: the editor sends an initialization request once the port
   is open and expects a reply. However, in container mode, the port is already
   open, but the language server in the container is not yet ready and the
   initial request is lost, causing the editor to wait indefinitely.

   We work around this by launching the container, waiting for it to be up and
   running and afterwards, we setup a port forward from the requested port into
   the container.

2. Jump to macro definitions cannot work in a straightforward way in the
   container: the macros are defined in files in the container, which are
   probably not existing on the host or are different.

   Unfortunately we cannot mount a container directory on the host
   (easily). Therefore we have another hack: the language server will copy the
   contents of :file:`/usr/lib/rpm` into :py:const:`_MACROS_COPY_DIR` if it
   exists. :py:const:`_MACROS_COPY_DIR` is a bind-mount to a temporary directory
   on the host and the language server in the container will then remap the
   found macro file with the temporary directory on the host. This should allow
   the editor to still find the macro definitions.

3. Currently you can only have one project open, as the language server bind
   mounts cwd into :file:`/src/` in the container. The language server expects
   all files to be there.

   We might be able to work around this in the future by relying exclusively on
   the in-memory representation or have a side-channel between container and the
   process running on the host to read arbitrary files.

"""

import asyncio
import logging
import socket
import sys
from os import getpid
from typing import NoReturn, Tuple

_DEFAULT_PORT = 2087
_MACROS_COPY_DIR = "/rpmmacros/"


async def _forward_data(
    loop: asyncio.AbstractEventLoop,
    receiving_socket: socket.socket,
    sending_socket: socket.socket,
) -> NoReturn:
    """Reads data from the ``receiving_socket`` and sends them to
    ``sending_socket`` in an endless loop.

    """
    while True:
        data, _ = await loop.sock_recvfrom(receiving_socket, 1024)
        await loop.sock_sendall(sending_socket, data)


async def _create_forwarder(lsp_port: int, ctr_addr: str, ctr_port: int) -> NoReturn:
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
            _forward_data(loop, client_sock, ctr_sock),
            _forward_data(loop, ctr_sock, client_sock),
        )


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

        # Communicating via stdio does not work in container mode, as we face
        # the same caching issue as with TCP mode. I.e. we'd require a second
        # forwarding implementation akin to the TCP port
        # forwarder. Additionally, --stdio has weird glitches in container mode,
        # where it needs to be ctrl-c'd twice to die. This causes problems for
        # editors to properly terminate the language server.
        if args.stdio:
            raise ValueError("Container mode does not support stdio")

        # typeguard is not installed in the container images
        if args.runtime_type_checks:
            raise ValueError("Container mode does not support runtime-type-checks")

        # we need the logs for our poor man's healthcheck and we don't really
        # want to have _another_ mount to pull the logs out of the container
        if args.log_file:
            raise ValueError(
                "Log files not supported in container mode, "
                "use $ctr_runtime logs $ctr_id"
            )

        with tempfile.TemporaryDirectory() as tmp_dir:
            _ctr_mount_path = "/src/"

            launch_args: Tuple[str, ...] = (
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

            if args.verbose:
                # forward verbosity arguments, but require at least INFO logging
                # level so that our poor man's healthcheck works
                launch_args += ("-" + ("v" * max(args.verbose, 1)),)

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
                # read the logs from the container
                log_output = (
                    subprocess.check_output(
                        (ctr_runtime, "logs", ctr_id), stderr=subprocess.STDOUT
                    )
                    .decode()
                    .strip()
                )

                # the server is up and running if the last line is:
                # INFO:start_tcp:Starting TCP server on 127.0.0.1:2087
                if (
                    log_lines := log_output.splitlines()
                ) and "INFO:start_tcp:Starting TCP server on" in log_lines[-1]:
                    break

                sleep(1)

            try:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(_create_forwarder(args.port, addr, int(port)))
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

    # if we're running in the container, then we need to add a signal handler
    # for SIGTERM, otherwise the container will not terminate cleanly on SIGTERM
    # and wait until SIGKILL
    # see: https://stackoverflow.com/a/62871549
    if getpid() == 1:
        from signal import SIGTERM, signal

        def terminate(signal, frame):
            sys.exit(0)

        signal(SIGTERM, terminate)

    if args.stdio:
        server.start_io()
    else:
        server.start_tcp(args.host, args.port)
