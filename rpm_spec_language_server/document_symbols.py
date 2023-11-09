from __future__ import annotations

from dataclasses import dataclass
from lsprotocol.types import DocumentSymbol, Position, Range, SymbolKind
from specfile.sections import Section
from specfile.specfile import Specfile


@dataclass
class SpecSection:
    name: str
    starting_line: int
    ending_line: int
    _section: Section

    @property
    def contents(self) -> str:
        return str(self._section)


@dataclass
class SpecSections:
    sections: list[SpecSection]
    spec: Specfile

    def section_under_cursor(self, position: Position) -> SpecSection | None:
        for sect in self.sections:
            if position.line >= sect.starting_line and position.line < sect.ending_line:
                return sect
        return None

    @staticmethod
    def parse(spec: Specfile) -> SpecSections:
        sections = []

        with spec.sections() as sects:
            current_line = 0

            for section in sects:
                name = section.name

                if opt := str(section.options).strip():
                    if not opt.startswith("-"):
                        name = f"{name} {spec.name}-{opt.split()[0]}"

                    if "-n" in opt:
                        name = f"{name} {(o := opt.split())[o.index('-n') + 1]}"

                section_length = len(section.data)

                if name != "package":
                    section_length += 1

                sections.append(
                    SpecSection(
                        name,
                        starting_line=current_line,
                        ending_line=current_line + section_length,
                        _section=section,
                    )
                )

                current_line += section_length

        return SpecSections(sections, spec)

    def to_document_symbols(self) -> list[DocumentSymbol]:
        return [
            DocumentSymbol(
                name=section.name,
                kind=SymbolKind.Namespace,
                range=(
                    section_range := Range(
                        start=Position(line=section.starting_line, character=0),
                        end=Position(line=section.ending_line, character=0),
                    )
                ),
                selection_range=section_range
                if section.name == "package"
                else Range(
                    start=Position(line=section.starting_line, character=0),
                    end=Position(line=section.starting_line + 1, character=0),
                ),
            )
            for section in self.sections
        ]
