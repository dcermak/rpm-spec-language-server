from pathlib import Path
from typing import Optional
from urllib.parse import quote

import pytest
from lsprotocol.types import Position, TextDocumentIdentifier
from rpm_spec_language_server.macros import (
    get_macro_string_at_position,
)
from rpm_spec_language_server.server import create_rpm_lang_server
from rpm_spec_language_server.util import parse_macros
from specfile.macros import Macro, MacroLevel
from specfile.specfile import Specfile

from tests.data import NOTMUCH_SPEC


@pytest.mark.parametrize(
    "line,character,macro_string",
    [
        ("Version: %{epoch}:%{version}", 13, "epoch"),
        ("Version: %{epoch}:%{version}", 22, "version"),
        ("Version: %{epoch}:%{version}", 3, None),
        ("%%deactivated", 5, None),
        ("mkdir -p %{buildroot}%{site_lisp}", 27, "site_lisp"),
        ("echo 'foo' %dnl %{buildroot}", 24, None),
        ("%if %{?suse_version}", 7, "suse_version"),
        ("%if %{!?fedora}", 6, "fedora"),
        ("", 0, None),
        ("%", 1, None),
        ("Name: foo", 999, None),
    ],
)
def test_macro_at_position(
    line: str, character: int, macro_string: Optional[str]
) -> None:
    assert get_macro_string_at_position(line, character) == macro_string


def test_get_macro_under_cursor_with_special_path(tmp_path: Path):
    """Regression test that we can have characters like `:` in the uri path
    (which get quoted).

    """
    (dest_dir := (tmp_path / "home:myself:notmuch")).mkdir(parents=True)
    (spec_f := (dest_dir / "notmuch.spec")).touch()
    spec_f.write_text(NOTMUCH_SPEC)

    macro = create_rpm_lang_server().get_macro_under_cursor(
        text_document=TextDocumentIdentifier(uri=f"file://{quote(str(spec_f))}"),
        position=Position(line=86, character=31),
        macros_dump=[Macro("libversion", None, "5", MacroLevel.SPEC, True)],
    )

    assert (
        macro
        and isinstance(macro, Macro)
        and macro.name == "libversion"
        and macro.body == "5"
    )


def test_get_macro_under_cursor_out_of_range() -> None:
    server = create_rpm_lang_server()
    spec = Specfile(content=NOTMUCH_SPEC, sourcedir=".", macros=parse_macros())

    macro = server.get_macro_under_cursor(
        spec=spec,
        position=Position(line=9999, character=0),
        macros_dump=server.macros,
    )

    assert macro is None
