from pathlib import Path

from lsprotocol.types import DocumentSymbol, Position, Range, SymbolKind
from rpm_spec_language_server.document_symbols import SpecSections
from rpm_spec_language_server.util import parse_macros
from specfile.specfile import Specfile

from .data import NOTMUCH_SPEC


def test_simple_spec_document_symbols(tmp_path: Path) -> None:
    with open((spec_path := tmp_path / "notmuch.spec"), "w") as spec:
        spec.write(NOTMUCH_SPEC)

    doc_symbols = SpecSections.parse(
        Specfile(str(spec_path), macros=parse_macros())
    ).to_document_symbols()
    assert doc_symbols[0] == DocumentSymbol(
        name="package",
        kind=SymbolKind.Namespace,
        range=(r := Range(Position(0, 0), Position(74, 0))),
        selection_range=r,
    )
    assert doc_symbols[1] == DocumentSymbol(
        name="description",
        kind=SymbolKind.Namespace,
        range=Range(p := Position(74, 0), Position(84, 0)),
        selection_range=Range(p, Position(75, 0)),
    )
    assert doc_symbols[2] == DocumentSymbol(
        name="package notmuch-devel",
        kind=SymbolKind.Namespace,
        range=Range(p := Position(84, 0), Position(88, 0)),
        selection_range=Range(p, Position(85, 0)),
    )
