from lsprotocol.types import DocumentSymbol, Position, Range, SymbolKind
from specfile.specfile import Specfile


def spec_to_document_symbols(spec_path: str) -> list[DocumentSymbol]:
    symbols = []
    spec = Specfile(spec_path)
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
