#!/usr/bin/env python3
"""Cross-Platform Sidecar Binary Builder for AKSA Engine.

Freezes `services/engine` into a standalone native binary per target triple:
  - aarch64-apple-darwin (Apple Silicon macOS)
  - x86_64-apple-darwin (Intel macOS)
  - x86_64-pc-windows-msvc (Windows 64-bit)
  - x86_64-unknown-linux-gnu (Linux 64-bit)
  - aarch64-unknown-linux-gnu (Linux ARM64)

Outputs to: `apps/desktop/src-tauri/binaries/aksa-engine-<target-triple>[.exe]`
"""

from __future__ import annotations

import argparse
import os
import platform
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any

MIN_REAL_SIDECAR_BYTES = 1_000_000

SUPPORTED_TRIPLE_BINARIES: dict[str, tuple[str, str]] = {
    "aarch64-apple-darwin": ("macho", "arm64"),
    "x86_64-apple-darwin": ("macho", "x86_64"),
    "x86_64-pc-windows-msvc": ("pe", "x86_64"),
    "aarch64-pc-windows-msvc": ("pe", "arm64"),
    "x86_64-unknown-linux-gnu": ("elf", "x86_64"),
    "aarch64-unknown-linux-gnu": ("elf", "arm64"),
}


def detect_target_triple() -> str:
    """Detect current system's target triple matching Rust/Tauri conventions."""
    try:
        out = subprocess.check_output(["rustc", "-vV"], text=True, timeout=5)
        for line in out.splitlines():
            if line.startswith("host:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass

    machine = platform.machine().lower()
    if sys.platform == "win32":
        return "aarch64-pc-windows-msvc" if ("arm" in machine or "aarch64" in machine) else "x86_64-pc-windows-msvc"
    if sys.platform == "darwin":
        return "aarch64-apple-darwin" if ("arm" in machine or "aarch64" in machine) else "x86_64-apple-darwin"
    if "aarch64" in machine or "arm64" in machine:
        return "aarch64-unknown-linux-gnu"
    return "x86_64-unknown-linux-gnu"


def infer_triple_from_filename(target_path: Path) -> str | None:
    """Infer target triple from a sidecar filename when present."""
    name = target_path.name
    for triple in SUPPORTED_TRIPLE_BINARIES:
        if triple in name:
            return triple
    return None


def _parse_macho_64_header(hdr: bytes, container_size: int) -> dict[str, Any]:
    if len(hdr) < 32:
        raise RuntimeError("Header Mach-O 64-bit terpotong (< 32 bytes).")
    magic = struct.unpack_from("<I", hdr, 0)[0]
    if magic != 0xFEEDFACF:
        raise RuntimeError(f"Magic Mach-O 64-bit tidak valid: 0x{magic:08x}")
    cputype_signed, _cpusubtype, filetype, ncmds, sizeofcmds, _flags, _reserved = struct.unpack_from("<iIIIIII", hdr, 4)
    cputype = cputype_signed & 0xFFFFFFFF
    if filetype != 2:  # MH_EXECUTE
        raise RuntimeError(f"Mach-O bukan executable (filetype={filetype}, wajib MH_EXECUTE=2).")
    if ncmds < 1 or sizeofcmds == 0 or (32 + sizeofcmds) > container_size:
        raise RuntimeError("Load commands Mach-O tidak valid atau melebihi batas ukuran binary.")
    arch_map = {
        0x0100000C: "arm64",
        0x01000007: "x86_64",
        7: "x86",
    }
    arch = arch_map.get(cputype)
    if not arch:
        raise RuntimeError(f"Arsitektur CPU Mach-O tidak dikenali: 0x{cputype:08x}")
    return {"format": "macho", "arch": arch, "archs": [arch], "bits": 64, "universal": False}


def parse_native_executable_header(target_path: Path) -> dict[str, Any]:
    """Parse structural ELF, Mach-O (thin/fat), or PE headers using strict offset/table bounds."""
    file_size = target_path.stat().st_size
    if file_size <= 0:
        raise RuntimeError(f"Binary sidecar kosong (0 byte): {target_path}")

    with target_path.open("rb") as fp:
        head = fp.read(4096)

        if head.startswith(b"#!"):
            raise RuntimeError(f"Script shebang teks ditolak sebagai native executable: {target_path}")

        # 1. ELF (Linux)
        if head[:4] == b"\x7fELF":
            if len(head) < 64:
                raise RuntimeError("Header ELF terpotong (< 64 bytes).")
            ei_class, ei_data, ei_version = head[4], head[5], head[6]
            if ei_class != 2 or ei_data != 1 or ei_version != 1:
                raise RuntimeError(
                    f"ELF harus 64-bit little-endian v1 (class={ei_class}, data={ei_data}, ver={ei_version})."
                )
            (
                e_type,
                e_machine,
                e_version,
                _e_entry,
                e_phoff,
                _e_shoff,
                _e_flags,
                e_ehsize,
                e_phentsize,
                e_phnum,
                _e_shentsize,
                _e_shnum,
                _e_shstrndx,
            ) = struct.unpack_from("<HHIQQQIHHHHHH", head, 16)
            if e_version != 1 or e_ehsize != 64:
                raise RuntimeError(f"Header ELF64 tidak konsisten (e_version={e_version}, e_ehsize={e_ehsize}).")
            if e_type not in (2, 3):  # ET_EXEC or ET_DYN (PIE executable)
                raise RuntimeError(f"ELF bukan executable/PIE (e_type={e_type}).")
            if e_phentsize < 56 or e_phnum < 1 or e_phoff < 64 or (e_phoff + e_phnum * e_phentsize) > file_size:
                raise RuntimeError("Tabel program header ELF tidak valid atau keluar batas file.")
            fp.seek(e_phoff)
            ph_count = min(e_phnum, 64)
            ph_bytes = fp.read(ph_count * e_phentsize)
            if len(ph_bytes) < e_phentsize:
                raise RuntimeError("Gagal membaca program header ELF.")
            has_pt_load = any(
                struct.unpack_from("<I", ph_bytes, idx * e_phentsize)[0] == 1
                for idx in range(ph_count)
            )
            if not has_pt_load:
                raise RuntimeError("ELF tidak memiliki segmen PT_LOAD yang sah.")
            mach_map = {62: "x86_64", 183: "arm64", 3: "x86", 40: "arm"}
            arch = mach_map.get(e_machine)
            if not arch:
                raise RuntimeError(f"Arsitektur ELF e_machine tidak didukung: {e_machine}")
            return {"format": "elf", "arch": arch, "archs": [arch], "bits": 64, "e_type": e_type}

        # 2. Thin 64-bit Mach-O (macOS)
        magic_le = struct.unpack_from("<I", head, 0)[0] if len(head) >= 4 else 0
        if magic_le == 0xFEEDFACF:
            return _parse_macho_64_header(head, file_size)

        # 3. Universal Fat Mach-O (macOS) — reject Java .class collision via strict slice bounds & Mach-O slice check
        magic_be = struct.unpack_from(">I", head, 0)[0] if len(head) >= 8 else 0
        if magic_be in (0xCAFEBABE, 0xCAFEBABF):
            nfat_arch = struct.unpack_from(">I", head, 4)[0]
            is_fat64 = magic_be == 0xCAFEBABF
            entry_fmt = ">iiQQII" if is_fat64 else ">iiIII"
            entry_sz = struct.calcsize(entry_fmt)
            if nfat_arch < 1 or nfat_arch > 16 or (8 + nfat_arch * entry_sz) > len(head):
                raise RuntimeError(f"Header Universal Mach-O tidak valid (nfat_arch={nfat_arch}).")
            archs: list[str] = []
            for idx in range(nfat_arch):
                unpacked = struct.unpack_from(entry_fmt, head, 8 + idx * entry_sz)
                fat_cpu = unpacked[0] & 0xFFFFFFFF
                sl_off = unpacked[2]
                sl_size = unpacked[3]
                if sl_off < (8 + nfat_arch * entry_sz) or sl_size < 32 or (sl_off + sl_size) > file_size:
                    raise RuntimeError("Offset/ukuran slice Universal Mach-O tidak valid.")
                fp.seek(sl_off)
                sl_hdr = fp.read(32)
                sl_info = _parse_macho_64_header(sl_hdr, sl_size)
                expected_fat_arch = {0x0100000C: "arm64", 0x01000007: "x86_64"}.get(fat_cpu)
                if expected_fat_arch != sl_info["arch"]:
                    raise RuntimeError("Ketidakcocokan arsitektur slice Universal Mach-O.")
                archs.append(sl_info["arch"])
            return {"format": "macho", "arch": archs[0], "archs": archs, "bits": 64, "universal": True}

        # 4. PE/COFF (Windows .exe)
        if head[:2] == b"MZ" and len(head) >= 0x40:
            e_lfanew = struct.unpack_from("<I", head, 0x3C)[0]
            if e_lfanew < 0x40 or (e_lfanew + 24) > file_size:
                raise RuntimeError(f"Offset header PE e_lfanew tidak valid: {e_lfanew}")
            fp.seek(e_lfanew)
            pe_hdr = fp.read(256)
            if len(pe_hdr) < 26 or pe_hdr[:4] != b"PE\x00\x00":
                raise RuntimeError("Signature PE\\0\\0 tidak ditemukan pada offset e_lfanew.")
            (
                machine,
                num_sections,
                _time_stamp,
                _sym_ptr,
                _num_syms,
                opt_size,
                characteristics,
            ) = struct.unpack_from("<HHIIIHH", pe_hdr, 4)
            if num_sections < 1 or opt_size < 24:
                raise RuntimeError("Struktur COFF header PE tidak valid.")
            if (e_lfanew + 24 + opt_size + num_sections * 40) > file_size:
                raise RuntimeError("Tabel section PE melampaui ukuran berkas.")
            if not (characteristics & 0x0002):  # IMAGE_FILE_EXECUTABLE_IMAGE
                raise RuntimeError("Berkas PE tidak memiliki flag IMAGE_FILE_EXECUTABLE_IMAGE.")
            if characteristics & 0x2000:  # IMAGE_FILE_DLL
                raise RuntimeError("Berkas PE berupa DLL, bukan executable mandiri.")
            opt_magic = struct.unpack_from("<H", pe_hdr, 24)[0]
            if opt_magic != 0x020B:  # PE32+ (64-bit)
                raise RuntimeError(f"Executable PE harus PE32+ 64-bit (opt_magic=0x{opt_magic:04x}).")
            mach_map = {0x8664: "x86_64", 0xAA64: "arm64", 0x014C: "x86"}
            arch = mach_map.get(machine)
            if not arch:
                raise RuntimeError(f"Arsitektur mesin PE tidak didukung: 0x{machine:04x}")
            return {"format": "pe", "arch": arch, "archs": [arch], "bits": 64}

    raise RuntimeError(f"Format binary tidak valid (wajib ELF/Mach-O/PE asli, bukan teks/stub): {target_path}")


def validate_native_executable_format(
    target_path: Path,
    *,
    expected_triple: str | None = None,
    min_size_bytes: int = MIN_REAL_SIDECAR_BYTES,
) -> dict[str, Any]:
    """Validate regular file, non-symlink, size threshold, and structural binary format + architecture."""
    if not target_path.exists() or target_path.is_symlink() or not target_path.is_file():
        raise FileNotFoundError(
            f"Binary sidecar target-triple tidak ditemukan atau bukan file reguler: {target_path}"
        )
    size_bytes = target_path.stat().st_size
    if size_bytes < min_size_bytes:
        raise RuntimeError(
            f"Ukuran binary sidecar '{target_path}' terlalu kecil ({size_bytes} bytes < {min_size_bytes}); "
            "wrapper/dummy kosong ditolak untuk build & Cargo check."
        )

    triple = expected_triple or infer_triple_from_filename(target_path) or detect_target_triple()
    if triple not in SUPPORTED_TRIPLE_BINARIES:
        raise ValueError(f"Target triple sidecar tidak dikenal atau tidak didukung: {triple}")
    expected_fmt, expected_arch = SUPPORTED_TRIPLE_BINARIES[triple]

    info = parse_native_executable_header(target_path)
    if info["format"] != expected_fmt:
        raise RuntimeError(
            f"Format binary sidecar tidak sesuai target '{triple}': "
            f"ditemukan '{info['format']}', wajib '{expected_fmt}'."
        )
    if expected_arch not in info["archs"]:
        raise RuntimeError(
            f"Arsitektur binary sidecar tidak sesuai target '{triple}': "
            f"ditemukan {info['archs']}, wajib '{expected_arch}'."
        )

    return {**info, "triple": triple, "size_bytes": size_bytes}


def resolve_sidecar_binary_path(target_triple: str | None = None) -> Path:
    """Resolve the expected Tauri target-triple sidecar binary path."""
    repo_root = Path(__file__).resolve().parent.parent
    binaries_dir = repo_root / "apps" / "desktop" / "src-tauri" / "binaries"
    binaries_dir.mkdir(parents=True, exist_ok=True)
    triple = target_triple or detect_target_triple()
    ext = ".exe" if "windows" in triple or (target_triple is None and sys.platform == "win32") else ""
    return binaries_dir / f"aksa-engine-{triple}{ext}"


def verify_sidecar_binary(
    target_path: Path,
    *,
    expected_triple: str | None = None,
    min_size_bytes: int = MIN_REAL_SIDECAR_BYTES,
) -> Path:
    """Verify target-triple sidecar binary exists, matches native format/arch, is executable, and is non-stub."""
    info = validate_native_executable_format(
        target_path,
        expected_triple=expected_triple,
        min_size_bytes=min_size_bytes,
    )
    if sys.platform != "win32" and "windows" not in str(info["triple"]):
        mode = target_path.stat().st_mode
        if not (mode & 0o111):
            target_path.chmod(mode | 0o755)
        if not os.access(target_path, os.X_OK):
            raise PermissionError(f"Binary sidecar tidak memiliki izin eksekusi: {target_path}")
    print(
        f"[OK] Sidecar verified: {target_path} "
        f"({info['size_bytes']:,} bytes, {info['format']}/{','.join(info['archs'])}, executable)"
    )
    return target_path


def build_sidecar(
    target_triple: str | None = None,
    dry_run: bool = False,
    one_file: bool = True,
    verify: bool = True,
) -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    engine_dir = repo_root / "services" / "engine"
    binaries_dir = repo_root / "apps" / "desktop" / "src-tauri" / "binaries"
    binaries_dir.mkdir(parents=True, exist_ok=True)
    work_dir = repo_root / "build" / "pyinstaller-work"
    spec_dir = repo_root / "build" / "pyinstaller-spec"

    triple = target_triple or detect_target_triple()
    target_path = resolve_sidecar_binary_path(triple)

    hidden_imports = [
        "aiosqlite",
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "websockets",
        "fastapi",
        "starlette",
        "pydantic",
        "pydantic_settings",
        "httpx",
        "keyring",
        "keyring.backends",
        "cryptography",
        "jsonschema",
        "numpy",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "openpyxl",
        "docx",
        "pptx",
        "pymupdf",
        "fitz",
        "reportlab",
        "watchdog",
        "aiogram",
    ]

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--paths",
        str(engine_dir),
        "--collect-submodules",
        "app",
        "--collect-submodules",
        "keyring.backends",
        "--name",
        f"aksa-engine-{triple}",
        "--distpath",
        str(binaries_dir),
        "--workpath",
        str(work_dir / triple),
        "--specpath",
        str(spec_dir),
    ]

    if one_file:
        cmd.append("--onefile")

    for mod in hidden_imports:
        cmd.extend(["--hidden-import", mod])

    # Entry point
    entry_point = engine_dir / "app" / "main.py"
    cmd.append(str(entry_point))

    print("===============================================================")
    print("  AKSA Engine Sidecar Builder")
    print(f"  Target Triple : {triple}")
    print(f"  Target Binary : {target_path}")
    print(f"  Entry Point   : {entry_point}")
    print("===============================================================")

    if dry_run:
        print(f"[DRY-RUN] Command:\n{' '.join(cmd)}")
        return target_path

    # Verify PyInstaller is installed
    try:
        import PyInstaller  # type: ignore # noqa: F401
    except ImportError:
        print(f"ERROR: PyInstaller is not installed in the current environment ({sys.executable}).")
        print("Install it with: pip install pyinstaller")
        sys.exit(1)

    work_dir.mkdir(parents=True, exist_ok=True)
    spec_dir.mkdir(parents=True, exist_ok=True)
    print("Running PyInstaller build...")
    subprocess.run(cmd, cwd=str(engine_dir), check=True)
    print(f"[OK] Sidecar binary built successfully at: {target_path}")
    if verify:
        verify_sidecar_binary(target_path, expected_triple=triple)
    return target_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build AKSA Engine Sidecar binary for Tauri v2")
    parser.add_argument("--triple", type=str, default=None, help="Target triple (e.g. aarch64-apple-darwin)")
    parser.add_argument("--dry-run", action="store_true", help="Print PyInstaller command without building")
    parser.add_argument("--onedir", action="store_true", help="Build directory instead of single-file executable")
    parser.add_argument("--verify-only", action="store_true", help="Verify existing target-triple sidecar binary")

    args = parser.parse_args()
    if args.verify_only:
        path = resolve_sidecar_binary_path(args.triple)
        try:
            verify_sidecar_binary(path, expected_triple=args.triple)
        except Exception as exc:
            print(f"❌ Sidecar verification failed: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    build_sidecar(
        target_triple=args.triple,
        dry_run=args.dry_run,
        one_file=not args.onedir,
    )


if __name__ == "__main__":
    main()

