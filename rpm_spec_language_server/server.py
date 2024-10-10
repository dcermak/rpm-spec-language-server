import os.path
import re
from importlib import metadata
from typing import Optional, Union, cast, overload
from urllib.parse import unquote, urlparse

import rpm
from lsprotocol.types import (
    INITIALIZE,
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
    InitializeParams,
    InitializeParamsClientInfoType,
    InitializeResult,
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
from pygls.protocol import LanguageServerProtocol, lsp_method
from pygls.server import LanguageServer
from specfile.exceptions import RPMException
from specfile.macros import Macro, MacroLevel, Macros
from specfile.specfile import Specfile

from rpm_spec_language_server.document_symbols import SpecSections
from rpm_spec_language_server.extract_docs import (
    create_autocompletion_documentation_from_spec_md,
    retrieve_spec_md,
)
from rpm_spec_language_server.logging import LOGGER
from rpm_spec_language_server.macros import (
    get_macro_string_at_position,
)
from rpm_spec_language_server.util import (
    position_from_match,
    spec_from_text,
)


class RpmLspProto(LanguageServerProtocol):
    """Our custom LSP Class that hooks into lsp_intialize and saves the client
    info for later consumption.

    """

    def __init__(self, *args, **kwargs) -> None:
        self.client: Optional[InitializeParamsClientInfoType] = None
        super().__init__(*args, **kwargs)

    @lsp_method(INITIALIZE)
    def lsp_initialize(self, params: InitializeParams) -> InitializeResult:
        self.client_info = params.client_info
        return super().lsp_initialize(params)


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

    def __init__(
        self,
        container_mount_path: Optional[str] = None,
        container_macro_mount_path: Optional[str] = None,
    ) -> None:
        super().__init__(
            name := "rpm_spec_language_server",
            metadata.version(name),
            protocol_cls=RpmLspProto,
        )
        self.spec_files: dict[str, SpecSections] = {}
        self.macros = Macros.dump()
        self.auto_complete_data = create_autocompletion_documentation_from_spec_md(
            retrieve_spec_md() or ""
        )
        self._container_path: str = container_mount_path or ""
        self._container_macro_mount_path: str = container_macro_mount_path or ""

    @property
    def is_vscode_connected(self) -> bool:
        """Try to guess from the LSP's client_info whether it is VSCode."""
        client_info: Optional[InitializeParamsClientInfoType] = cast(
            RpmLspProto, self.lsp
        ).client_info
        if client_info:
            return client_info.name.lower().startswith("code")
        return False

    def macro_and_scriptlet_completions(
        self, with_percent: bool
    ) -> list[CompletionItem]:
        # vscode does weird things with completions and sometimes needs the % to
        # be written in front of macros and sometimes not.
        # Other clients (lsp-mode.el, eglot.el, vim) on the other hand do not
        # like it to have their trigger character removed and discard such
        # completion items. Thus we have to include the % always for these
        # clients
        if not self.is_vscode_connected:
            with_percent = True

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
        return list(set(tag[0] for tag in self.auto_complete_data.tags).union({"%"}))

    def spec_sections_from_cache_or_file(
        self, text_document: Union[TextDocumentIdentifier, TextDocumentItem]
    ) -> Optional[SpecSections]:
        if sections := self.spec_files.get((uri := text_document.uri), None):
            return sections

        if not (spec := self.spec_from_text_document(text_document)):
            return None

        self.spec_files[uri] = (sect := SpecSections.parse(spec))
        return sect

    def _spec_path_from_uri(self, uri: str) -> Optional[str]:
        url = urlparse(uri)
        path = unquote(url.path)

        if url.scheme != "file" or not path.endswith(".spec"):
            return None

        if self._container_path:
            return os.path.join(self._container_path, os.path.basename(path))

        return path

    def _macro_uri(self, macro_file_location: str) -> str:
        if self._container_macro_mount_path:
            return "file://" + os.path.join(
                self._container_macro_mount_path,
                # remove leading slashes from the location as os.path.join will
                # otherwise return *only* macro_file_location and omit
                # self._container_macro_mount_path
                macro_file_location.lstrip("/"),
            )
        else:
            return f"file://{macro_file_location}"

    def spec_from_text_document(
        self,
        text_document: Union[TextDocumentIdentifier, TextDocumentItem],
    ) -> Optional[Specfile]:
        """Load a Specfile from a ``TextDocumentIdentifier`` or ``TextDocumentItem``.

        For ``TextDocumentIdentifier``s, load the file from disk and create the
        ``Specfile`` instance. For ``TextDocumentItem``s, load the spec from the
        in-memory representation.

        Returns ``None`` if the spec cannot be parsed.

        """
        path = self._spec_path_from_uri(text_document.uri)

        if not path:
            return None

        if not (text := getattr(text_document, "text", None)):
            try:
                return Specfile(path)
            except RPMException as rpm_exc:
                LOGGER.debug("Failed to parse spec %s, got %s", path, rpm_exc)
                return None

        return spec_from_text(text, os.path.basename(path))

    @overload
    def get_macro_under_cursor(
        self,
        *,
        spec: Specfile,
        position: Position,
        macros_dump: Optional[list[Macro]] = None,
    ) -> Optional[Union[Macro, str]]: ...

    @overload
    def get_macro_under_cursor(
        self,
        *,
        text_document: TextDocumentIdentifier,
        position: Position,
        macros_dump: Optional[list[Macro]] = None,
    ) -> Optional[Union[Macro, str]]: ...

    def get_macro_under_cursor(
        self,
        *,
        spec: Optional[Specfile] = None,
        text_document: Optional[TextDocumentIdentifier] = None,
        position: Position,
        macros_dump: Optional[list[Macro]] = None,
    ) -> Optional[Union[Macro, str]]:
        """Find the macro in the text document or spec under the cursor. If the text
        document is not a spec or there is no macro under the cursor, then ``None``
        is returned. If the symbol under the cursor looks like a macro and it is
        present in ``macros_dump``, then the respective ``Macro`` object is
        returned. If the symbol under the cursor looks like a macro, but is not in
        ``macros_dump``, then the symbol is returned as a string.

        If ``macros_dump`` is ``None``, then the system rpm macros are
        loaded. Passing a list (even an empty list) ensures that no macros are
        loaded.

        """
        if text_document is not None:
            path = self._spec_path_from_uri(text_document.uri)
            if not path:
                return None
            try:
                spec = Specfile(path)
            except RPMException as rpm_exc:
                LOGGER.debug("Failed to parse spec %s, got %s", path, rpm_exc)
                return None

        assert spec

        with spec.lines() as lines:
            symbol = get_macro_string_at_position(
                lines[position.line], position.character
            )
            if not symbol:
                return None

            for macro in macros_dump if macros_dump is not None else Macros.dump():
                if macro.name == symbol:
                    return macro

            return symbol


def create_rpm_lang_server(
    container_mount_path: Optional[str] = None,
    container_macro_mount_path: Optional[str] = None,
) -> RpmSpecLanguageServer:
    rpm_spec_server = RpmSpecLanguageServer(
        container_mount_path, container_macro_mount_path
    )

    def did_open_or_save(
        server: RpmSpecLanguageServer,
        param: Union[DidOpenTextDocumentParams, DidSaveTextDocumentParams],
    ) -> None:
        LOGGER.debug("open or save event")
        if not (spec := server.spec_from_text_document(param.text_document)):
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
                    for key, value in server.auto_complete_data.tags.items()
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
                    for key, value in server.auto_complete_data.tags.items()
                    if key.startswith(trigger_char)
                ],
            )

    @rpm_spec_server.feature(TEXT_DOCUMENT_DOCUMENT_SYMBOL)
    def spec_symbols(
        server: RpmSpecLanguageServer,
        param: DocumentSymbolParams,
    ) -> Optional[Union[list[DocumentSymbol], list[SymbolInformation]]]:
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
    ) -> Optional[Union[Location, list[Location], list[LocationLink]]]:
        # get the in memory spec if available
        if not (
            spec_sections := server.spec_sections_from_cache_or_file(
                param.text_document
            )
        ):
            return None

        macro_under_cursor = server.get_macro_under_cursor(
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
                                file_uri = server._macro_uri(f.name)
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
                        file_uri = server._macro_uri(fname)

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
    ) -> Optional[Hover]:
        if spec_sections := server.spec_files.get(params.text_document.uri, None):
            macro = server.get_macro_under_cursor(
                spec=spec_sections.spec,
                position=params.position,
                macros_dump=server.macros,
            )
        else:
            macro = server.get_macro_under_cursor(
                text_document=params.text_document,
                position=params.position,
                macros_dump=server.macros,
            )

        LOGGER.debug("Got macro '%s' at position %s", macro, params.position)

        # not a macro
        if not macro:
            return None

        if isinstance(macro, str):
            if not macro.startswith("%"):
                macro = f"%{macro}"

            try:
                if spec_sections:
                    expanded = spec_sections.spec.expand(macro)
                else:
                    path = server._spec_path_from_uri(params.text_document.uri)
                    if not path:
                        return None
                    spec = Specfile(path)
                    expanded = spec.expand(macro)

                LOGGER.debug("Expanded '%s' to '%s'", macro, expanded)
                if expanded == macro:
                    return None
                return Hover(
                    contents=MarkupContent(
                        value=f"```bash\n{expanded}\n```", kind=MarkupKind.Markdown
                    )
                )
            except RPMException:
                return None

        assert isinstance(macro, Macro)
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
