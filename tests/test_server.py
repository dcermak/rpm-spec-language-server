from time import sleep
from pathlib import Path
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
from .conftest import CLIENT_SERVER_T

_HELLO_SPEC = """
Name:       hello-world
Version:    1
Release:    1
Summary:    Most simple RPM package
License:    FIXME

%description
This is my first RPM package, which does nothing.

%prep
# we have no source, so nothing here

%build
cat > hello-world.sh <<EOF
#!/usr/bin/bash
echo Hello world
EOF

%install
mkdir -p %{buildroot}/usr/bin/
install -m 755 hello-world.sh %{buildroot}/usr/bin/hello-world.sh

%files
/usr/bin/hello-world.sh

%changelog
# let's skip this for now
"""


def test_in_memory_spec_sections(
    client_server: CLIENT_SERVER_T, tmp_path: Path
) -> None:
    with open(path := str(tmp_path / "hello_world.spec"), "w") as f:
        f.write(_HELLO_SPEC)
    client, server = client_server

    client.lsp.notify(
        TEXT_DOCUMENT_DID_OPEN,
        DidOpenTextDocumentParams(
            text_document=TextDocumentItem(
                uri=(uri := f"file://{path}"),
                version=0,
                language_id="rpmspec",
                text=_HELLO_SPEC,
            )
        ),
    )

    sleep(0.5)
    assert (
        server.spec_files
        and uri in server.spec_files
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
