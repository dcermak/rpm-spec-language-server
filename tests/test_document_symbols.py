from pathlib import Path

from lsprotocol.types import DocumentSymbol, Position, Range, SymbolKind
from specfile.specfile import Specfile

from rpm_spec_language_server.document_symbols import SpecSections


# from https://build.opensuse.org/package/view_file/devel:libraries:c_c++/notmuch/notmuch.spec?expand=1
_NOTMUCH_SPEC = r"""#
# spec file for package notmuch
#
# Copyright (c) 2023 SUSE LLC
#
# All modifications and additions to the file contributed by third parties
# remain the property of their copyright owners, unless otherwise agreed
# upon. The license for this file, and modifications and additions to the
# file, is the same license as for the pristine package itself (unless the
# license for the pristine package is not an Open Source License, in which
# case the license is the MIT License). An "Open Source License" is a
# license that conforms to the Open Source Definition (Version 1.9)
# published by the Open Source Initiative.

# Please submit bugfixes or comments via https://bugs.opensuse.org/
#


%define libversion 5
Name:           notmuch
Version:        0.37
Release:        0
Summary:        The mail indexer
License:        GPL-3.0-or-later
URL:            https://notmuchmail.org
Source0:        https://notmuchmail.org/releases/notmuch-%{version}.tar.xz
Source1:        https://notmuchmail.org/releases/notmuch-%{version}.tar.xz.asc
# key fingerprint: 7A18 807F 100A 4570 C596  8420 7E4E 65C8 720B 706B
Source4:        notmuch.keyring
BuildRequires:  libxapian-devel
# info pages
BuildRequires:  info
BuildRequires:  makeinfo
BuildRequires:  pkgconfig
BuildRequires:  python3-Sphinx
BuildRequires:  pkgconfig(gmime-3.0)
BuildRequires:  pkgconfig(talloc)

%{bcond_without python3}
%{bcond_without emacs}

#FIXME: at the moment they are not enabled
%{bcond_with ruby}
%{bcond_with go}

# dtach is not present on SLE
# cannot run the tests there
%if 0%{?is_opensuse}
%{bcond_without tests}
%else
%{bcond_with tests}
%endif
# testsuite
%if %{with tests}
BuildRequires:  dtach
BuildRequires:  gdb
BuildRequires:  man
BuildRequires:  openssl
BuildRequires:  valgrind-devel
%endif
%if %{with emacs}
BuildRequires:  emacs-el
BuildRequires:  emacs-nox
%endif
%if %{with python3}
BuildRequires:  python3-base
%endif
%if %{with ruby}
BuildRequires:  ruby-devel
%endif
%if %{with go}
BuildRequires:  go
%endif

%description
A global-search and tag-based email system that can be used from a terminal or
from within a text editor. Notmuch provides a library interface so that its
indexing/searching/tagging features can be integrated elsewhere.

Notmuch is not much of an email program. It does not receive messages
(no POP or IMAP support), it does not send messages (no mail
composer, no network code at all). It does email search, for which it
uses the Xapian library.

%package        devel
Summary:        Development files for %{name}
Requires:       libnotmuch%{libversion} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%package        doc
Summary:        Documentation for %{name}
Requires:       %{name} = %{version}-%{release}

%description    doc
This package contains the info pages for %{name}.

%package   -n libnotmuch%{libversion}
Summary:        A shared library for %{name}

%description -n libnotmuch%{libversion}
A global-search and tag-based email system which uses Xapian for indexing.

The libnotmuch%{libversion} package contains shared libraries for %{name}.

%if %{with python3}
%package -n python3-%{name}
Summary:        Python3 bindings for %{name}
Recommends:     python-%{name}-doc = %{version}

%description -n python3-%{name}
Python3 interface (bindings) for %{name}

%package -n python-%{name}-doc
Summary:        Documentation of Python bindings for %{name}

%description -n python-%{name}-doc
Documentation of Python interface (bindings) for %{name}
%endif

%if %{with emacs}
%package emacs
Summary:        Emacs lisp email client based on %{name}
Requires:       %{name} = %{version}-%{release}
Requires:       emacs
Requires:       emacs-el

%description emacs
%{name}-based email client written in emacs lisp
%endif

%prep
%autosetup

%build
#hand-made configure script
#zsh completion is a part of zsh itself
export CFLAGS="%{?build_cflags}%{?!build_cflags:%optflags}"
export CXXFLAGS="%{?build_cxxflags}%{?!build_cxxflags:%optflags}"
export LDFLAGS="${RPM_LD_FLAGS}"
./configure \
%if %{without emacs}
  --without-emacs \
%endif
  --prefix=%{_prefix} \
  --sysconfdir=%{_sysconfdir} \
  --datadir=%{_datadir} \
  --includedir=%{_includedir} \
  --libdir=%{_libdir} \
  --libexecdir=%{_libexecdir} \
  --localstatedir=%{_localstatedir} \
  --mandir=%{_mandir} \
  --infodir=%{_infodir} \
  --disable-dependency-tracking \
  --without-zsh-completion

%{make_build}

#TODO: bindings - go, ruby
pushd bindings

%if %{with python3}
cp -r python python3
pushd python3
python3 setup.py build
pushd docs
%{make_build} dirhtml
rm -f build/dirhtml/.buildinfo
popd
popd
%endif

popd

%install
%make_install

%if %{with python3}
pushd bindings/python3
python3 setup.py install --prefix=%{_prefix} --root=%{buildroot}
popd
%endif

%check
# Temporary: all tests pass except by known python-cffi ones, fixed upstream
exit 0

%if %{with tests}

# ensure that the tests are not running in parallel
export NOTMUCH_TEST_SERIALIZE=t

# this test fails on PPC64 (see id:87o8mpr5w6.fsf@tethera.net)
%ifarch ppc64
export NOTMUCH_SKIP_TESTS="T360-symbol-hiding"
%endif

# can only run the testsuite when debugging symbols are available (boo#1152451)
if echo "%{optflags}"|grep -q '\-g'; then
    %make_build check
fi

%endif
# {with tests}

%post -n libnotmuch%{libversion} -p /sbin/ldconfig
%postun -n libnotmuch%{libversion} -p /sbin/ldconfig

%files
%doc AUTHORS NEWS README
%license COPYING COPYING-GPL-3
%{_bindir}/%{name}
%{_bindir}/%{name}-emacs-mua
%{_mandir}/man1/%{name}*.1%{?ext_man}
%{_mandir}/man1/nmbug.1%{?ext_man}
%{_mandir}/man5/%{name}-hooks.5%{?ext_man}
%{_mandir}/man7/%{name}-search-terms.7%{?ext_man}
%{_mandir}/man7/%{name}-properties.7%{?ext_man}
%{_mandir}/man7/%{name}-sexp-queries.7%{?ext_man}

%files -n libnotmuch%{libversion}
%{_libdir}/libnotmuch.so.%{libversion}*

%files devel
%{_includedir}/%{name}.h
%{_libdir}/libnotmuch.so

%files doc
%{_infodir}/nmbug.info%{?ext_info}
%{_infodir}/%{name}.info%{?ext_info}
%{_infodir}/%{name}-*.info%{?ext_info}

%if %{with python3}
%files -n python3-%{name}
%doc bindings/python/README
%{python3_sitelib}/%{name}/
%{python3_sitelib}/%{name}*egg-info

%files -n python-%{name}-doc
%doc bindings/python3/docs/build/dirhtml/
%endif

%if %{with emacs}
%files emacs
%{_datadir}/emacs/site-lisp/
%exclude %{_datadir}/applications/
%endif

%changelog
"""


def test_simple_spec_document_symbols(tmp_path: Path) -> None:
    with open((spec_path := tmp_path / "notmuch.spec"), "w") as spec:
        spec.write(_NOTMUCH_SPEC)

    doc_symbols = SpecSections.parse(Specfile(str(spec_path))).to_document_symbols()
    assert doc_symbols[0] == DocumentSymbol(
        name="package",
        kind=SymbolKind.Namespace,
        range=(r := Range(Position(0, 0), Position(74, 0))),
        selection_range=r,
    )
    assert doc_symbols[1] == DocumentSymbol(
        name="description",
        kind=SymbolKind.Namespace,
        range=Range(p := Position(74, 0), Position(84, 0)),
        selection_range=Range(p, Position(75, 0)),
    )
    assert doc_symbols[2] == DocumentSymbol(
        name="package notmuch-devel",
        kind=SymbolKind.Namespace,
        range=Range(p := Position(84, 0), Position(88, 0)),
        selection_range=Range(p, Position(85, 0)),
    )
