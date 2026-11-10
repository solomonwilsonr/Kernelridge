"""Bounded emulation using a separate network and filesystem namespace."""
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path


def run(binary, timeout=10):
    if not 0 < timeout <= 300:
        raise ValueError("timeout must be between 0 and 300 seconds")
    path = Path(binary).resolve(strict=True)
    header = path.read_bytes()[:20]
    if len(header) < 20 or header[:4] != b"\x7fELF" or header[5] not in (1, 2):
        raise ValueError("expected an ELF binary")
    byteorder = "little" if header[5] == 1 else "big"
    if int.from_bytes(header[18:20], byteorder) != 243 or header[4] != 2:
        raise ValueError("runner supports only 64-bit RISC-V ELF")
    qemu, bwrap = shutil.which("qemu-riscv64"), shutil.which("bwrap")
    if not qemu or not bwrap:
        return {"status": "UNKNOWN", "reason": "qemu-riscv64 and bubblewrap are required; execution was not attempted", "physical_hardware_verified": False}
    with tempfile.TemporaryDirectory(prefix="kernelridge-") as directory:
        copy = Path(directory) / "artifact"
        shutil.copyfile(path, copy)
        sha = hashlib.sha256(copy.read_bytes()).hexdigest()
        command = [bwrap, "--unshare-all", "--die-with-parent", "--new-session", "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib"]
        if Path("/lib64").exists():
            command += ["--ro-bind", "/lib64", "/lib64"]
        command += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--ro-bind", str(copy), "/artifact", "--clearenv", "--setenv", "PATH", "/usr/bin", qemu, "/artifact"]
        # prlimit bounds CPU, address space, output size and child process count.
        limiter = shutil.which("prlimit")
        if not limiter:
            return {"status": "UNKNOWN", "reason": "prlimit is required"}
        command = [limiter, "--cpu=30", "--as=1073741824", "--fsize=1048576", "--nproc=32", "--"] + command
        with tempfile.TemporaryFile() as output:
            try:
                proc = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, timeout=timeout, check=False, start_new_session=True)
                code = proc.returncode
            except subprocess.TimeoutExpired:
                code = None
            output.seek(0)
            logs = output.read(65536).decode(errors="replace")
        return {"status": "SUPPORTED_IN_EMULATION" if code == 0 else "UNKNOWN", "exit_code": code, "logs": logs, "artifact_sha256": sha, "environment": "qemu-user", "physical_hardware_verified": False, "scope": "Static binary smoke execution only; no target CPU, kernel, or workload equivalence established"}
