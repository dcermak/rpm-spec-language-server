from functools import reduce
from re import IGNORECASE, MULTILINE, Match, finditer, search
from tempfile import TemporaryDirectory
from typing import List, Optional

from lsprotocol.types import Position
from specfile.exceptions import RPMException
from specfile.specfile import Specfile

from rpm_spec_language_server.logging import LOGGER


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
            return Specfile(path)
        except RPMException as rpm_exc:
            LOGGER.debug("Failed to parse spec, got %s", rpm_exc)
            return None


def find_macro_matches_in_macro_file(
    macro_name: str, macro_file_contents: str
) -> List[Match[str]]:
    """Searches for definitions of ``macro_name`` in a rpm macro file with the
    contents ``macro_file_contents``.

    A macro can be defined in a macro file like: ``%macro `` or ``%macro($args)``.

    """
    return list(
        finditer(
            rf"^([\t \f]*)(%{macro_name})([\t \f]+|\()(\S+)",
            macro_file_contents,
            flags=MULTILINE,
        )
    )


def find_preamble_definition_in_spec(
    macro_name: str, spec_file_contents: str
) -> list[Match[str]]:
    """Find the definition of a "macro" like ``%version`` in the preamble of a
    spec file with the supplied contents. If any matches are found, then they
    are returned as a list of matches.

    """
    m = search(
        rf"^([\t \f]*)({macro_name}):([\t \f]+)(\S*)",
        spec_file_contents,
        flags=MULTILINE | IGNORECASE,
    )
    return [] if m is None else [m]


def find_macro_define_in_spec(
    macro_name: str, spec_file_contents: str
) -> list[Match[str]]:
    """Searches for the definition of the macro ``macro_name`` as it would
    appear in a spec file, i.e.: ``%global macro`` or ``%define macro``.

    """
    return list(
        finditer(
            rf"^([\t \f]*)(%(?:global|define))([\t \f]+)({macro_name})",
            spec_file_contents,
            flags=MULTILINE,
        )
    )
