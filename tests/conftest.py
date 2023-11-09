import asyncio
import os
import threading
from typing import Generator
from lsprotocol.types import (
    EXIT,
    INITIALIZE,
    SHUTDOWN,
    ClientCapabilities,
    InitializeParams,
)
from pygls.server import LanguageServer
import pytest

from rpm_spec_language_server.server import (
    RpmSpecLanguageServer,
    create_rpm_lang_server,
)


class ClientServer:
    # shamelessly stolen from
    # https://github.com/openlawlibrary/pygls/blob/8f601029dcf3c7c91be7bf2d86a841a1598ce1f0/tests/ls_setup.py#L109

    def __init__(self):
        # Client to Server pipe
        csr, csw = os.pipe()
        # Server to client pipe
        scr, scw = os.pipe()

        # Setup Server
        self.server = create_rpm_lang_server()
        self.server_thread = threading.Thread(
            name="Server Thread",
            target=self.server.start_io,
            args=(os.fdopen(csr, "rb"), os.fdopen(scw, "wb")),
        )
        self.server_thread.daemon = True

        # Setup client
        self.client = LanguageServer("client", "v1", asyncio.new_event_loop())
        self.client_thread = threading.Thread(
            name="Client Thread",
            target=self.client.start_io,
            args=(os.fdopen(scr, "rb"), os.fdopen(csw, "wb")),
        )
        self.client_thread.daemon = True

    @classmethod
    def decorate(cls):
        return pytest.mark.parametrize("client_server", [cls], indirect=True)

    def start(self) -> None:
        self.server_thread.start()
        self.server.thread_id = self.server_thread.ident
        self.client_thread.start()
        self.initialize()

    def stop(self) -> None:
        shutdown_response = self.client.lsp.send_request(SHUTDOWN).result()
        assert shutdown_response is None
        self.client.lsp.notify(EXIT)
        self.server_thread.join()
        self.client._stop_event.set()
        try:
            self.client.loop._signal_handlers.clear()  # HACK ?
        except AttributeError:
            pass
        self.client_thread.join()

    # @retry_stalled_init_fix_hack()
    def initialize(self) -> None:
        timeout = None if "DISABLE_TIMEOUT" in os.environ else 1
        response = self.client.lsp.send_request(
            INITIALIZE,
            InitializeParams(
                process_id=12345, root_uri="file://", capabilities=ClientCapabilities()
            ),
        ).result(timeout=timeout)
        assert response.capabilities is not None

    def __iter__(self) -> Generator[LanguageServer, None, None]:
        yield self.client
        yield self.server


CLIENT_SERVER_T = Generator[tuple[LanguageServer, RpmSpecLanguageServer], None, None]


@pytest.fixture
def client_server() -> CLIENT_SERVER_T:
    cs = ClientServer()
    cs.start()

    client, server = cs
    yield client, server

    cs.stop()
