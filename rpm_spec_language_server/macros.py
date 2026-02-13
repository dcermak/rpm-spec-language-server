from typing import Optional


def get_macro_string_at_position(line: str, character: int) -> Optional[str]:
    """Return the macro at the character position ``character`` from the line
    ``line`` and return it.

    """
    if not line:
        return None

    if character < 0 or character >= len(line):
        return None

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
    if start_of_macro >= len(line):
        return None

    if line[start_of_macro] != "%" or (
        line[start_of_macro] == "%"
        and (start_of_macro + 1) < len(line)
        and line[start_of_macro + 1] == "%"
    ):
        return None

    # macro is commented out => nothing
    if "%dnl" in line[:start_of_macro]:
        return None

    start_of_macro += 1
    if start_of_macro >= len(line):
        return None

    if line[start_of_macro] == "{":
        start_of_macro += 1
        if start_of_macro >= len(line):
            return None

    for i in range(start_of_macro, len(line)):
        if line[i] not in ("?", "!"):
            break
        start_of_macro += 1

    for i in range(max(character, start_of_macro), len(line)):
        if line[i] in ("}", "%", ",", ";") or line[i].isspace():
            end_of_macro = i
            break

    return line[start_of_macro:end_of_macro]
