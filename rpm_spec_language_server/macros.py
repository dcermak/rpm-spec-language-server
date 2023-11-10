from typing import overload
from urllib.parse import urlparse

from lsprotocol.types import Position, TextDocumentIdentifier
from specfile.macros import Macro, Macros
from specfile.specfile import Specfile


def get_macro_string_at_position(line: str, character: int) -> str | None:
    """Return the macro at the character position ``character`` from the line
    ``line`` and return it.

    """
    start_of_macro = 0
    end_of_macro = len(line)
    for i in range(character):
        # two %% indicate a "deactivated" macro
        if (
            line[i] == "%"
            and (i == 0 or line[i - 1] != "%")
            and (i == len(line) - 1 or line[i + 1] != "%")
        ):
            start_of_macro = i

    # not a macro, just a word
    # or a macro prefixed with another % and thus being commented out
    if line[start_of_macro] != "%" or (
        line[start_of_macro] == "%" and line[start_of_macro + 1] == "%"
    ):
        return None

    # macro is commented out => nothing
    if "%dnl" in line[:start_of_macro]:
        return None

    start_of_macro += 1
    if line[start_of_macro] == "{":
        start_of_macro += 1

    for i in range(start_of_macro, len(line)):
        if line[i] not in ("?", "!"):
            break
        start_of_macro += 1

    for i in range(max(character, start_of_macro), len(line)):
        if line[i] in ("}", "%", ",", ";") or line[i].isspace():
            end_of_macro = i
            break

    return line[start_of_macro:end_of_macro]


@overload
def get_macro_under_cursor(
    *,
    spec: Specfile,
    position: Position,
    macros_dump: list[Macro] | None = None,
) -> Macro | None:
    ...


@overload
def get_macro_under_cursor(
    *,
    text_document: TextDocumentIdentifier,
    position: Position,
    macros_dump: list[Macro] | None = None,
) -> Macro | None:
    ...


def get_macro_under_cursor(
    *,
    spec: Specfile | None = None,
    text_document: TextDocumentIdentifier | None = None,
    position: Position,
    macros_dump: list[Macro] | None = None,
) -> Macro | None:
    if text_document is not None:
        url = urlparse(text_document.uri)

        if url.scheme != "file" or not url.path.endswith(".spec"):
            return None

        spec = Specfile(url.path)

    assert spec

    with spec.lines() as lines:
        symbol = get_macro_string_at_position(lines[position.line], position.character)
        if not symbol:
            return None

        for macro in macros_dump if macros_dump is not None else Macros.dump():
            if macro.name == symbol:
                return macro

    return None
