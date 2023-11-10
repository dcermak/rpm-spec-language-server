import re
from time import sleep
from typing import Callable
from lsprotocol.types import (
    TEXT_DOCUMENT_COMPLETION,
    TEXT_DOCUMENT_DEFINITION,
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_CLOSE,
    TEXT_DOCUMENT_DID_OPEN,
    CompletionContext,
    CompletionList,
    CompletionParams,
    CompletionTriggerKind,
    DefinitionParams,
    DidChangeTextDocumentParams,
    DidCloseTextDocumentParams,
    DidOpenTextDocumentParams,
    Location,
    Position,
    Range,
    TextDocumentContentChangeEvent_Type2,
    TextDocumentIdentifier,
    TextDocumentItem,
    VersionedTextDocumentIdentifier,
)
from pygls.server import LanguageServer
import pytest
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

%undefined_macro

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


_RPM_MACROS_FILE = "/usr/lib/rpm/macros"
# dirty, dirty…
# but sadly we don't know exactly where %_bindir is defined in
# /usr/lib/rpm/macros so we have to find out at runtime :-(
with open(_RPM_MACROS_FILE, "r") as macros_file:
    lines = macros_file.readlines()
    bindir_define_line = -1
    bindir_match_length = 0
    for i, line in enumerate(lines):
        if line.startswith("%_bindir"):
            bindir_define_line = i
            bindir_match_length = re.match(r"%_bindir([\t \f]+)(\S+)", line).end()
            break

assert bindir_define_line > 0, f"Could not find %_bindir in {_RPM_MACROS_FILE}"


@pytest.mark.parametrize(
    "cursor_position,expected_ranges,defined_in_uri",
    [
        (
            # position on %{name}
            Position(line=17, character=34),
            [Range(start=Position(0, 0), end=Position(0, 23))],
            None,
        ),
        (
            # position on %{version}
            Position(line=17, character=44),
            [Range(start=Position(1, 0), end=Position(1, 13))],
            None,
        ),
        (
            # position of %dest in %install
            Position(line=22, character=46),
            [Range(start=Position(10, 0), end=Position(10, 12))],
            None,
        ),
        (
            # position of %script in %build
            Position(line=15, character=9),
            [Range(start=Position(9, 0), end=Position(9, 14))],
            None,
        ),
        # %undefined_macro
        (Position(line=24, character=10), None, None),
        (
            Position(line=21, character=27),
            [
                Range(
                    start=Position(bindir_define_line, 0),
                    end=Position(bindir_define_line, bindir_match_length),
                )
            ],
            f"file://{_RPM_MACROS_FILE}",
        ),
    ],
)
def test_jump_to_definition(
    client_server: CLIENT_SERVER_T,
    cursor_position: Position,
    expected_ranges: list[Range] | None,
    defined_in_uri: str | None,
) -> None:
    client, _ = client_server
    open_spec_file(client, (path := "/home/me/specs/hello_world.spec"), _HELLO_SPEC)
    sleep(0.5)

    resp = client.lsp.send_request(
        TEXT_DOCUMENT_DEFINITION,
        DefinitionParams(
            text_document=TextDocumentIdentifier(uri=(uri := f"file://{path}")),
            position=cursor_position,
        ),
    ).result()

    assert resp == (
        [Location(uri=defined_in_uri or uri, range=r) for r in expected_ranges]
        if expected_ranges
        else None
    )

    # insert two newlines at the beginning of the spec and repeat the
    # gotoDefinition request with the positions two lines below => should get
    # results shifted by exactly two lines
    client.lsp.notify(
        TEXT_DOCUMENT_DID_CHANGE,
        DidChangeTextDocumentParams(
            text_document=VersionedTextDocumentIdentifier(version=1, uri=uri),
            content_changes=[
                TextDocumentContentChangeEvent_Type2(text="\n\n" + _HELLO_SPEC)
            ],
        ),
    )
    sleep(0.5)

    def two_lines_below(pos: Position) -> Position:
        return Position(line=pos.line + 2, character=pos.character)

    resp = client.lsp.send_request(
        TEXT_DOCUMENT_DEFINITION,
        DefinitionParams(
            text_document=TextDocumentIdentifier(uri=(uri := f"file://{path}")),
            position=two_lines_below(cursor_position),
        ),
    ).result()

    # we edited that file but if the macro comes from a different file, then the
    # destination will not change
    if defined_in_uri:
        assert expected_ranges
        assert resp == [
            Location(uri=defined_in_uri or uri, range=r) for r in expected_ranges
        ]
    else:
        assert resp == (
            [
                Location(
                    uri=uri,
                    range=Range(
                        start=two_lines_below(r.start), end=two_lines_below(r.end)
                    ),
                )
                for r in expected_ranges
            ]
            if expected_ranges
            else None
        )


def _check_only_macros_completed(completion_list: CompletionList) -> None:
    assert not any(not item.label.startswith("%") for item in completion_list.items)


def _check_only_preamble_items(completion_list: CompletionList) -> None:
    assert all(
        item.label[0].isupper() and not item.label.startswith("%")
        for item in completion_list.items
    )


def _keyword_in_completion_list(keyword: str, completion_list: CompletionList) -> bool:
    return any(item.label == keyword for item in completion_list.items)


def _check_everything_completed(completion_list: CompletionList) -> None:
    assert all(
        item.label[0].isupper() or item.label.startswith("%")
        for item in completion_list.items
    ) and _keyword_in_completion_list("BuildRequires", completion_list)


def _check_probably_only_macros(completion_list: CompletionList) -> None:
    assert all(not item.label.startswith("%") for item in completion_list.items)
    assert not _keyword_in_completion_list("BuildRequires", completion_list)
    assert _keyword_in_completion_list("prep", completion_list)


@pytest.mark.parametrize(
    "position,checker,ctx",
    [
        (Position(line=19, character=0), _check_only_macros_completed, None),
        (
            Position(0, 0),
            _check_only_preamble_items,
            CompletionContext(
                trigger_character="B",
                trigger_kind=CompletionTriggerKind.TriggerCharacter,
            ),
        ),
        (Position(0, 0), _check_everything_completed, None),
        (
            Position(0, 0),
            _check_probably_only_macros,
            CompletionContext(
                trigger_character="%",
                trigger_kind=CompletionTriggerKind.TriggerCharacter,
            ),
        ),
    ],
)
def test_autocomplete(
    client_server: CLIENT_SERVER_T,
    position: Position,
    checker: Callable[[CompletionList], None],
    ctx: CompletionContext | None,
) -> None:
    client, _ = client_server
    open_spec_file(client, (path := "/home/me/specs/hello_world.spec"), _HELLO_SPEC)
    sleep(0.5)

    resp = client.lsp.send_request(
        TEXT_DOCUMENT_COMPLETION,
        CompletionParams(
            text_document=TextDocumentIdentifier(uri=(uri := f"file://{path}")),
            position=position,
            context=ctx,
        ),
    ).result()

    assert isinstance(resp, CompletionList) and not resp.is_incomplete

    checker(resp)
