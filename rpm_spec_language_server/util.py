from functools import reduce
from re import Match
from tempfile import TemporaryDirectory
from typing import Optional

from lsprotocol.types import Position
from specfile.exceptions import RPMException
from specfile.specfile import Specfile

from rpm_spec_language_server.logging import LOGGER

_DEFAULT_PARSE_MACROS = [
    ("bcond_without", "%{!?with_%{1}: %global with_%{1} 0}"),
    ("bcond_with", "%{!?with_%{1}: %global with_%{1} 1}"),
]


def parse_macros() -> list[tuple[str, str]]:
    return list(_DEFAULT_PARSE_MACROS)


def position_from_match(re_match: Match[str]) -> Position:
    """Calculate the position of a regex search/match in a string."""

    line_count_before_match = re_match.string[: re_match.start()].count("\n")
    lines_before_match = re_match.string.splitlines()[:line_count_before_match]

    # length of all the lines *before* the match
    length_of_lines = (
        # summed up length of all lines before the match
        # add 0 as the initial value in case the match is on the first line
        reduce(lambda a, b: a + b, (len(line) for line in lines_before_match), 0)
        # don't forget to consider the line separators
        + len(lines_before_match)
    )

    character_pos = re_match.start() - length_of_lines

    return Position(line=line_count_before_match, character=character_pos)


def spec_from_text(
    spec_contents: str, file_name: Optional[str] = None
) -> Optional[Specfile]:
    """Load a specfile with the supplied contents and return a ``Specfile``
    instance or ``None`` if the spec cannot be parsed.

    The optional ``file_name`` parameter can be used to set the file name of the
    temporary spec that is used for parsing.

    """
    with TemporaryDirectory() as tmp_dir:
        with open(
            path := (f"{tmp_dir}/{file_name or 'unnamed.spec'}"), "w"
        ) as tmp_spec:
            tmp_spec.write(spec_contents)

        try:
            return Specfile(path, macros=parse_macros())
        except RPMException as rpm_exc:
            LOGGER.debug("Failed to parse spec, got %s", rpm_exc)
            return None
