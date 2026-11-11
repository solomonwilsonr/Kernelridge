"""Minimal, dependency-free ELF header and RISC-V architecture-string inspection.

Best effort only: fields this cannot determine from the raw bytes are left as
null, matching the rest of kernelridge's "explicit unknown over guessed fact"
policy. Does not require readelf, pyelftools, or any third-party package.
"""
import struct
from pathlib import Path

EI_NIDENT = 16
EM_RISCV = 243
MACHINE_TO_ARCHITECTURE = {62: "x86_64", 183: "arm64"}
# e_flags & EF_RISCV_FLOAT_ABI_MASK (bits 1-2): 0=soft, 1=single, 2=double, 3=quad.
RISCV_FLOAT_ABI_SUFFIX = {0x0: "", 0x2: "f", 0x4: "d", 0x6: "q"}
SHT_RISCV_ATTRIBUTES_SECTION_NAME = ".riscv.attributes"


def _read_ehdr(data):
    if len(data) < EI_NIDENT + 4 or data[:4] != b"\x7fELF":
        raise ValueError("expected an ELF file")
    ei_class, ei_data = data[4], data[5]
    if ei_class not in (1, 2):
        raise ValueError("unknown ELF class")
    if ei_data not in (1, 2):
        raise ValueError("unknown ELF data encoding")
    endian = "<" if ei_data == 1 else ">"
    is64 = ei_class == 2
    fmt = endian + ("HHIQQQIHHHHHH" if is64 else "HHIIIIIHHHHHH")
    size = struct.calcsize(fmt)
    if len(data) < EI_NIDENT + size:
        raise ValueError("truncated ELF header")
    (e_type, e_machine, e_version, e_entry, e_phoff, e_shoff, e_flags,
     e_ehsize, e_phentsize, e_phnum, e_shentsize, e_shnum, e_shstrndx) = struct.unpack_from(fmt, data, EI_NIDENT)
    return {"class": 64 if is64 else 32, "endian": endian, "machine": e_machine, "flags": e_flags,
            "shoff": e_shoff, "shentsize": e_shentsize, "shnum": e_shnum, "shstrndx": e_shstrndx}


def _sections64(data, hdr):
    if hdr["class"] != 64 or not hdr["shoff"] or not hdr["shnum"] or hdr["shstrndx"] >= hdr["shnum"]:
        return None
    endian, fmt = hdr["endian"], hdr["endian"] + "IIQQQQIIQQ"
    size = struct.calcsize(fmt)
    raw = []
    for i in range(hdr["shnum"]):
        offset = hdr["shoff"] + i * hdr["shentsize"]
        if offset + size > len(data):
            return None
        name, _type, _flags, _addr, section_offset, section_size, *_rest = struct.unpack_from(fmt, data, offset)
        raw.append({"name_offset": name, "offset": section_offset, "size": section_size})
    strtab = raw[hdr["shstrndx"]]
    strtab_bytes = data[strtab["offset"]: strtab["offset"] + strtab["size"]]

    def name_at(off):
        end = strtab_bytes.find(b"\x00", off)
        end = len(strtab_bytes) if end == -1 else end
        return strtab_bytes[off:end].decode("ascii", errors="replace")

    return {name_at(s["name_offset"]): s for s in raw}


def _find_arch_string(raw):
    for prefix in (b"rv64", b"rv32"):
        idx = raw.find(prefix)
        if idx != -1:
            end = raw.find(b"\x00", idx)
            end = len(raw) if end == -1 else end
            return raw[idx:end].decode("ascii", errors="replace")
    return None


def _parse_arch_string(arch):
    for prefix in ("rv64", "rv32"):
        if arch.startswith(prefix):
            arch = arch[len(prefix):]
            break
    else:
        return []
    extensions = []
    for token in arch.split("_"):
        i = 0
        while i < len(token) and token[i].isalpha():
            i += 1
        alpha, rest = token[:i], token[i:]
        if not alpha:
            continue
        if len(alpha) > 1 and not rest:
            extensions.extend(list(alpha))
        else:
            extensions.append(alpha)
    return extensions


def inspect(path):
    """Return a machine/artifact-shaped JSON fragment derived from a real ELF file."""
    data = Path(path).read_bytes()
    hdr = _read_ehdr(data)
    if hdr["machine"] == EM_RISCV:
        architecture = "riscv64" if hdr["class"] == 64 else "riscv32"
    else:
        architecture = MACHINE_TO_ARCHITECTURE.get(hdr["machine"], f"unknown-elf-machine-0x{hdr['machine']:x}")
    abi, extensions = None, None
    if architecture == "riscv64":
        float_abi = RISCV_FLOAT_ABI_SUFFIX.get(hdr["flags"] & 0x6)
        if float_abi is not None and hdr["class"] == 64:
            abi = "lp64" + float_abi
        sections = _sections64(data, hdr)
        attrs = sections.get(SHT_RISCV_ATTRIBUTES_SECTION_NAME) if sections else None
        if attrs:
            raw = data[attrs["offset"]: attrs["offset"] + attrs["size"]]
            arch_string = _find_arch_string(raw)
            if arch_string:
                extensions = _parse_arch_string(arch_string)
    return {"id": Path(path).name, "architecture": architecture, "abi": abi,
            "isa_extensions": extensions, "required_extensions": extensions, "libraries": {}}
