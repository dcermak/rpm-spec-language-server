#! /usr/bin/env python3.11

# We're only extracting preamble tags and dependencies here for now

# Scriptlets probably can be done easily but conditionals, comments, and
# triggers will have to be done manually or someone will have to expand this
# script because they are laid out totally differently.  Fortunately there's
# not as many of those so it could just be done by hand.

# Sub-sections should be pretty easy but I'm leaving it out for now

# I am not currently cleaning up whitespace in the docstrings, which makes them
# quite messy.

# There's no standard layout here so this is Ultra Custom

import json


def get_index_of_line(document, line):
    return list(filter(lambda entry: entry[1].startswith(line), enumerate(document)))[
        0
    ][0]


def split_document(document):
    preamble_start = get_index_of_line(document, "### Preamble tags")

    dependencies_start = get_index_of_line(document, "### Dependencies")
    subsections_start = get_index_of_line(document, "### Sub-sections")

    scriptlets_start = get_index_of_line(document, "## Build scriptlets")

    preamble = document[preamble_start:dependencies_start]
    dependencies = document[dependencies_start:subsections_start]
    scriptlets = document[scriptlets_start:]

    return preamble, dependencies, scriptlets


def get_preamble_or_dependencies_keywords(chunk):
    keywords = []
    for line in chunk:
        if line.startswith("#### "):
            keywords.append(line.strip().split(" ")[1])

    return keywords


def get_preamble_or_dependencies_doc(keyword, chunk):
    entered_doc = False
    doc = ""
    for line in chunk:
        if (not entered_doc) and line.startswith("#### ") and (keyword in line):
            entered_doc = True
            continue
        if (entered_doc) and line.startswith("#### "):
            entered_doc = False
            break

        if entered_doc:
            doc += line

    return doc


def get_scriptlets_keywords(chunk):
    keywords = []
    for line in chunk:
        if line.startswith("###"):
            keywords.append(line.strip().split(" ")[1])
    print(keywords)


def get_scriptlets_doc(keyword, chunk):
    pass


document = []

with open("../resources/spec.md") as specdocs:
    document = specdocs.readlines()

preamble, dependencies, scriptlets = split_document(document)


preamble_keywords = get_preamble_or_dependencies_keywords(preamble)
dependencies_keywords = get_preamble_or_dependencies_keywords(dependencies)

preamble_data = []
dependencies_data = []

for keyword in preamble_keywords:
    preamble_data.append((keyword, get_preamble_or_dependencies_doc(keyword, preamble)))

for keyword in dependencies_keywords:
    dependencies_data.append(
        (keyword, get_preamble_or_dependencies_doc(keyword, dependencies))
    )

autocomplete_data = preamble_data + dependencies_data

with open("../src/autocomplete_data.json", "w") as adata:
    adata.write(json.dumps(autocomplete_data))
