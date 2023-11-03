from specfile.macros import Macros
from lsprotocol.types import (
    TEXT_DOCUMENT_COMPLETION,
    CompletionItem,
    CompletionList,
    CompletionOptions,
    CompletionParams,
)
from pygls.server import LanguageServer


class RpmSpecLanguageServer(LanguageServer):
    pass


rpm_spec_server = RpmSpecLanguageServer("rpm-spec-server", "0.0.1")

_MACROS = Macros.dump()


@rpm_spec_server.feature(
    TEXT_DOCUMENT_COMPLETION, CompletionOptions(trigger_characters=["%"])
)
def complete_macro_name(params: CompletionParams | None) -> CompletionList:
    return CompletionList(
        is_incomplete=False,
        items=[CompletionItem(label=macro.name) for macro in _MACROS],
    )
