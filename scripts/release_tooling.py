#!/usr/bin/env python3
"""AKSA Release Tooling: SBOM Generation, Checksums, Provenance, and Smoke Testing.

Provides tools for SLSA Level 3 compliance:
- Software Bill of Materials (SBOM) generation in CycloneDX 1.5 JSON format (Python + npm).
- Cryptographic SHA-256 checksum generation and verification (`SHA256SUMS.txt`).
- Automated sidecar executable smoke testing and lifecycle integrity validation.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


def get_repo_root() -> Path:
    """Resolve the repository root directory."""
    return Path(__file__).resolve().parent.parent


def generate_python_components(engine_dir: Path) -> list[dict[str, Any]]:
    """Inspect Python packages installed in environment or declared in pyproject.toml."""
    components: list[dict[str, Any]] = []

    # Try importlib.metadata first
    try:
        import importlib.metadata as meta

        installed = meta.distributions()
        seen = set()
        for dist in installed:
            name = dist.metadata.get("Name")
            if not name or name in seen:
                continue
            seen.add(name)
            version = dist.metadata.get("Version", "unknown")
            license_val = dist.metadata.get("License", "Unknown")

            components.append({
                "type": "library",
                "name": name,
                "version": version,
                "purl": f"pkg:pypi/{name.lower()}@{version}",
                "licenses": [{"license": {"name": license_val}}],
                "scope": "required",
            })
    except Exception:
        pass

    # If importlib.metadata gave nothing, fallback to parsing pyproject.toml
    if not components and engine_dir.exists():
        pyproject = engine_dir / "pyproject.toml"
        if pyproject.exists():
            for line in pyproject.read_text(encoding="utf-8").splitlines():
                line = line.strip().strip('",')
                if line and not line.startswith("[") and not line.startswith("#") and ">=" in line:
                    parts = line.split(">=")
                    pkg_name = parts[0].split("[")[0].strip()
                    pkg_ver = parts[1].strip() if len(parts) > 1 else "latest"
                    components.append({
                        "type": "library",
                        "name": pkg_name,
                        "version": pkg_ver,
                        "purl": f"pkg:pypi/{pkg_name.lower()}@{pkg_ver}",
                        "scope": "required",
                    })

    return sorted(components, key=lambda c: c["name"].lower())


def generate_npm_components(desktop_dir: Path) -> list[dict[str, Any]]:
    """Parse npm dependencies from apps/desktop/package.json."""
    components: list[dict[str, Any]] = []
    pkg_file = desktop_dir / "package.json"
    if not pkg_file.exists():
        return components

    try:
        data = json.loads(pkg_file.read_text(encoding="utf-8"))
        deps = data.get("dependencies", {})
        for name, version in deps.items():
            clean_ver = version.lstrip("^~")
            components.append({
                "type": "library",
                "name": name,
                "version": clean_ver,
                "purl": f"pkg:npm/{name}@{clean_ver}",
                "scope": "required",
            })

        dev_deps = data.get("devDependencies", {})
        for name, version in dev_deps.items():
            clean_ver = version.lstrip("^~")
            components.append({
                "type": "library",
                "name": name,
                "version": clean_ver,
                "purl": f"pkg:npm/{name}@{clean_ver}",
                "scope": "optional",
            })
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to parse package.json for SBOM: {e}\n")

    return sorted(components, key=lambda c: c["name"].lower())


def generate_cargo_components(tauri_dir: Path) -> list[dict[str, Any]]:
    """Parse Rust/Cargo dependencies from apps/desktop/src-tauri/Cargo.lock (P2-02)."""
    components: list[dict[str, Any]] = []
    lock_file = tauri_dir / "Cargo.lock"
    if not lock_file.exists():
        return components

    try:
        content = lock_file.read_text(encoding="utf-8")
        current_pkg: dict[str, str] = {}
        for line in content.splitlines():
            line = line.strip()
            if line == "[[package]]":
                if current_pkg.get("name") and current_pkg.get("version"):
                    name = current_pkg["name"]
                    ver = current_pkg["version"]
                    components.append({
                        "type": "library",
                        "name": name,
                        "version": ver,
                        "purl": f"pkg:cargo/{name}@{ver}",
                        "scope": "required",
                    })
                current_pkg = {}
            elif "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"')
                if key in ("name", "version", "source", "checksum"):
                    current_pkg[key] = val

        if current_pkg.get("name") and current_pkg.get("version"):
            name = current_pkg["name"]
            ver = current_pkg["version"]
            components.append({
                "type": "library",
                "name": name,
                "version": ver,
                "purl": f"pkg:cargo/{name}@{ver}",
                "scope": "required",
            })
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to parse Cargo.lock for SBOM: {e}\n")

    return sorted(components, key=lambda c: c["name"].lower())


def generate_cyclonedx_sbom(
    repo_root: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Generate CycloneDX 1.5 JSON SBOM for AKSA full stack (Python + npm + Cargo)."""
    root = repo_root or get_repo_root()
    engine_dir = root / "services" / "engine"
    desktop_dir = root / "apps" / "desktop"
    tauri_dir = root / "apps" / "desktop" / "src-tauri"

    py_components = generate_python_components(engine_dir)
    npm_components = generate_npm_components(desktop_dir)
    cargo_components = generate_cargo_components(tauri_dir)
    all_components = py_components + npm_components + cargo_components

    sbom: dict[str, Any] = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "tools": {
                "components": [
                    {
                        "type": "application",
                        "name": "aksa-release-tooling",
                        "version": "0.0.2",
                    }
                ]
            },
            "component": {
                "type": "application",
                "name": "aksa",
                "version": "0.0.2",
                "description": "AKSA — Autonomous Hierarchical AI Agent & PC Automation Platform",
            },
        },
        "components": all_components,
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(sbom, indent=2), encoding="utf-8")
        print(f"[OK] CycloneDX SBOM written to: {output_path} ({len(all_components)} components)")

    return sbom


