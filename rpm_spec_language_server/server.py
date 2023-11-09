import rpm
import re
from urllib.parse import urlparse
from importlib import metadata
from specfile.exceptions import RPMException
from specfile.macros import MacroLevel, Macros
from lsprotocol.types import (
    TEXT_DOCUMENT_COMPLETION,
    TEXT_DOCUMENT_DEFINITION,
    TEXT_DOCUMENT_DOCUMENT_SYMBOL,
    TEXT_DOCUMENT_HOVER,
    CompletionItem,
    CompletionList,
    CompletionOptions,
    CompletionParams,
    DefinitionParams,
    DocumentSymbol,
    DocumentSymbolParams,
    Hover,
    HoverParams,
    Location,
    LocationLink,
    Position,
    Range,
    SymbolInformation,
    TextDocumentIdentifier,
    TextDocumentItem,
)
from pygls.server import LanguageServer

from rpm_spec_language_server.document_symbols import spec_to_document_symbols
from rpm_spec_language_server.document_symbols import SpecSections
from rpm_spec_language_server.extract_docs import (
    create_autocompletion_documentation_from_spec_md,
    spec_md_from_rpm_db,
)
from rpm_spec_language_server.macros import get_macro_under_cursor
from rpm_spec_language_server.util import position_from_match


class RpmSpecLanguageServer(LanguageServer):
    def __init__(self) -> None:
        super().__init__(name := "rpm_spec_language_server", metadata.version(name))
        self.spec_files: dict[str, SpecSections] = {}

    def spec_sections_from_cache_or_file(
        self, text_document: TextDocumentIdentifier | TextDocumentItem
    ) -> SpecSections | None:
        if sections := self.spec_files.get((uri := text_document.uri), None):
            return sections

        if not (spec := spec_from_text_document(text_document)):
            return None

        self.spec_files[uri] = (sect := SpecSections.parse(spec))
        return sect


def create_rpm_lang_server() -> RpmSpecLanguageServer:
    rpm_spec_server = RpmSpecLanguageServer()

    _MACROS = Macros.dump()

    auto_complete_data = create_autocompletion_documentation_from_spec_md(
        spec_md_from_rpm_db() or ""
    )

    @rpm_spec_server.feature(
        TEXT_DOCUMENT_COMPLETION, CompletionOptions(trigger_characters=["%"])
    )
    def complete_macro_name(params: CompletionParams | None) -> CompletionList:
        return CompletionList(
            is_incomplete=False,
            items=[
                CompletionItem(label=key[1:], documentation=value)
                for key, value in auto_complete_data.scriptlets.items()
            ]
            + [CompletionItem(label=macro.name) for macro in _MACROS],
        )

    @rpm_spec_server.feature(TEXT_DOCUMENT_DOCUMENT_SYMBOL)
    def spec_symbols(
        param: DocumentSymbolParams,
    ) -> list[DocumentSymbol] | list[SymbolInformation] | None:
        url = urlparse(param.text_document.uri)

        if url.scheme != "file" or not url.path.endswith(".spec"):
            return None

        return spec_to_document_symbols(url.path)

    @rpm_spec_server.feature(TEXT_DOCUMENT_DEFINITION)
    def find_macro_definition(
        param: DefinitionParams,
    ) -> Location | list[Location] | list[LocationLink] | None:
        macro_under_cursor = get_macro_under_cursor(param.text_document, param.position)

        if not macro_under_cursor:
            return None

        def find_macro_define_in_spec(file_contents: str) -> list[re.Match[str]]:
            """Searches for the definition of the macro ``macro_under_cursor``
            as it would appear in a spec file, i.e.: ``%global macro`` or
            ``%define macro``.

            """
            regex = re.compile(
                rf"^(\s*)(%(?:global|define))(\s+)({macro_under_cursor.name})",
                re.MULTILINE,
            )
            return list(regex.finditer(file_contents))

        def find_macro_in_macro_file(file_contents: str) -> list[re.Match[str]]:
            """Searches for the definition of the macro ``macro_under_cursor``
            as it would appear in a rpm macros file, i.e.: ``%macro …``.

            """
            regex = re.compile(
                rf"^(\s*)(%{macro_under_cursor.name})(\s+)", re.MULTILINE
            )
            return list(regex.finditer(file_contents))

        define_matches, file_uri = [], None

        # macro is defined in the spec file
        if macro_under_cursor.level == MacroLevel.GLOBAL:
            with open(urlparse(param.text_document.uri).path) as spec:
                if not (define_match := find_macro_define_in_spec(spec.read(-1))):
                    return None

            file_uri = param.text_document.uri

        # the macro comes from a macro file
        #
        # We have now two options, either it is provided by a rpm package. Then
        # there will be a package providing `rpm_macro($NAME)`. If that is the
        # case, then we query the rpm db for all files provided by all packages
        # providing this symbol and look for the macro definition in all files
        # that are in %_rpmmacrodir (nothing else will be loaded by rpm)
        #
        # If this yields nothing, then the macro most likely comes from the
        # builtin macros file of rpm (_should_ be in %_rpmconfigdir/macros) so
        # we retry the search in that file.
        elif macro_under_cursor.level == MacroLevel.MACROFILES:
            MACROS_DIR = rpm.expandMacro("%_rpmmacrodir")
            ts = rpm.TransactionSet()

            # search in packages
            for pkg in ts.dbMatch("provides", f"rpm_macro({macro_under_cursor.name})"):
                for f in rpm.files(pkg):
                    if f.name.startswith(MACROS_DIR):
                        with open(f.name) as macro_file_f:
                            if define_matches := find_macro_in_macro_file(
                                macro_file_f.read(-1)
                            ):
                                file_uri = f"file://{f.name}"
                                break

            # we didn't find a match
            # => the macro can be from %_rpmconfigdir/macros (no provides generated for it)
            if not define_matches:
                fname = rpm.expandMacro("%_rpmconfigdir") + "/macros"
                with open(fname) as macro_file_f:
                    if define_matches := find_macro_in_macro_file(
                        macro_file_f.read(-1)
                    ):
                        file_uri = f"file://{fname}"

        if define_matches and file_uri:
            return [
                Location(
                    uri=file_uri,
                    range=Range(
                        start := position_from_match(define_match),
                        Position(
                            line=start.line,
                            character=(
                                start.character
                                + define_match.end()
                                - define_match.start()
                            ),
                        ),
                    ),
                )
                for define_match in define_matches
            ]

        return None

    @rpm_spec_server.feature(TEXT_DOCUMENT_HOVER)
    def expand_macro(params: HoverParams) -> Hover | None:
        macro = get_macro_under_cursor(params.text_document, params.position)
        if not macro:
            return None

        try:
            return Hover(contents=Macros.expand(macro.body))
        except RPMException:
            return Hover(contents=macro.body)

    return rpm_spec_server
