import pytest
from rpm_spec_language_server.macros import get_macro_string_at_position


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
    ],
)
def test_macro_at_position(line: str, character: int, macro_string: str | None) -> None:
    assert get_macro_string_at_position(line, character) == macro_string
