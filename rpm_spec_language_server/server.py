import os.path
import re
from importlib import metadata

import rpm
from lsprotocol.types import (
    TEXT_DOCUMENT_COMPLETION,
    TEXT_DOCUMENT_DEFINITION,
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_CLOSE,
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_DID_SAVE,
    TEXT_DOCUMENT_DOCUMENT_SYMBOL,
    TEXT_DOCUMENT_HOVER,
    CompletionItem,
    CompletionList,
    CompletionOptions,
    CompletionParams,
    DefinitionParams,
    DidChangeTextDocumentParams,
    DidCloseTextDocumentParams,
    DidOpenTextDocumentParams,
    DidSaveTextDocumentParams,
    DocumentSymbol,
    DocumentSymbolParams,
    Hover,
    HoverParams,
    Location,
    LocationLink,
    MarkupContent,
    MarkupKind,
    Position,
    Range,
    SymbolInformation,
    TextDocumentIdentifier,
    TextDocumentItem,
)
from pygls.server import LanguageServer
from specfile.exceptions import RPMException
from specfile.macros import MacroLevel, Macros

from rpm_spec_language_server.document_symbols import SpecSections
from rpm_spec_language_server.extract_docs import (
    create_autocompletion_documentation_from_spec_md,
    retrieve_spec_md,
)
from rpm_spec_language_server.logging import LOGGER
from rpm_spec_language_server.macros import get_macro_under_cursor
from rpm_spec_language_server.util import (
    position_from_match,
    spec_from_text,
    spec_from_text_document,
)


