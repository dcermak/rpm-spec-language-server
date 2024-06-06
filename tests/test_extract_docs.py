# trailing whitespaces are intentional and present upstream
# ruff: noqa: W291
import re
from dataclasses import dataclass
from pathlib import Path

import pytest
import rpm
from rpm_spec_language_server.extract_docs import (
    create_autocompletion_documentation_from_spec_md,
    fetch_upstream_spec_md,
    retrieve_spec_md,
)

# trailing whitespace is intentional
_NAME_DOC = """The Name tag contains the proper name of the package. Names must not
include whitespace and may include a hyphen '-' (unlike version and release  
tags). Names should not include any numeric operators ('<', '>','=') as
future versions of rpm may need to reserve characters other than '-'.
"""

_PATCH_DOC = """Used to declare patches applied on top of sources. All patches declared
will be packaged into source rpms.
"""

_ICON_DOC = "Used to attach an icon to an rpm package file. Obsolete."

_PROVIDES_DOC = """Capabilities provided by this package.

`name = [epoch:]version-release` is automatically added to all packages.
"""

_CONFLICTS_DOC = """Capabilities this package conflicts with, typically packages with
conflicting paths or otherwise conflicting functionality.
"""

_OBSOLETES_DOC = """Packages obsoleted by this package. Used for replacing and renaming
packages.
"""

_GENERATE_BUILDREQUIRES_DOC = """
This optional script can be used to determine `BuildRequires`
dynamically. If present it is executed after %prep and can though
access the unpacked and patched sources. The script must print the found build
dependencies to stdout in the same syntax as used after
`BuildRequires:` one dependency per line.

`rpmbuild` will then check if the dependencies are met before
continuing the build. If some dependencies are missing a package with
the `.buildreqs.nosrc.rpm` postfix is created, that - as the name
suggests - contains the found build requires but no sources. It can be
used to install the build requires and restart the build.

On success the found build dependencies are also added to the source
package. As always they depend on the exact circumstance of the build
and may be different when bulding based on other packages or even
another architecture.
"""

_CONF_DOC = """In %conf, the unpacked sources are configured for building.

Different build- and language ecosystems come with their
own helper macros, but rpm has helpers for autotools based builds such as
itself which typically look like this:

```
%conf
%configure
```
"""

_CHECK_DOC = """If the packaged software has accomppanying tests, this is where they
should be executed.
"""

