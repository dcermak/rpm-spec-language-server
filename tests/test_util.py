# ruff: noqa: E501
# don't care about long line warnings in copied together strings
import re
from pathlib import Path
from typing import List
from urllib.parse import quote

import pytest
from lsprotocol.types import Position, TextDocumentIdentifier
from rpm_spec_language_server.server import create_rpm_lang_server
from rpm_spec_language_server.util import (
    find_macro_matches_in_macro_file,
    position_from_match,
)

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

    spec = create_rpm_lang_server().spec_from_text_document(
        text_document=TextDocumentIdentifier(
            uri=f"file://{quote(str(spec_f.absolute()))}"
        )
    )

    assert spec
    assert spec.name == "notmuch"


# copied together out of macros.python & macros.cmake
_FAKE_MACROS_FILE = r"""# Use the slashes after expand so that the command starts on the same line as
# the macro
%py3_build() %{expand:\\\
  CFLAGS="${CFLAGS:-${RPM_OPT_FLAGS}}" LDFLAGS="${LDFLAGS:-${RPM_LD_FLAGS}}"\\\
  %{__python3} %{py_setup} %{?py_setup_args} build --executable="%{__python3} %{py3_shbang_opts}" %{?*}
}

%py3_build_wheel() %{expand:\\\
  CFLAGS="${CFLAGS:-${RPM_OPT_FLAGS}}" LDFLAGS="${LDFLAGS:-${RPM_LD_FLAGS}}"\\\
  %{__python3} %{py_setup} %{?py_setup_args} bdist_wheel %{?*}
}

%cmake \
  %{set_build_flags} \
  %__cmake \\\
        %{!?__cmake_in_source_build:-S "%{_vpath_srcdir}"} \\\
        %{!?__cmake_in_source_build:-B "%{__cmake_builddir}"} \\\
        -DCMAKE_C_FLAGS_RELEASE:STRING="-DNDEBUG" \\\
        -DCMAKE_CXX_FLAGS_RELEASE:STRING="-DNDEBUG" \\\
        -DCMAKE_Fortran_FLAGS_RELEASE:STRING="-DNDEBUG" \\\
        -DCMAKE_VERBOSE_MAKEFILE:BOOL=ON \\\
        -DCMAKE_INSTALL_DO_STRIP:BOOL=OFF \\\
        -DCMAKE_INSTALL_PREFIX:PATH=%{_prefix} \\\
        -DINCLUDE_INSTALL_DIR:PATH=%{_includedir} \\\
        -DLIB_INSTALL_DIR:PATH=%{_libdir} \\\
        -DSYSCONF_INSTALL_DIR:PATH=%{_sysconfdir} \\\
        -DSHARE_INSTALL_PREFIX:PATH=%{_datadir} \\\
%if "%{?_lib}" == "lib64" \
        %{?_cmake_lib_suffix64} \\\
%endif \
        %{?_cmake_shared_libs}

%cmake_build \
  %__cmake --build "%{__cmake_builddir}" %{?_smp_mflags} --verbose

"""


@pytest.mark.parametrize(
    "macro_name, starts",
    [("py3_build", [90]), ("cmake", [481]), ("cmake_build", [1280])],
)
def test_macro_matches_in_macro_file(macro_name: str, starts: List[int]) -> None:
    matches = find_macro_matches_in_macro_file(macro_name, _FAKE_MACROS_FILE)

    assert len(matches) == len(starts)
    for i, pos in enumerate(starts):
        assert matches[i].start() == pos
