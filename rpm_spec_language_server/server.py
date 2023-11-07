import rpm
import re
from urllib.parse import urlparse
from specfile.macros import MacroLevel, Macros
from lsprotocol.types import (
    TEXT_DOCUMENT_COMPLETION,
    TEXT_DOCUMENT_DEFINITION,
    TEXT_DOCUMENT_DOCUMENT_SYMBOL,
    CompletionItem,
    CompletionList,
    CompletionOptions,
    CompletionParams,
    DefinitionParams,
    DocumentSymbol,
    DocumentSymbolParams,
    Location,
    LocationLink,
    Position,
    Range,
    SymbolInformation,
)
from pygls.server import LanguageServer
from specfile.specfile import Specfile

from rpm_spec_language_server.document_symbols import spec_to_document_symbols
from rpm_spec_language_server.macros import get_macro_string_at_position
from rpm_spec_language_server.util import position_from_match


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

    @rpm_spec_server.feature(TEXT_DOCUMENT_DEFINITION)
    def find_macro_definition(
        param: DefinitionParams,
    ) -> Location | list[Location] | list[LocationLink] | None:
        url = urlparse(param.text_document.uri)

        if url.scheme != "file" or not url.path.endswith(".spec"):
            return None

        spec = Specfile(url.path)

        macro_under_cursor = None
        with spec.lines() as lines:
            symbol = get_macro_string_at_position(
                lines[param.position.line], param.position.character
            )
            if not symbol:
                return None

            for macro in Macros.dump():
                if macro.name == symbol:
                    macro_under_cursor = macro
                    break

        if not macro_under_cursor:
            return None

        def find_macro_define_in_spec(file_contents: str) -> re.Match[str] | None:
            """Searches for the definition of the macro ``macro_under_cursor``
            as it would appear in a spec file, i.e.: ``%global macro`` or
            ``%define macro``.

            """
            regex = re.compile(
                rf"^(\s*)(%(?:global|define))(\s+)({macro_under_cursor.name})",
                re.MULTILINE,
            )
            return regex.search(file_contents)

        def find_macro_in_macro_file(file_contents: str) -> re.Match[str] | None:
            """Searches for the definition of the macro ``macro_under_cursor``
            as it would appear in a rpm macros file, i.e.: ``%macro …``.

            """
            regex = re.compile(
                rf"^(\s*)(%{macro_under_cursor.name})(\s+)", re.MULTILINE
            )
            return regex.search(file_contents)

        define_match, file_uri = None, None

        # macro is defined in the spec file
        if macro_under_cursor.level == MacroLevel.GLOBAL:
            if not (define_match := find_macro_define_in_spec(str(spec))):
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
                            if define_match := find_macro_in_macro_file(
                                macro_file_f.read(-1)
                            ):
                                file_uri = f"file://{f.name}"
                                break

            # we didn't find a match
            # => the macro can be from %_rpmconfigdir/macros (no provides generated for it)
            if not define_match:
                fname = rpm.expandMacro("%_rpmconfigdir") + "/macros"
                with open(fname) as macro_file_f:
                    if define_match := find_macro_in_macro_file(macro_file_f.read(-1)):
                        file_uri = f"file://{fname}"

        if define_match and file_uri:
            return Location(
                uri=file_uri,
                range=Range(
                    start := position_from_match(define_match),
                    Position(
                        line=start.line,
                        character=(
                            start.character + define_match.end() - define_match.start()
                        ),
                    ),
                ),
            )

        return None

    return rpm_spec_server
