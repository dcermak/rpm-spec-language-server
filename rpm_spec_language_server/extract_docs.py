# We're only extracting preamble tags and dependencies here for now

# Scriptlets probably can be done easily but conditionals, comments, and
# triggers will have to be done manually or someone will have to expand this
# script because they are laid out totally differently.  Fortunately there's
# not as many of those so it could just be done by hand.

# Sub-sections should be pretty easy but I'm leaving it out for now

# There's no standard layout here so this is Ultra Custom

import os
from dataclasses import dataclass

import rpm


@dataclass(frozen=True)
class _SpecDocument:
    preamble: list[str]
    dependencies: list[str]
    build_scriptlets: list[str]


@dataclass(frozen=True)
class AutoCompleteDoc:
    preamble: dict[str, str]
    dependencies: dict[str, str]
    scriptlets: dict[str, str]


def get_index_of_line(document: list[str], line_start: str) -> int:
    """Returns the index of the first line starting with ``line_start``."""
    return [
        (ind, line) for ind, line in enumerate(document) if line.startswith(line_start)
    ][0][0]


def split_document(document: list[str]) -> _SpecDocument:
    """Split the upstream spec file documentation into the preamble,
    dependencies and Build Scriptlets section.

    """

    preamble_start = get_index_of_line(document, "### Preamble tags")

    dependencies_start = get_index_of_line(document, "### Dependencies")
    subsections_start = get_index_of_line(document, "### Sub-sections")

    scriptlets_start = get_index_of_line(document, "## Build scriptlets")

    preamble = document[preamble_start:dependencies_start]
    dependencies = document[dependencies_start:subsections_start]
    scriptlets = document[scriptlets_start:]

    return _SpecDocument(preamble, dependencies, scriptlets)


def get_preamble_or_dependencies_keywords(lines: list[str]) -> list[str]:
    keywords = []
    for line in lines:
        if line.startswith("#### "):
            keywords.append(line.strip().split(" ")[1])

    return keywords


def get_preamble_or_dependencies_doc(keyword: str, lines: list[str]) -> str:
    entered_doc = False
    doc = ""
    for line in lines:
        if (not entered_doc) and line.startswith("#### ") and (keyword in line):
            entered_doc = True
            continue
        if (entered_doc) and line.startswith("#### "):
            entered_doc = False
            break

        if entered_doc:
            doc += line

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
            and ((line.startswith("###") or line.startswith(" * `%")) and ("%" in line))
        ):
            entered_doc = True
            continue
        if (entered_doc) and (line.startswith("###") or line.startswith(" * `%")):
            entered_doc = False
            break

        if entered_doc:
            doc += line

    return doc.strip()


def create_autocompletion_documentation_from_spec_md(spec_md: str) -> AutoCompleteDoc:
    spec = split_document(spec_md.splitlines())

    preamble_keywords = get_preamble_or_dependencies_keywords(spec.preamble)
    dependencies_keywords = get_preamble_or_dependencies_keywords(spec.dependencies)
    build_scriptlets_keywords = get_build_scriptlets_keywords(spec.build_scriptlets)

    preamble = {}
    dependencies = {}
    build_scriptlets = {}

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

    return AutoCompleteDoc(preamble, dependencies, build_scriptlets)


def spec_md_from_rpm_db() -> str | None:
    path = os.path.expanduser("~/.cache/rpm/spec.md")
    if os.path.exists(path):
        with open(path) as spec_md_f:
            return spec_md_f.read(-1)
    else:
        ts = rpm.TransactionSet()
        for pkg in ts.dbMatch("name", "rpm"):
            for f in rpm.files(pkg):
                if (path := f.name).endswith("spec.md"):
                    with open(path) as spec_md_f:
                        return spec_md_f.read(-1)

    return None
