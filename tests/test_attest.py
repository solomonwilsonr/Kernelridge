import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from kernelridge import attest


class AttestDegradeTests(unittest.TestCase):
    def test_keygen_degrades_without_openssl(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('kernelridge.attest.shutil.which', return_value=None):
                result = attest.keygen(Path(directory) / 'priv.pem', Path(directory) / 'pub.pem')
            self.assertFalse(result['signed'])
            self.assertIn('reason', result)
            self.assertFalse((Path(directory) / 'priv.pem').exists())

    def test_sign_degrades_without_openssl(self):
        with patch('kernelridge.attest.shutil.which', return_value=None):
            self.assertIsNone(attest.sign('deadbeef', '/nonexistent/priv.pem'))

    def test_verify_degrades_without_openssl(self):
        with patch('kernelridge.attest.shutil.which', return_value=None):
            self.assertFalse(attest.verify('deadbeef', 'c2lnbmF0dXJl', '/nonexistent/pub.pem'))

    def test_verify_rejects_malformed_signature(self):
        self.assertFalse(attest.verify('deadbeef', 'not-valid-base64!!', '/nonexistent/pub.pem'))

    def test_verify_rejects_missing_signature(self):
        self.assertFalse(attest.verify('deadbeef', None, '/nonexistent/pub.pem'))


@unittest.skipUnless(attest.openssl_available(), "openssl not available in this environment")
class AttestRoundTripTests(unittest.TestCase):
    def test_keygen_sign_verify_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            priv, pub = Path(directory) / 'priv.pem', Path(directory) / 'pub.pem'
            keys = attest.keygen(priv, pub)
            self.assertTrue(keys['signed'])
            self.assertTrue(priv.exists())
            self.assertTrue(pub.exists())
            signature = attest.sign('deadbeef' * 8, priv)
            self.assertIsNotNone(signature)
            self.assertTrue(attest.verify('deadbeef' * 8, signature, pub))
            self.assertFalse(attest.verify('tampered' * 8, signature, pub))

    def test_verify_fails_with_wrong_public_key(self):
        with tempfile.TemporaryDirectory() as directory:
            priv_a, pub_a = Path(directory) / 'a.priv', Path(directory) / 'a.pub'
            priv_b, pub_b = Path(directory) / 'b.priv', Path(directory) / 'b.pub'
            attest.keygen(priv_a, pub_a)
            attest.keygen(priv_b, pub_b)
            signature = attest.sign('deadbeef', priv_a)
            self.assertFalse(attest.verify('deadbeef', signature, pub_b))


if __name__ == '__main__':
    unittest.main()