#: cut down version of https://github.com/rpm-software-management/rpm/blob/master/docs/manual/spec.md
_SPEC_MD = rf"""---
layout: default
title: rpm.org - Spec file format
---
# Spec file format


### Preamble tags

Since RPM 4.20 preamble tags can be indented with white space. Older
versions require the Tags to be at the beginning of a line. Comments
and empty lines are allowed.

#### Name

{_NAME_DOC}

#### Patch

{_PATCH_DOC}

#### Icon

{_ICON_DOC}

#### AutoReqProv
#### AutoReq
#### AutoProv

Control per-package automatic dependency generation for provides and requires. 
Accepted values are 1/0 or yes/no, default is always "yes". Autoreqprov is
equal to specifying Autoreq and Autoprov separately.

### Dependencies

The following tags are used to supply package dependency information,
all follow the same basic form. Can appear multiple times in the spec,
multiple values accepted, a single value is of the form
`capability [operator version]`. Capability names must
start with alphanumerics or underscore. Optional version range can be
supplied after capability name, accepted operators are `=`, `<`, `>`,
`<=` and `>=`, version 

#### Provides

{_PROVIDES_DOC}

#### Conflicts

{_CONFLICTS_DOC}

#### Obsoletes

{_OBSOLETES_DOC}

#### Recommends (since rpm >= 4.13)
#### Suggests
#### Supplements
#### Enhances

#### ExcludeArch

Package is not buildable on architectures listed here.
Used when software is portable across most architectures except some,
for example due to endianess issues.

#### ExclusiveArch

Package is only buildable on architectures listed here.
For example, it's probably not possible to build an i386-specific BIOS
utility on ARM, and even if it was it probably would not make any sense.


### Sub-sections

#### `%package [-n]<name>`

`%package <name>` starts a preamble section for a new sub-package.
Most preamble tags can are usable in sub-packages too, but there are
exceptions such as Name, which is taken from the `%package` directive.

By default subpackages are named by prepending the main package name
followed by a dash to the subpackage name(s), ie `<mainname>-<subname>`.
Using the `-n` option allows specifying an arbitrary (sub-)package name.

#### `%description [-n][name]`

%description is free form text, but there are two things to note.
The first regards reformatting.  Lines that begin with white space
are considered "pre-formatted" and will be left alone.  Adjacent
lines without leading whitespace are considered a single paragraph
and may be subject to formatting by glint or another RPM tool.

The `-n` option and `<name>` are the same as for `%package`, except that
when name is omitted, the description refers to the main package.

## Build scriptlets

Package build is divided into multiple separate steps, each executed in a
separate shell: `%prep`, `%conf`, `%build`, `%install`, `%check`, `%clean`
and `%generate_buildrequires`. Any unnecessary scriptlet sections can be
omitted.

Each section may be present only once, but in rpm >= 4.20 it is
possible to augment them by appending or prepending to them using
`-a` and `-p` options.
Append and prepend can be used multiple times. They are applied relative
to the corresponding main section, in the order they appear in the spec.
If the main section does not exist, they are applied relative to the
first fragment.

During the execution of build scriptlets, (at least) the following
rpm-specific environment variables are set:

Variable            | Description
--------------------|------------------------------
RPM_ARCH            | Architecture of the package
RPM_BUILD_DIR       | The build directory of the package
RPM_BUILD_NCPUS     | The number of CPUs available for the build
RPM_BUILD_ROOT      | The buildroot directory of the package
RPM_BUILD_TIME      | The build time of the package (seconds since the epoch)
RPM_DOC_DIR         | The special documentation directory of the package
RPM_LD_FLAGS        | Linker flags
RPM_OPT_FLAGS       | Compiler flags
RPM_OS              | OS of the package
RPM_PACKAGE_NAME    | Rpm name of the source package
RPM_PACKAGE_VERSION | Rpm version of the source package
RPM_PACKAGE_RELEASE | Rpm release of the source package
RPM_SOURCE_DIR      | The source directory of the package
RPM_SPECPARTS_DIR   | The directory of dynamically generated spec parts

Note: many of these have macro counterparts which may seem more convenient
and consistent with the rest of the spec, but one should always use
the environment variables inside the scripts. The reason for this is
that macros are evaluated during spec parse and may not be up-to-date,
whereas environment variables are evaluated at the time of their execution
in the script.

### %prep

%prep prepares the sources for building. This is where sources are
unpacked and possible patches applied, and other similar activies
could be performed.

Typically [%autosetup](autosetup.md) is used to automatically handle
it all, but for more advanced cases there are lower level `%setup`
and `%patch` builtin-macros available in this slot.

In simple packages `%prep` is often just:
```
%prep
%autosetup
```

#### %setup

`%setup [options]`

The primary function of `%setup` is to set up the build directory for the
package, typically unpacking the package's sources but optionally it
can just create the directory. It accepts a number of options:

```
-a N        unpack source N after changing to the build directory
-b N        unpack source N before changing to the build directory
-c          create the build directory (and change to it) before unpacking
-C          Create the build directory and ensure the archive contents
            are unpacked there, stripping the top level directory in the archive
            if it exists
-D          do not delete the build directory prior to unpacking (used
            when more than one source is to be unpacked with `-a` or `-b`)
-n DIR      set the name of build directory (default is `%{{name}}-%{{version}}`)
-T          skip the default unpacking of the first source (used with
            `-a` or `-b`)
-q          operate quietly
```


### %generate_buildrequires (since rpm >= 4.15)

{_GENERATE_BUILDREQUIRES_DOC}

### %conf (since rpm >= 4.18)

{_CONF_DOC}

### %check

{_CHECK_DOC}

### %clean (OBSOLETE)

Packages should place all their temporaries inside their designated
`%builddir`, which rpm will automatically clean up. Needing a package
specific `%clean` section generally suggests flaws in the spec.

## Runtime scriptlets

Runtime scriptlets are executed at the time of install and erase of the
package. By default, scriptlets are executed with `/bin/sh` shell, but
this can be overridden with `-p <path>` as an argument to the scriptlet
for each scriptlet individually. Other supported operations include
[scriptlet expansion](scriptlet_expansion.md).

### Basic scriptlets

 * `%pre`
 * `%post`
 * `%preun`
 * `%postun`
 * `%pretrans`
 * `%posttrans`
 * `%preuntrans`
 * `%postuntrans`
 * `%verify`

### Triggers

 * `%triggerprein`
 * `%triggerin`
 * `%triggerun`
 * `%triggerpostun`

More information is available in [trigger chapter](triggers.md).

### File triggers (since rpm >= 4.13)

 * `%filetriggerin`
 * `%filetriggerun`
 * `%filetriggerpostun`
 * `%transfiletriggerin`
 * `%transfiletriggerun`
 * `%transfiletriggerpostun`

#### `%attr(<mode>, <user>, <group>) <file|directory>`

`%attr()` overrides the permissions for a single file. `<mode>` is
an octal number such as you'd pass to `chmod`(1), `<user>` and `<group>`
are user and group names. Any of the three can be specified as `-` to
indicate use of current default value for that parameter.

#### `%defattr(<mode>, <user>, <group>, <dirmode>)`

`%defattr()` sets the default permissions of the following entries in
up to the next `%defattr()` directive or the end of the `%files` section
for that package, whichever comes first.

The first three arguments are the same as for `%attr()` (see above),
`<dirmode>` is the octal default mode for directories.

#### %readme

Obsolete.


"""

_auto_completion_data = create_autocompletion_documentation_from_spec_md(_SPEC_MD)
# equivalent of \s minus \n with at most one trailing or leading \n
_whitespace_cleanup_re = re.compile(r"\n?[\f\t\v\r ]+\n?")


def _whitespace_cleanup(s: str) -> str:
    return _whitespace_cleanup_re.sub(" ", s).replace("\n", " ").strip()


