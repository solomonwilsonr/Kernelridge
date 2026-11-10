"""Local Ed25519 attestations via the system `openssl` CLI; no Python crypto dependency.

Degrades to the existing unsigned export when `openssl` is not on PATH: never
silently claims a report is signed when it isn't.
"""
import base64
import binascii
import shutil
import subprocess
import tempfile
from pathlib import Path


def openssl_available():
    return shutil.which("openssl") is not None


def _as_bytes(message):
    return message.encode() if isinstance(message, str) else message


def keygen(private_path, public_path):
    if not openssl_available():
        return {"signed": False, "reason": "openssl not found on PATH; keypair was not generated"}
    Path(private_path).parent.mkdir(parents=True, exist_ok=True)
    Path(public_path).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(private_path)], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", str(private_path), "-pubout", "-out", str(public_path)], check=True, capture_output=True)
    return {"signed": True, "private_key": str(private_path), "public_key": str(public_path)}


def sign(message, private_path):
    if not openssl_available():
        return None
    with tempfile.NamedTemporaryFile() as msg_file, tempfile.NamedTemporaryFile() as sig_file:
        msg_file.write(_as_bytes(message))
        msg_file.flush()
        result = subprocess.run(
            ["openssl", "pkeyutl", "-sign", "-inkey", str(private_path), "-rawin", "-in", msg_file.name, "-out", sig_file.name],
            capture_output=True,
        )
        if result.returncode != 0:
            return None
        return base64.b64encode(Path(sig_file.name).read_bytes()).decode()


def verify(message, signature_b64, public_path):
    if not openssl_available() or not signature_b64:
        return False
    try:
        signature = base64.b64decode(signature_b64, validate=True)
    except (binascii.Error, ValueError):
        return False
    with tempfile.NamedTemporaryFile() as msg_file, tempfile.NamedTemporaryFile() as sig_file:
        msg_file.write(_as_bytes(message))
        msg_file.flush()
        Path(sig_file.name).write_bytes(signature)
        result = subprocess.run(
            ["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(public_path), "-rawin", "-in", msg_file.name, "-sigfile", sig_file.name],
            capture_output=True,
        )
        return result.returncode == 0
