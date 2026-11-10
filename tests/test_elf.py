import struct
import tempfile
import unittest
from kernelridge.elf import inspect

EI_NIDENT_HEADER = struct.Struct("<4sBBBBB7x")


def _ehdr64(machine, flags=0, shoff=0, shentsize=0, shnum=0, shstrndx=0):
    ident = EI_NIDENT_HEADER.pack(b"\x7fELF", 2, 1, 1, 0, 0)
    fields = struct.pack("<HHIQQQIHHHHHH", 2, machine, 1, 0, 0, shoff, flags, 64, 0, 0, shentsize, shnum, shstrndx)
    return ident + fields


def _shdr64(name_offset, section_type, offset, size):
    return struct.pack("<IIQQQQIIQQ", name_offset, section_type, 0, 0, offset, size, 0, 0, 0, 0)


def _build_riscv_elf(arch_string):
    attrs_payload = b"A\x00\x00\x00" + b"riscv\x00" + arch_string.encode() + b"\x00"
    strtab = b"\x00.riscv.attributes\x00.shstrtab\x00"
    attrs_name_off, shstrtab_name_off = 1, 1 + len(b".riscv.attributes\x00")
    header_size = 64
    attrs_offset = header_size
    strtab_offset = attrs_offset + len(attrs_payload)
    shoff = strtab_offset + len(strtab)
    sh_null = _shdr64(0, 0, 0, 0)
    sh_attrs = _shdr64(attrs_name_off, 0x70000003, attrs_offset, len(attrs_payload))
    sh_strtab = _shdr64(shstrtab_name_off, 3, strtab_offset, len(strtab))
    header = _ehdr64(machine=243, flags=0x4, shoff=shoff, shentsize=64, shnum=3, shstrndx=2)
    return header + attrs_payload + strtab + sh_null + sh_attrs + sh_strtab


class ElfInspectTests(unittest.TestCase):
    def test_x86_64_minimal_header(self):
        with tempfile.NamedTemporaryFile() as binary:
            binary.write(_ehdr64(machine=62))
            binary.flush()
            fragment = inspect(binary.name)
            self.assertEqual(fragment["architecture"], "x86_64")
            self.assertIsNone(fragment["abi"])
            self.assertIsNone(fragment["isa_extensions"])
            self.assertEqual(fragment["libraries"], {})

    def test_riscv64_abi_and_extensions_from_attributes(self):
        with tempfile.NamedTemporaryFile() as binary:
            binary.write(_build_riscv_elf("rv64i2p1_m2p0_a2p1_f2p2_d2p2_c2p0"))
            binary.flush()
            fragment = inspect(binary.name)
            self.assertEqual(fragment["architecture"], "riscv64")
            self.assertEqual(fragment["abi"], "lp64d")
            self.assertEqual(fragment["isa_extensions"], ["i", "m", "a", "f", "d", "c"])
            self.assertEqual(fragment["required_extensions"], ["i", "m", "a", "f", "d", "c"])

    def test_riscv64_without_attributes_section_is_unknown_extensions(self):
        with tempfile.NamedTemporaryFile() as binary:
            binary.write(_ehdr64(machine=243, flags=0x2))
            binary.flush()
            fragment = inspect(binary.name)
            self.assertEqual(fragment["architecture"], "riscv64")
            self.assertEqual(fragment["abi"], "lp64f")
            self.assertIsNone(fragment["isa_extensions"])

    def test_rejects_non_elf(self):
        with tempfile.NamedTemporaryFile() as binary:
            binary.write(b"not executable")
            binary.flush()
            with self.assertRaises(ValueError):
                inspect(binary.name)


if __name__ == "__main__":
    unittest.main()