@pytest.mark.parametrize(
    "preamble_name, preamble_doc",
    (
        ("Name", _NAME_DOC),
        ("Patch", _PATCH_DOC),
        ("Icon", _ICON_DOC),
        ("AutoReqProv", ""),
        ("AutoReq", ""),
    ),
)
def test_autocompletion_doc_creation(preamble_name: str, preamble_doc: str) -> None:
    assert (preamble_name in _auto_completion_data.preamble) and (
        _auto_completion_data.preamble[preamble_name]
        == _whitespace_cleanup(preamble_doc)
    )


@pytest.mark.parametrize(
    "dependency_name, dependency_doc",
    (
        ("Provides", _PROVIDES_DOC),
        ("Obsoletes", _OBSOLETES_DOC),
        ("Conflicts", _CONFLICTS_DOC),
        ("Recommends", ""),
        ("Suggests", ""),
        ("Supplements", ""),
        ("Enhances", ""),
    ),
)
def test_dependencies_doc_creation(dependency_name: str, dependency_doc: str) -> None:
    assert (dependency_name in _auto_completion_data.dependencies) and (
        _auto_completion_data.dependencies[dependency_name]
        == _whitespace_cleanup(dependency_doc)
    )


@pytest.mark.parametrize(
    "scriptlet_name, scriptlet_doc",
    (
        ("%conf", _CONF_DOC),
        ("%check", _CHECK_DOC),
        ("%generate_buildrequires", _GENERATE_BUILDREQUIRES_DOC),
        ("%filetriggerin", ""),
        ("%preun", ""),
    ),
)
def test_scriptlets_doc_creation(scriptlet_name: str, scriptlet_doc: str) -> None:
    assert (scriptlet_name in _auto_completion_data.scriptlets) and (
        _auto_completion_data.scriptlets[scriptlet_name]
        == _whitespace_cleanup(scriptlet_doc)
    )


def test_fetch_upstream_spec_md() -> None:
    """Just try to fetch spec.md from github and fail if it is None"""
    assert fetch_upstream_spec_md()


def test_parse_upstream_spec_md() -> None:
    """Fetch upstream's spec.md from github and try to parse it. Then check that
    the parsed dictionaries are not empty.

    """
    spec_md = fetch_upstream_spec_md()
    assert spec_md

    auto_complete_data = create_autocompletion_documentation_from_spec_md(spec_md)

    assert auto_complete_data.dependencies
    assert auto_complete_data.preamble
    assert auto_complete_data.scriptlets


def test_cache_creation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    class MockTransactionSet:
        """Fake rpm.TransactionSet that returns no dbMatch so that
        retrieve_spec_md is forced to fetch the source from github.

        """

        def dbMatch(self, _tag, _pkg):
            return []

    monkeypatch.setattr(rpm, "TransactionSet", MockTransactionSet)

    spec = retrieve_spec_md()
    assert spec

    assert (
        cached_spec_path := (tmp_path / "rpm" / "spec.md")
    ).exists() and cached_spec_path.read_text() == spec


def test_spec_md_read_from_cache_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    (rpm_spec_cache := (tmp_path / "rpm")).mkdir(parents=True, exist_ok=True)
    (rpm_spec_cache / "spec.md").write_text(_SPEC_MD)

    class MockTransactionSet:
        """Fake rpm.TransactionSet that simply fails to instantiate"""

        def __init__(self) -> None:
            raise RuntimeError("barf")

    monkeypatch.setattr(rpm, "TransactionSet", MockTransactionSet)

    assert retrieve_spec_md() == _SPEC_MD


def test_spec_md_fetched_from_upstream_if_not_in_rpm_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    class MockTransactionSet:
        """Fake rpm.TransactionSet that simply fails to instantiate"""

        def dbMatch(self, tag, pkg):
            """returns a fake rpm package"""
            return [(tag, pkg)]

    def mock_rpm_files(pkg):
        assert not (ret := (tmp_path / "spec.md")).exists()
        return [ret]

    monkeypatch.setattr(rpm, "TransactionSet", MockTransactionSet)
    monkeypatch.setattr(rpm, "files", mock_rpm_files)

    # just check that it is not None, the contents will be fetched from github
    assert retrieve_spec_md()


def test_spec_md_read_from_rpm_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    (spec_md_p := (tmp_path / "spec.md")).write_text(
        fake_spec_md_text := "This is a dummy text"
    )

    class MockTransactionSet:
        """Fake rpm.TransactionSet that simply fails to instantiate"""

        def dbMatch(self, tag, pkg):
            """returns a fake rpm package"""
            return [(tag, pkg)]

    def mock_rpm_files(pkg):
        @dataclass
        class MockRpmFile:
            name: str

        assert spec_md_p.exists()
        return [MockRpmFile(name=str(spec_md_p.absolute()))]

    monkeypatch.setattr(rpm, "TransactionSet", MockTransactionSet)
    monkeypatch.setattr(rpm, "files", mock_rpm_files)

    # just check that it is not None, the contents will be fetched from github
    assert retrieve_spec_md() == fake_spec_md_text
