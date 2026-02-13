# We're only extracting preamble tags and dependencies here for now

# Scriptlets probably can be done easily but conditionals, comments, and
# triggers will have to be done manually or someone will have to expand this
# script because they are laid out totally differently.  Fortunately there's
# not as many of those so it could just be done by hand.

# Sub-sections should be pretty easy but I'm leaving it out for now

# There's no standard layout here so this is Ultra Custom

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import rpm
from specfile.constants import (
    SCRIPT_SECTIONS,
    SECTION_NAMES,
    SIMPLE_SCRIPT_SECTIONS,
    TAG_NAMES,
)


@dataclass(frozen=True)
class _SpecDocument:
    preamble: list[str]
    dependencies: list[str]
    build_scriptlets: list[str]


@dataclass(frozen=True)
class AutoCompleteDoc:
    #: Tags from the preamble and dependency identifiers
    tags: dict[str, str]

    #: scriptlets like %build, %setup, etc.
    scriptlets: dict[str, str]


def get_index_of_line(document: list[str], line_start: str) -> Optional[int]:
    """Return the index of the first line starting with ``line_start``, or `None`."""
    for ind, line in enumerate(document):
        if line.startswith(line_start):
            return ind
    return None


def split_document(document: list[str]) -> _SpecDocument:
    """Split the upstream spec file documentation into the preamble,
    dependencies and Build Scriptlets section.

    """

    preamble_start = get_index_of_line(document, "### Preamble tags")
    dependencies_start = get_index_of_line(document, "### Dependencies")
    subsections_start = get_index_of_line(document, "### Sub-sections")
    scriptlets_start = get_index_of_line(document, "## Build scriptlets")

    if None in (
        preamble_start,
        dependencies_start,
        subsections_start,
        scriptlets_start,
    ):
        return _SpecDocument(preamble=[], dependencies=[], build_scriptlets=[])

    preamble = document[preamble_start:dependencies_start]
    dependencies = document[dependencies_start:subsections_start]
    scriptlets = document[scriptlets_start:]

    return _SpecDocument(
        preamble=preamble, dependencies=dependencies, build_scriptlets=scriptlets
    )


def get_preamble_or_dependencies_keywords(lines: list[str]) -> list[str]:
    keywords = []
    for line in lines:
        if line.startswith("#### "):
            keywords.append(line.strip().split(" ")[1])

    return keywords


_md_heading_re = re.compile(r"^[#]+ ")


def get_preamble_or_dependencies_doc(keyword: str, lines: list[str]) -> str:
    entered_doc = False
    doc = ""
    for line in lines:
        if (not entered_doc) and _md_heading_re.match(line) and (keyword in line):
            entered_doc = True
            continue
        if entered_doc and _md_heading_re.match(line):
            entered_doc = False
            break

        if entered_doc:
            doc += line.strip() + " "

    return doc.strip()


def get_build_scriptlets_keywords(lines: list[str]) -> list[str]:
    keywords = []
    for line in lines:
        if (line.startswith("###") or line.startswith(" * `%")) and ("%" in line):
            transtable = str.maketrans(
                {
                    "*": None,
                    "`": None,
                    "#": None,
                    "(": " ",
                }
            )
            keywords.append(str.split(line.translate(transtable).strip())[0])

    return keywords


def get_build_scriptlets_doc(keyword: str, lines: list[str]) -> str:
    entered_doc = False
    doc = ""
    for line in lines:
        if (
            (not entered_doc)
            and (keyword in line)
            and (
                (_md_heading_re.match(line) or line.startswith(" * `%"))
                and ("%" in line)
            )
        ):
            entered_doc = True
            continue
        if entered_doc and (_md_heading_re.match(line) or line.startswith(" * `%")):
            entered_doc = False
            break

        if entered_doc:
            doc += line.strip() + " "

    return doc.strip()


def create_autocompletion_documentation_from_spec_md(spec_md: str) -> AutoCompleteDoc:
    """Given the upstream specfile document :file:`spec.md`, parse it and
    extract the Preamble, Dependency description and scriptlets from it and
    their corresponding documentation.

    """
    spec = split_document(spec_md.splitlines())

    preamble_keywords = get_preamble_or_dependencies_keywords(spec.preamble)
    dependencies_keywords = get_preamble_or_dependencies_keywords(spec.dependencies)
    build_scriptlets_keywords = get_build_scriptlets_keywords(spec.build_scriptlets)

    preamble: dict[str, str] = {}
    dependencies: dict[str, str] = {}
    build_scriptlets: dict[str, str] = {}

    for keyword in preamble_keywords:
        preamble[keyword] = get_preamble_or_dependencies_doc(keyword, spec.preamble)

    for keyword in dependencies_keywords:
        dependencies[keyword] = get_preamble_or_dependencies_doc(
            keyword, spec.dependencies
        )

    for keyword in build_scriptlets_keywords:
        build_scriptlets[keyword] = get_build_scriptlets_doc(
            keyword, spec.build_scriptlets
        )

    tags = {**preamble, **dependencies}

    # add any missing tags from the specfile module
    lowercase_tags_keys = [k.lower() for k in tags.keys()]
    for tag in TAG_NAMES:
        if tag not in lowercase_tags_keys:
            tags[tag] = ""

    # add missing scriptlets from specfile
    for scriptlet in SECTION_NAMES | SIMPLE_SCRIPT_SECTIONS | SCRIPT_SECTIONS:
        if (full_name := f"%{scriptlet}") not in build_scriptlets:
            build_scriptlets[full_name] = ""

    return AutoCompleteDoc(tags=tags, scriptlets=build_scriptlets)


def fetch_upstream_spec_md(timeout: float = 5.0) -> Optional[str]:
    """Fetches :file:`spec.md` from the upstream `github repo
    <https://github.com/rpm-software-management/rpm>`_ and returns its
    contents. If the fetching fails, then `None` is returned.

    """
    import requests

    try:
        resp = requests.get(
            "https://raw.githubusercontent.com/rpm-software-management/rpm/master/docs/manual/spec.md",
            timeout=timeout,
        )
        return resp.text
    except requests.exceptions.RequestException:
        pass

    return None


def retrieve_spec_md(
    *, allow_network: bool = True, fetch_timeout: float = 5.0
) -> Optional[str]:
    """Retrieve :file:`spec.md` from either :file:`XDG_CACHE_HOME/rpm/spec.md`,
    the ``rpm`` package on the system or from the upstream git repository.

    If the :file:`spec.md` was fetched from the upstream git repository, then it
    is saved in :file:`XDG_CACHE_HOME/rpm/spec.md`.

    """
    cache_dir = Path(os.getenv("XDG_CACHE_HOME", os.path.expanduser("~/.cache")))
    path = (rpm_cache_dir := (cache_dir / "rpm")) / "spec.md"

    if path.exists():
        with open(path) as spec_md_f:
            return spec_md_f.read(-1)

    ts = rpm.TransactionSet()
    for pkg in ts.dbMatch("name", "rpm"):
        for f in rpm.files(pkg):
            if (spec_md_location := f.name).endswith("spec.md"):
                if (spec_md := Path(spec_md_location)).exists():
                    return spec_md.read_text()

    if not allow_network:
        return None

    if not (spec_md_contents := fetch_upstream_spec_md(timeout=fetch_timeout)):
        return None

    rpm_cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(spec_md_contents)
    return spec_md_contents
