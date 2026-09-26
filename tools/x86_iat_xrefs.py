from __future__ import annotations

import argparse
import struct
from dataclasses import dataclass
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs


@dataclass(frozen=True)
class Section:
    name: str
    virtual_address: int
    virtual_size: int
    raw_offset: int
    raw_size: int


class Pe32:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        pe_offset = struct.unpack_from("<I", self.data, 0x3C)[0]
        if self.data[pe_offset : pe_offset + 4] != b"PE\0\0":
            raise ValueError("Not a PE image")
        file_header = pe_offset + 4
        section_count = struct.unpack_from("<H", self.data, file_header + 2)[0]
        optional_size = struct.unpack_from("<H", self.data, file_header + 16)[0]
        optional = file_header + 20
        if struct.unpack_from("<H", self.data, optional)[0] != 0x10B:
            raise ValueError("Only PE32 images are supported")
        self.image_base = struct.unpack_from("<I", self.data, optional + 28)[0]
        section_table = optional + optional_size
        sections: list[Section] = []
        for index in range(section_count):
            offset = section_table + index * 40
            name = self.data[offset : offset + 8].split(b"\0", 1)[0].decode("ascii")
            virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
                "<IIII", self.data, offset + 8
            )
            sections.append(
                Section(
                    name=name,
                    virtual_address=virtual_address,
                    virtual_size=virtual_size,
                    raw_offset=raw_offset,
                    raw_size=raw_size,
                )
            )
        self.sections = sections

    def section(self, name: str) -> Section:
        return next(section for section in self.sections if section.name == name)

    def va_to_offset(self, va: int) -> int:
        rva = va - self.image_base
        for section in self.sections:
            if section.virtual_address <= rva < (
                section.virtual_address + max(section.virtual_size, section.raw_size)
            ):
                return section.raw_offset + rva - section.virtual_address
        raise ValueError(f"VA is not mapped: {va:08X}")

    def offset_to_va(self, offset: int) -> int:
        for section in self.sections:
            if section.raw_offset <= offset < section.raw_offset + section.raw_size:
                return (
                    self.image_base
                    + section.virtual_address
                    + offset
                    - section.raw_offset
                )
        raise ValueError(f"File offset is not mapped: {offset:08X}")


def disassemble_context(pe: Pe32, call_offset: int, context: int) -> str:
    text = pe.section(".text")
    lower = max(text.raw_offset, call_offset - context)
    upper = min(text.raw_offset + text.raw_size, call_offset + context)
    start_va = pe.offset_to_va(lower)
    call_va = pe.offset_to_va(call_offset)
    engine = Cs(CS_ARCH_X86, CS_MODE_32)
    lines: list[str] = []
    for instruction in engine.disasm(pe.data[lower:upper], start_va):
        marker = "=>" if instruction.address == call_va else "  "
        lines.append(
            f"{marker} {instruction.address:08X}  "
            f"{instruction.mnemonic:<8} {instruction.op_str}"
        )
    return "\n".join(lines)


def disassemble_function(pe: Pe32, call_offset: int, limit: int = 0x4000) -> str:
    text = pe.section(".text")
    text_start = text.raw_offset
    text_end = text.raw_offset + text.raw_size
    search_start = max(text_start, call_offset - limit)
    padding = b"\xCC\xCC\xCC\xCC"
    previous = pe.data.rfind(padding, search_start, call_offset)
    if previous < 0:
        lower = search_start
    else:
        lower = previous + len(padding)
        while lower < call_offset and pe.data[lower] == 0xCC:
            lower += 1

    following = pe.data.find(padding, call_offset, min(text_end, call_offset + limit))
    upper = following if following >= 0 else min(text_end, call_offset + limit)
    start_va = pe.offset_to_va(lower)
    call_va = pe.offset_to_va(call_offset)
    engine = Cs(CS_ARCH_X86, CS_MODE_32)
    lines: list[str] = []
    for instruction in engine.disasm(pe.data[lower:upper], start_va):
        marker = "=>" if instruction.address == call_va else "  "
        lines.append(
            f"{marker} {instruction.address:08X}  "
            f"{instruction.mnemonic:<8} {instruction.op_str}"
        )
    return "\n".join(lines)


def find_xrefs(pe: Pe32, target_va: int) -> list[tuple[int, str]]:
    text = pe.section(".text")
    start = text.raw_offset
    end = start + text.raw_size
    raw = pe.data[start:end]
    immediate = struct.pack("<I", target_va)
    results: list[tuple[int, str]] = []
    cursor = 0
    while True:
        index = raw.find(immediate, cursor)
        if index < 0:
            break
        absolute = start + index
        prefix = pe.data[max(0, absolute - 2) : absolute]
        kind = {
            b"\xFF\x15": "call [iat]",
            b"\xFF\x25": "jmp [iat]",
        }.get(prefix, "immediate")
        instruction_offset = absolute - 2 if kind != "immediate" else absolute
        results.append((instruction_offset, kind))
        cursor = index + 1
    return results


def find_relative_xrefs(pe: Pe32, target_va: int) -> list[tuple[int, str]]:
    text = pe.section(".text")
    start = text.raw_offset
    end = start + text.raw_size
    results: list[tuple[int, str]] = []
    for offset in range(start, end - 5):
        opcode = pe.data[offset]
        if opcode not in (0xE8, 0xE9):
            continue
        source_va = pe.offset_to_va(offset)
        displacement = struct.unpack_from("<i", pe.data, offset + 1)[0]
        destination = source_va + 5 + displacement
        if destination == target_va:
            results.append(
                (offset, "relative call" if opcode == 0xE8 else "relative jump")
            )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find x86 references to PE import-address-table slots"
    )
    parser.add_argument("image", type=Path)
    parser.add_argument("address", nargs="+", help="IAT virtual address in hex")
    parser.add_argument("--context", type=int, default=96)
    parser.add_argument(
        "--function",
        action="store_true",
        help="Disassemble the surrounding function using INT3 padding",
    )
    parser.add_argument(
        "--relative",
        action="store_true",
        help="Find direct relative calls and jumps to code addresses",
    )
    args = parser.parse_args()

    pe = Pe32(args.image)
    for text in args.address:
        target = int(text, 16)
        xrefs = (
            find_relative_xrefs(pe, target)
            if args.relative
            else find_xrefs(pe, target)
        )
        label = "CODE" if args.relative else "IAT"
        print(f"{label} {target:08X}: {len(xrefs)} .text reference(s)")
        for number, (offset, kind) in enumerate(xrefs, 1):
            print(
                f"\n[{number}] {kind} at {pe.offset_to_va(offset):08X} "
                f"(file {offset:08X})"
            )
            if args.function and kind == "call [iat]":
                print(disassemble_function(pe, offset))
            else:
                print(disassemble_context(pe, offset, args.context))


if __name__ == "__main__":
    main()
