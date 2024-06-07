import re
from pathlib import Path
from urllib.parse import quote

import pytest
from lsprotocol.types import Position, TextDocumentIdentifier
from rpm_spec_language_server.util import position_from_match, spec_from_text_document

from tests.data import NOTMUCH_SPEC


@pytest.mark.parametrize(
    "re_match,pos",
    [
        (
            re.search(
                "foobar",
                """nothing
bl
foobar
""",
            ),
            Position(2, 0),
        ),
        (
            re.search(
                "boooooo",
                """nothing
bl
foobar booo
                boooooooooooooo
""",
            ),
            Position(3, 16),
        ),
        (
            re.search(
                "bla",
                """bla
blub
""",
            ),
            Position(0, 0),
        ),
    ],
)
def test_position_from_match(re_match: re.Match[str], pos: Position) -> None:
    assert position_from_match(re_match) == pos


def test_spec_from_text_with_special_path(tmp_path: Path) -> None:
    """Regression test that we can have characters like `:` in the uri path
    (which get quoted).

    """
    (dest_dir := (tmp_path / "home:myself:notmuch")).mkdir(parents=True)
    (spec_f := (dest_dir / "notmuch.spec")).touch()
    spec_f.write_text(NOTMUCH_SPEC)

    spec = spec_from_text_document(
        text_document=TextDocumentIdentifier(
            uri=f"file://{quote(str(spec_f.absolute()))}"
        )
    )

    assert spec
    assert spec.name == "notmuch"
