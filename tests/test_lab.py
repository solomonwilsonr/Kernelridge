import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from kernelridge.lab import run


class LabTests(unittest.TestCase):
    def test_missing_executor_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / 'app'
            header = bytearray(20)
            header[:6] = b'\x7fELF\x02\x01'
            header[18:20] = (243).to_bytes(2, 'little')
            binary.write_bytes(header)
            with patch('kernelridge.lab.shutil.which', return_value=None):
                result = run(binary)
            self.assertEqual(result['status'], 'UNKNOWN')
            self.assertFalse(result['physical_hardware_verified'])

    def test_rejects_non_elf(self):
        with tempfile.NamedTemporaryFile() as binary:
            binary.write(b'not executable')
            binary.flush()
            with self.assertRaises(ValueError):
                run(binary.name)