class RpmSpecLanguageServer(LanguageServer):
    _CONDITION_KEYWORDS = [
        # from https://github.com/rpm-software-management/rpm/blob/7d3d9041af2d75c4709cf7a721daf5d1787cce14/build/rpmbuild_internal.h#L58
        "%endif",
        "%else",
        "%if",
        "%ifarch",
        "%ifnarch",
        "%ifos",
        "%ifnos",
        "%include",
        "%elifarch",
        "%elifos",
        "%elif",
    ]

    def __init__(self) -> None:
        super().__init__(name := "rpm_spec_language_server", metadata.version(name))
        self.spec_files: dict[str, SpecSections] = {}
        self.macros = Macros.dump()
        self.auto_complete_data = create_autocompletion_documentation_from_spec_md(
            retrieve_spec_md() or ""
        )

    def macro_and_scriptlet_completions(
        self, with_percent: bool
    ) -> list[CompletionItem]:
        return (
            [
                CompletionItem(
                    label=key if with_percent else key[1:], documentation=value
                )
                for key, value in self.auto_complete_data.scriptlets.items()
            ]
            + [
                CompletionItem(label=keyword if with_percent else keyword[1:])
                for keyword in self._CONDITION_KEYWORDS
            ]
            + [
                CompletionItem(label=f"%{macro.name}" if with_percent else macro.name)
                for macro in self.macros
            ]
        )

    @property
    def trigger_characters(self) -> list[str]:
        return list(
            set(
                preamble_element[0]
                for preamble_element in {
                    **self.auto_complete_data.preamble,
                    **self.auto_complete_data.dependencies,
                }
            ).union({"%"})
        )

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

    def did_open_or_save(
        server: RpmSpecLanguageServer,
        param: DidOpenTextDocumentParams | DidSaveTextDocumentParams,
    ) -> None:
        LOGGER.debug("open or save event")
        if not (spec := spec_from_text_document(param.text_document)):
            return None

        LOGGER.debug("Saving parsed spec for %s", param.text_document.uri)
        server.spec_files[param.text_document.uri] = SpecSections.parse(spec)

    rpm_spec_server.feature(TEXT_DOCUMENT_DID_OPEN)(did_open_or_save)
    rpm_spec_server.feature(TEXT_DOCUMENT_DID_SAVE)(did_open_or_save)

    @rpm_spec_server.feature(TEXT_DOCUMENT_DID_CLOSE)
    def did_close(
        server: RpmSpecLanguageServer, param: DidCloseTextDocumentParams
    ) -> None:
        if param.text_document.uri in server.spec_files:
            del server.spec_files[param.text_document.uri]

    @rpm_spec_server.feature(TEXT_DOCUMENT_DID_CHANGE)
    def did_change(
        server: RpmSpecLanguageServer, param: DidChangeTextDocumentParams
    ) -> None:
        LOGGER.debug("Text document %s changed", (uri := param.text_document.uri))

        if spec := spec_from_text(
            server.workspace.text_documents[uri].source, os.path.basename(uri)
        ):
            server.spec_files[uri] = SpecSections.parse(spec)
            LOGGER.debug("Updated the spec for %s", uri)

    @rpm_spec_server.feature(
        TEXT_DOCUMENT_COMPLETION,
        CompletionOptions(trigger_characters=rpm_spec_server.trigger_characters),
    )
    def complete_macro_name(
        server: RpmSpecLanguageServer, params: CompletionParams
    ) -> CompletionList:
        if not (
            spec_sections := server.spec_sections_from_cache_or_file(
                text_document=params.text_document
            )
        ):
            return CompletionList(is_incomplete=False, items=[])

        trigger_char = (
            None if params.context is None else params.context.trigger_character
        )

        # we are *not* in the preamble or a %package foobar section
        # only complete macros
        if not (
            cur_sect := spec_sections.section_under_cursor(params.position)
        ) or not cur_sect.name.startswith("package"):
            # also if we have no completion context, just send macros and if we
            # have it, only send them if this was triggered by a %
            LOGGER.debug(
                "Sending completions for outside the package section with "
                "trigger_character %s",
                trigger_char,
            )
            if (trigger_char and trigger_char == "%") or trigger_char is None:
                return CompletionList(
                    is_incomplete=False,
                    items=server.macro_and_scriptlet_completions(
                        with_percent=trigger_char is None
                    ),
                )
            return CompletionList(is_incomplete=False, items=[])

        # we are in a package section => we can return preamble and dependency
        # tags as completion items too

        # return everything if we have no trigger character
        if trigger_char is None:
            LOGGER.debug(
                "Sending completions for %package/preamble without a trigger_character"
            )
            return CompletionList(
                is_incomplete=False,
                items=[
                    CompletionItem(label=key, documentation=value)
                    for key, value in {
                        **server.auto_complete_data.dependencies,
                        **server.auto_complete_data.preamble,
                    }.items()
                ]
                + server.macro_and_scriptlet_completions(with_percent=True),
            )

        if trigger_char == "%":
            LOGGER.debug("Sending completions for %package/premable triggered by %")
            return CompletionList(
                is_incomplete=False,
                items=server.macro_and_scriptlet_completions(with_percent=False),
            )
        else:
            LOGGER.debug(
                "Sending completions for %package/premable triggered by %s",
                trigger_char,
            )
            return CompletionList(
                is_incomplete=False,
                items=[
                    CompletionItem(label=key, documentation=value)
                    for key, value in {
                        **server.auto_complete_data.dependencies,
                        **server.auto_complete_data.preamble,
                    }.items()
                    if key.startswith(trigger_char)
                ],
            )

    @rpm_spec_server.feature(TEXT_DOCUMENT_DOCUMENT_SYMBOL)
    def spec_symbols(
        server: RpmSpecLanguageServer,
        param: DocumentSymbolParams,
    ) -> list[DocumentSymbol] | list[SymbolInformation] | None:
        if not (
            spec_sections := server.spec_sections_from_cache_or_file(
                text_document=param.text_document
            )
        ):
            return None

        return spec_sections.to_document_symbols()

    @rpm_spec_server.feature(TEXT_DOCUMENT_DEFINITION)
    def find_macro_definition(
        server: RpmSpecLanguageServer,
        param: DefinitionParams,
    ) -> Location | list[Location] | list[LocationLink] | None:
        # get the in memory spec if available
        if not (
            spec_sections := server.spec_sections_from_cache_or_file(
                param.text_document
            )
        ):
            return None

        macro_under_cursor = get_macro_under_cursor(
            spec=spec_sections.spec, position=param.position, macros_dump=server.macros
        )

        if not macro_under_cursor:
            return None

        macro_name = (
            macro_under_cursor
            if isinstance(macro_under_cursor, str)
            else macro_under_cursor.name
        )
        macro_level = (
            MacroLevel.SPEC
            if isinstance(macro_under_cursor, str)
            else macro_under_cursor.level
        )

        def find_macro_define_in_spec(file_contents: str) -> list[re.Match[str]]:
            """Searches for the definition of the macro ``macro_under_cursor``
            as it would appear in a spec file, i.e.: ``%global macro`` or
            ``%define macro``.

            """
            regex = re.compile(
                rf"^([\t \f]*)(%(?:global|define))([\t \f]+)({macro_name})",
                re.MULTILINE,
            )
            return list(regex.finditer(file_contents))

        def find_macro_in_macro_file(file_contents: str) -> list[re.Match[str]]:
            """Searches for the definition of the macro ``macro_under_cursor``
            as it would appear in a rpm macros file, i.e.: ``%macro …``.

            """
            regex = re.compile(
                rf"^([\t \f]*)(%{macro_name})([\t \f]+)(\S+)", re.MULTILINE
            )
            return list(regex.finditer(file_contents))

        def find_preamble_definition_in_spec(
            file_contents: str,
        ) -> list[re.Match[str]]:
            regex = re.compile(
                rf"^([\t \f]*)({macro_name}):([\t \f]+)(\S*)",
                re.MULTILINE | re.IGNORECASE,
            )
            if (m := regex.search(file_contents)) is None:
                return []
            return [m]

        define_matches, file_uri = [], None

        # macro is defined in the spec file
        if macro_level == MacroLevel.GLOBAL:
            if not (
                define_matches := find_macro_define_in_spec(str(spec_sections.spec))
            ):
                return None

            file_uri = param.text_document.uri

        # macro is something like %version, %release, etc.
        elif macro_level == MacroLevel.SPEC:
            if not (
                define_matches := find_preamble_definition_in_spec(
                    str(spec_sections.spec)
                )
            ):
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
        elif macro_level == MacroLevel.MACROFILES:
            MACROS_DIR = rpm.expandMacro("%_rpmmacrodir")
            ts = rpm.TransactionSet()

            # search in packages
            for pkg in ts.dbMatch("provides", f"rpm_macro({macro_name})"):
                for f in rpm.files(pkg):
                    if f.name.startswith(MACROS_DIR):
                        with open(f.name) as macro_file_f:
                            if define_matches := find_macro_in_macro_file(
                                macro_file_f.read(-1)
                            ):
                                file_uri = f"file://{f.name}"
                                break

            # we didn't find a match
            # => the macro can be from %_rpmconfigdir/macros (no provides
            #    generated for it)
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
    def expand_macro(
        server: RpmSpecLanguageServer, params: HoverParams
    ) -> Hover | None:
        if spec_sections := server.spec_files.get(params.text_document.uri, None):
            macro = get_macro_under_cursor(
                spec=spec_sections.spec,
                position=params.position,
                macros_dump=server.macros,
            )
        else:
            macro = get_macro_under_cursor(
                text_document=params.text_document,
                position=params.position,
                macros_dump=server.macros,
            )

        # not a macro or an unknown macro => cannot show a meaningful hover
        if not macro or isinstance(macro, str):
            return None

        if macro.level == MacroLevel.BUILTIN:
            return Hover(contents="builtin")

        try:
            expanded_macro = Macros.expand(macro.body)
            formatted_macro = f"```bash\n{expanded_macro}\n```"
            contents = MarkupContent(kind=MarkupKind.Markdown, value=formatted_macro)
            return Hover(contents)
        except RPMException:
            return Hover(contents=macro.body)

    return rpm_spec_server
