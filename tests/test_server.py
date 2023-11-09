from time import sleep
from lsprotocol.types import (
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_CLOSE,
    TEXT_DOCUMENT_DID_OPEN,
    DidChangeTextDocumentParams,
    DidCloseTextDocumentParams,
    DidOpenTextDocumentParams,
    TextDocumentContentChangeEvent_Type2,
    TextDocumentIdentifier,
    TextDocumentItem,
    VersionedTextDocumentIdentifier,
)
from pygls.server import LanguageServer
from .conftest import CLIENT_SERVER_T


_HELLO_SPEC = """Name:       hello-world
Version:    1
Release:    1
Summary:    Most simple RPM package
License:    FIXME

%description
This is my first RPM package, which does nothing.

%global script hello-world.sh
%define dest %{_bindir}/%script
%prep
# we have no source, so nothing here

%build
cat > %script <<EOF
#!/usr/bin/bash
echo Hello world from package %{name}-%{version}
EOF

%install
mkdir -p %{buildroot}%{_bindir}
install -m 755 hello-world.sh %{buildroot}%{dest}

%files
/usr/bin/hello-world.sh

%changelog
# let's skip this for now
"""


def open_spec_file(client: LanguageServer, path: str, file_contents: str) -> None:
    client.lsp.notify(
        TEXT_DOCUMENT_DID_OPEN,
        DidOpenTextDocumentParams(
            text_document=TextDocumentItem(
                uri=f"file://{path}",
                version=0,
                language_id="rpmspec",
                text=file_contents,
            )
        ),
    )


def test_in_memory_spec_sections(client_server: CLIENT_SERVER_T) -> None:
    client, server = client_server
    open_spec_file(client, (path := "/home/me/specs/hello_world.spec"), _HELLO_SPEC)
    sleep(0.5)

    assert (
        server.spec_files
        and (uri := f"file://{path}") in server.spec_files
        and str(server.spec_files[uri].spec) == _HELLO_SPEC
    )

    client.lsp.notify(
        TEXT_DOCUMENT_DID_CHANGE,
        DidChangeTextDocumentParams(
            text_document=VersionedTextDocumentIdentifier(version=1, uri=uri),
            content_changes=[
                TextDocumentContentChangeEvent_Type2(
                    text=(
                        new_content := "\n".join(
                            (lines := _HELLO_SPEC.splitlines())[:7]
                            + [""] * 3
                            + lines[7:]
                        )
                        + "\n"  # trailing newline to mimic the behavior of Specfile.__str__()
                    )
                )
            ],
        ),
    )
    sleep(0.5)

    assert str(server.spec_files[uri].spec) == new_content

    client.lsp.notify(
        TEXT_DOCUMENT_DID_CLOSE,
        DidCloseTextDocumentParams(text_document=TextDocumentIdentifier(uri=uri)),
    )
    sleep(0.5)

    assert uri not in server.spec_files
