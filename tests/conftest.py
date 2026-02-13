import json
import os
from typing import Generator

import pytest
from _pytest.fixtures import SubRequest
from lsprotocol.types import (
    EXIT,
    INITIALIZE,
    SHUTDOWN,
    ClientCapabilities,
    ClientInfo,
    InitializeParams,
)
from pygls.lsp.server import LanguageServer
from specfile.macros import Macros
from typeguard import install_import_hook

install_import_hook("rpm_spec_language_server")

# we have to import rpm_spec_language_server *after* installing the import hook
from rpm_spec_language_server.server import (  # noqa: E402
    RpmSpecLanguageServer,
    create_rpm_lang_server,
)


@pytest.fixture(scope="session", autouse=True)
def ensure_bcond_macros() -> None:
    existing = {macro.name for macro in Macros.dump()}
    if "bcond_without" not in existing:
        Macros.define("bcond_without", "%{!?with_%{1}: %global with_%{1} 0}")
    if "bcond_with" not in existing:
        Macros.define("bcond_with", "%{!?with_%{1}: %global with_%{1} 1}")


class _LocalWriter:
    def __init__(self, target_protocol):
        self._target_protocol = target_protocol

    def write(self, data: bytes) -> None:
        message = json.loads(data.decode("utf-8"))
        structured = self._target_protocol.structure_message(message)
        self._target_protocol.handle_message(structured)


class ClientServer:
    def __init__(self, client_name: str = "client"):
        self.client_name = client_name
        self.server = create_rpm_lang_server()
        self.client = LanguageServer("client", "v1")
        self._link_protocols()

    @classmethod
    def decorate(cls):
        return pytest.mark.parametrize("client_server", [cls], indirect=True)

    def start(self) -> None:
        self.initialize()

    def stop(self) -> None:
        shutdown_response = self.client.protocol.send_request(SHUTDOWN).result()
        assert shutdown_response is None
        self.client.protocol.notify(EXIT)

    def initialize(self) -> None:
        timeout = None if "DISABLE_TIMEOUT" in os.environ else 1
        response = self.client.protocol.send_request(
            INITIALIZE,
            InitializeParams(
                process_id=12345,
                root_uri="file://",
                capabilities=ClientCapabilities(),
                client_info=ClientInfo(name=self.client_name),
            ),
        ).result(timeout=timeout)
        assert response.capabilities is not None

    def _link_protocols(self) -> None:
        client_protocol = self.client.protocol
        server_protocol = self.server.protocol
        client_protocol.set_writer(_LocalWriter(server_protocol), include_headers=False)
        server_protocol.set_writer(_LocalWriter(client_protocol), include_headers=False)

    def __iter__(self) -> Generator[LanguageServer, None, None]:
        yield self.client
        yield self.server


CLIENT_SERVER_T = Generator[tuple[LanguageServer, RpmSpecLanguageServer], None, None]


@pytest.fixture
def client_server(request: SubRequest) -> CLIENT_SERVER_T:
    if (param := getattr(request, "param", None)) and isinstance(param, str):
        cs = ClientServer(client_name=param)
    else:
        cs = ClientServer()
    cs.start()

    client, server = cs
    yield client, server

    cs.stop()
