from functools import reduce
from re import Match

from lsprotocol.types import Position


def position_from_match(re_match: Match[str]) -> Position:
    """Calculate the position of a regex search/match in a string."""

    line_count_before_match = re_match.string[: re_match.start()].count("\n")
    lines_before_match = re_match.string.splitlines()[:line_count_before_match]

    # length of all the lines *before* the match
    length_of_lines = (
        # summed up length of all lines before the match
        reduce(lambda a, b: a + b, (len(line) for line in lines_before_match))
        # don't forget to consider the line separators
        + len(lines_before_match)
    )

    character_pos = re_match.start() - length_of_lines

    return Position(line=line_count_before_match, character=character_pos)
