#! /usr/bin/python3.11

from pygls.server import LanguageServer
from lsprotocol.types import (
    TEXT_DOCUMENT_COMPLETION,
    CompletionItem,
    CompletionList,
    CompletionParams,
)

import os
import json
from thefuzz import fuzz
from thefuzz import process

server = LanguageServer("rpm-spec-lsp", "v0.1")

# Prepare keywords for thefuzz process match
with open(os.path.dirname(__file__)+"/autocomplete_data.json") as adata:
    autocomplete_data = json.loads(adata.read())

keywords = []
fuzzylimit = 20

for entry in autocomplete_data:
    keywords.append(entry[0])

def get_matching_doc(keyword):
    for entry in autocomplete_data:
        if keyword == entry[0]:
            return entry[1]

def prepare_completion_list(completion_entries):
    items = []
    for entry in completion_entries:
        items.append(CompletionItem(label=entry[0], documentation=get_matching_doc(entry[0])))

    return items


@server.feature(TEXT_DOCUMENT_COMPLETION)
def completions(params: CompletionParams):
    items = []
    document = server.workspace.get_document(params.text_document.uri)
    current_line = document.lines[params.position.line].strip()
    current_word = document.word_at_position(params.position)

    completion_entries = process.extract(current_word, keywords, limit=fuzzylimit)
    items = prepare_completion_list(completion_entries)

    #completion_entry = process.extractOne(current_word, keywords)

    #items = [CompletionItem(label=completion_entry[0], documentation=get_matching_doc(completion_entry[0]))]

    return CompletionList(
        is_incomplete=True,
        items=items,
    )


server.start_io()
