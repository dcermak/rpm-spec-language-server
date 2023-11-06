from urllib.parse import urlparse
from specfile.macros import Macros
from lsprotocol.types import (
    TEXT_DOCUMENT_COMPLETION,
    TEXT_DOCUMENT_DOCUMENT_SYMBOL,
    CompletionItem,
    CompletionList,
    CompletionOptions,
    CompletionParams,
    DocumentSymbol,
    DocumentSymbolParams,
    SymbolInformation,
)
from pygls.server import LanguageServer

from rpm_spec_language_server.document_symbols import spec_to_document_symbols


class RpmSpecLanguageServer(LanguageServer):
    pass


def create_rpm_lang_server() -> RpmSpecLanguageServer:
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

    @rpm_spec_server.feature(TEXT_DOCUMENT_DOCUMENT_SYMBOL)
    def spec_symbols(
        param: DocumentSymbolParams,
    ) -> list[DocumentSymbol] | list[SymbolInformation] | None:
        url = urlparse(param.text_document.uri)

        if url.scheme != "file" or not url.path.endswith(".spec"):
            return None

        return spec_to_document_symbols(url.path)

    return rpm_spec_server