def compute_file_sha256(file_path: Path) -> str:
    """Compute cryptographic SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def generate_checksums(
    artifact_paths: list[Path],
    output_path: Path | None = None,
) -> dict[str, str]:
    """Generate SHA256 checksums mapping for artifact files."""
    checksums: dict[str, str] = {}
    lines: list[str] = []

    for path in artifact_paths:
        if not path.exists():
            continue
        sha = compute_file_sha256(path)
        checksums[path.name] = sha
        lines.append(f"{sha}  {path.name}")

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"[OK] Checksums written to: {output_path} ({len(checksums)} files)")

    return checksums


def verify_checksums(checksums_file: Path) -> tuple[bool, list[str]]:
    """Verify SHA256 checksums in SHA256SUMS.txt format."""
    if not checksums_file.exists():
        return False, [f"Checksums file not found: {checksums_file}"]

    base_dir = checksums_file.parent
    errors: list[str] = []
    lines = checksums_file.read_text(encoding="utf-8").splitlines()

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            errors.append(f"Malformed checksum line: '{line}'")
            continue
        expected_sha, file_name = parts[0].strip(), parts[1].strip()
        target_file = base_dir / file_name
        if not target_file.exists():
            errors.append(f"Target artifact missing: {target_file}")
            continue

        actual_sha = compute_file_sha256(target_file)
        if actual_sha.lower() != expected_sha.lower():
            errors.append(
                f"Checksum mismatch for '{file_name}': expected {expected_sha}, got {actual_sha}"
            )

    success = len(errors) == 0
    return success, errors


def verify_sidecar_binary_format(
    executable_path: Path,
    *,
    expected_triple: str | None = None,
    min_size_bytes: int = 1_000_000,
) -> dict[str, Any]:
    """Validate executable file integrity, native binary format (ELF/Mach-O/PE), and architecture."""
    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from build_sidecar import detect_target_triple, validate_native_executable_format

    triple = expected_triple or detect_target_triple()
    info = validate_native_executable_format(
        executable_path,
        expected_triple=triple,
        min_size_bytes=min_size_bytes,
    )
    if sys.platform != "win32" and "windows" not in triple and not os.access(executable_path, os.X_OK):
        raise PermissionError(f"Required sidecar executable lacks execute permission: {executable_path}")
    return info


def smoke_test_sidecar(
    executable_path: str | Path | None = None,
    repo_root: Path | None = None,
    require_executable: bool = False,
    expected_triple: str | None = None,
) -> bool:
    """Validate binary format/architecture (when executable is targeted) and run behavioral smoke checks."""
    root = repo_root or get_repo_root()
    engine_dir = root / "services" / "engine"

    resolved_exe: Path | None = Path(executable_path) if executable_path is not None else None
    if require_executable and resolved_exe is None:
        scripts_dir = str(root / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from build_sidecar import resolve_sidecar_binary_path

        resolved_exe = resolve_sidecar_binary_path(expected_triple)

    if resolved_exe is not None:
        min_sz = 1_000_000 if require_executable else 1
        try:
            bin_info = verify_sidecar_binary_format(
                resolved_exe,
                expected_triple=expected_triple,
                min_size_bytes=min_sz,
            )
            print(
                f"[OK] Binary format verified: {resolved_exe.name} "
                f"({bin_info['format']}/{','.join(bin_info['archs'])}, {bin_info['size_bytes']:,} bytes)"
            )
        except Exception as exc:
            print(f"[ERROR] Native binary validation failed for {resolved_exe}: {exc}")
            return False
        cmd_version = [str(resolved_exe), "--version"]
        cmd_smoke = [str(resolved_exe), "--smoke-test"]
        cwd = None
        timeout_v, timeout_s = 45, 60
    else:
        # Test using python interpreter running app.main
        venv_py = engine_dir / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        python_exe = str(venv_py) if venv_py.exists() else sys.executable
        cmd_version = [python_exe, "-m", "app.main", "--version"]
        cmd_smoke = [python_exe, "-m", "app.main", "--smoke-test"]
        cwd = str(engine_dir)
        timeout_v, timeout_s = 15, 25

    print(f"Running sidecar --version check: {' '.join(cmd_version)}")
    res_v = subprocess.run(cmd_version, cwd=cwd, capture_output=True, text=True, timeout=timeout_v)
    if res_v.returncode != 0 or "AKSA Engine" not in res_v.stdout:
        print(f"[ERROR] Version check failed: code={res_v.returncode}, stdout={res_v.stdout}, stderr={res_v.stderr}")
        return False
    print(f"[OK] Version check passed: {res_v.stdout.strip()}")

    print(f"Running sidecar --smoke-test check: {' '.join(cmd_smoke)}")
    res_s = subprocess.run(cmd_smoke, cwd=cwd, capture_output=True, text=True, timeout=timeout_s)
    if res_s.returncode != 0 or "[SMOKE-TEST]" not in res_s.stdout:
        print(f"[ERROR] Smoke test failed: code={res_s.returncode}, stdout={res_s.stdout}, stderr={res_s.stderr}")
        return False
    print(f"[OK] Smoke test passed: {res_s.stdout.strip()}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="AKSA Release Tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # SBOM
    sbom_p = subparsers.add_parser("sbom", help="Generate CycloneDX SBOM")
    sbom_p.add_argument("--output", "-o", type=Path, default=None, help="Output path for JSON SBOM")

    # Checksums
    cs_p = subparsers.add_parser("checksums", help="Generate SHA-256 checksums")
    cs_p.add_argument("--artifacts", "-a", nargs="+", type=Path, required=True, help="Artifact file paths")
    cs_p.add_argument("--output", "-o", type=Path, default=None, help="Output SHA256SUMS.txt path")

    # Verify Checksums
    v_p = subparsers.add_parser("verify-checksums", help="Verify SHA256 checksums")
    v_p.add_argument("--file", "-f", type=Path, required=True, help="Path to SHA256SUMS.txt")

    # Verify Native Executable Binary Format & Arch
    vb_p = subparsers.add_parser("verify-binary", help="Verify native ELF/Mach-O/PE format and target triple arch")
    vb_p.add_argument("--executable", "-e", type=Path, required=True, help="Path to compiled sidecar binary")
    vb_p.add_argument("--triple", "-t", type=str, default=None, help="Expected Rust/Tauri target triple")

    # Smoke Test
    st_p = subparsers.add_parser("smoke-test", help="Smoke test sidecar engine binary or module")
    st_p.add_argument("--executable", "-e", type=Path, default=None, help="Path to compiled sidecar binary")
    st_p.add_argument("--triple", "-t", type=str, default=None, help="Expected target triple for binary check")
    st_p.add_argument(
        "--require-executable",
        action="store_true",
        help="Require real compiled target-triple sidecar executable (fail closed if missing or dummy)",
    )

    args = parser.parse_args()

    if args.command == "sbom":
        generate_cyclonedx_sbom(output_path=args.output)
    elif args.command == "checksums":
        generate_checksums(args.artifacts, output_path=args.output)
    elif args.command == "verify-checksums":
        ok, errors = verify_checksums(args.file)
        if not ok:
            print("❌ Checksum verification failed:")
            for err in errors:
                print(f"  - {err}")
            sys.exit(1)
        print("[OK] All checksums verified successfully!")
    elif args.command == "verify-binary":
        try:
            info = verify_sidecar_binary_format(args.executable, expected_triple=args.triple)
            print(
                f"[OK] Native binary validated: {args.executable} "
                f"({info['triple']}: {info['format']}/{','.join(info['archs'])}, {info['size_bytes']:,} bytes)"
            )
        except Exception as exc:
            print(f"[ERROR] Native binary validation failed: {exc}", file=sys.stderr)
            sys.exit(1)
    elif args.command == "smoke-test":
        ok = smoke_test_sidecar(
            args.executable,
            require_executable=args.require_executable,
            expected_triple=args.triple,
        )
        if not ok:
            print("[ERROR] Sidecar smoke test failed!")
            sys.exit(1)
        print("[OK] Sidecar smoke test passed completely!")


if __name__ == "__main__":
    main()

