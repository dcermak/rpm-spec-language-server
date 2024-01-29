import re

import pytest
from lsprotocol.types import Position
from rpm_spec_language_server.util import position_from_match


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
