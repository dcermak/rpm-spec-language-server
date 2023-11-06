from urllib.parse import urlparse
from specfile.macros import Macros
from specfile.specfile import Specfile
from lsprotocol.types import (
    TEXT_DOCUMENT_COMPLETION,
    TEXT_DOCUMENT_DOCUMENT_SYMBOL,
    CompletionItem,
    CompletionList,
    CompletionOptions,
    CompletionParams,
    DocumentSymbol,
    DocumentSymbolParams,
    Position,
    Range,
    SymbolInformation,
    SymbolKind,
)
from pygls.server import LanguageServer


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

        symbols = []

        spec = Specfile(url.path)
        with spec.sections() as sections:
            current_line = 0

            for section in sections:
                name = section.name

                if opt := str(section.options).strip():
                    if not opt.startswith("-"):
                        name = f"{name} {spec.name}-{opt.split()[0]}"

                    if "-n" in opt:
                        name = f"{name} {(o := opt.split())[o.index('-n') + 1]}"

                section_length = len(section.data)

                if name != "package":
                    section_length += 1

                symbols.append(
                    DocumentSymbol(
                        name=name,
                        kind=SymbolKind.Namespace,
                        range=(
                            section_range := Range(
                                start=Position(line=current_line, character=0),
                                end=Position(
                                    line=current_line + section_length, character=0
                                ),
                            )
                        ),
                        selection_range=section_range
                        if name == "package"
                        else Range(
                            start=Position(line=current_line, character=0),
                            end=Position(line=current_line + 1, character=0),
                        ),
                    )
                )

                current_line += section_length

        return symbols

    return rpm_spec_server
