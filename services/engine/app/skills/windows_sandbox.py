"""Windows AppContainer + Suspended Job Object OS Sandbox (AKSA-SEC-003-R5).

Enforces kernel-level containment on Windows without running any untrusted code
prior to isolation attachment:
1. Creates a zero-capability AppContainer profile (``CapabilityCount = 0`` ->
   Windows Filtering Platform blocks all network access and user profile paths).
2. Grants explicit DACL access to the AppContainer SID ONLY for ``workspace``
   (read/write) and ``read_roots`` (read/execute). Revokes ACEs on cleanup.
3. Spawns the target process with ``CREATE_SUSPENDED | EXTENDED_STARTUPINFO_PRESENT``
   and ``PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES``.
4. Attaches the suspended process to a Windows Job Object enforcing
   ``ACTIVE_PROCESS = 1`` (no child processes), ``PROCESS_MEMORY`` limit (512 MB),
   and ``KILL_ON_JOB_CLOSE`` BEFORE calling ``ResumeThread``.
5. Any setup or attachment error terminates the child immediately and raises
   ``PermissionError`` (fail-closed — never falls back to unsandboxed execution).
"""

from __future__ import annotations

import ctypes
import logging
import os
import re
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger("aksa.sandbox.windows")

_DRIVE_ROOT_RE = re.compile(r"^[a-z]:/?$")
_BROAD_POSIX_PREFIXES = {
    "",
    "/",
    "/users",
    "/home",
    "/root",
    "/etc",
    "/var",
    "/tmp",
    "/private",
    "/private/etc",
    "/private/var",
    "/library",
    "/system",
    "/applications",
    "/program files",
    "/program files (x86)",
    "/programdata",
    "/windows",
}


class WindowsSandboxError(PermissionError):
    """Raised when Windows AppContainer or Job Object confinement fails (fail-closed)."""


def redact_path_for_log(path: Path) -> str:
    """Return a path summary safe for audit logs without exposing full user directories."""
    name = path.name or path.drive or "root"
    return f"<path:{name}:depth={len(path.parts)}>"


def _normalize_posix_lower(raw: str | Path) -> str:
    s = str(raw).replace("\\", "/").rstrip("/").lower()
    return s or "/"


def validate_sandbox_read_root(root: Path, *, allow_system_usr: bool = False) -> Path:
    """Reject overly broad filesystem, drive, or user-profile roots before ACL or bind mount."""
    raw_norm = _normalize_posix_lower(root)
    if _DRIVE_ROOT_RE.match(raw_norm):
        raise WindowsSandboxError(
            f"Root baca sandbox terlalu luas dan ditolak: {redact_path_for_log(root)}"
        )

    resolved = root.resolve(strict=False)
    if resolved == resolved.parent or len(resolved.parts) <= 1:
        raise WindowsSandboxError(
            f"Root baca sandbox tidak boleh berupa drive/filesystem root: {redact_path_for_log(resolved)}"
        )

    res_norm = _normalize_posix_lower(resolved)
    if _DRIVE_ROOT_RE.match(res_norm):
        raise WindowsSandboxError(
            f"Root baca sandbox terlalu luas dan ditolak: {redact_path_for_log(resolved)}"
        )

    broad_set = set(_BROAD_POSIX_PREFIXES)
    if not allow_system_usr:
        broad_set.add("/usr")

    # Add dynamic user home & OS profile dirs if available
    try:
        home = Path.home().resolve(strict=False)
        broad_set.add(_normalize_posix_lower(home))
        if home.parent != home:
            broad_set.add(_normalize_posix_lower(home.parent))
    except Exception:
        pass

    for env_key in ("USERPROFILE", "HOME", "PUBLIC", "ALLUSERSPROFILE", "WINDIR", "SYSTEMROOT"):
        val = os.environ.get(env_key)
        if val:
            broad_set.add(_normalize_posix_lower(val))

    if raw_norm in broad_set or res_norm in broad_set:
        raise WindowsSandboxError(
            f"Root baca sandbox terlalu luas untuk ACL AppContainer: {redact_path_for_log(resolved)}"
        )

    # Reject <drive>:/users, <drive>:/windows, <drive>:/program files, etc. on Windows (even if inspected on POSIX)
    broad_win_re = r"^[a-z]:/(users|windows|programdata|program files|program files \(x86\))$"
    if re.match(broad_win_re, raw_norm) or re.match(broad_win_re, res_norm):
        raise WindowsSandboxError(
            f"Root sistem/profil pengguna terlalu luas dan ditolak: {redact_path_for_log(resolved)}"
        )

    return resolved


def _escape_env_block(env: dict[str, str]) -> ctypes.Array[ctypes.c_wchar]:
    """Encode environment dict as double-null-terminated UTF-16 block for CreateProcessW."""
    merged = dict(env)
    if sys.platform == "win32":
        if "SYSTEMROOT" not in merged:
            merged["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
        if "WINDIR" not in merged:
            merged["WINDIR"] = os.environ.get("WINDIR", merged["SYSTEMROOT"])
    items = [f"{k}={v}" for k, v in merged.items()]
    block = "\0".join(items) + "\0\0"
    return ctypes.create_unicode_buffer(block)


def _win_last_error() -> int:
    fn = getattr(ctypes, "get_last_error", None)
    return int(fn()) if fn else 0


def run_windows_appcontainer_sandboxed(
    cmd: list[str],
    cwd: Path,
    env: dict[str, str],
    workspace: Path,
    read_roots: list[Path] | None = None,
    timeout: float = 15.0,
    max_output_bytes: int = 1024 * 1024,
    *,
    required_read_roots: list[Path] | None = None,
    optional_read_roots: list[Path] | None = None,
    stdin_bytes: bytes | None = None,
    read_only_workspace: bool = False,
    max_stderr_bytes: int | None = None,
    stderr_retain_bytes: int | None = None,
    abort_on_output_limit: bool = False,
) -> dict[str, Any]:
    """Execute ``cmd`` inside a zero-capability Windows AppContainer + Job Object.

    Security invariants:
    - Overly broad roots (drive roots, ``C:\\Users``, ``/``, user home) are rejected fail-closed.
    - All ``required_read_roots`` MUST exist and receive explicit R/X ACL grants (fail-closed).
    - When ``read_only_workspace=True``, workspace ACL is restricted strictly to ``FILE_READ_EXEC``.
    - ``PROC_THREAD_ATTRIBUTE_HANDLE_LIST`` restricts child handle inheritance strictly to
      configured stdio pipe handles.
    """
    if sys.platform != "win32":
        raise WindowsSandboxError("Windows AppContainer sandbox hanya dapat dijalankan di Windows.")

    ws_resolved = validate_sandbox_read_root(workspace)
    req_candidates = (
        list(read_roots or [])
        if required_read_roots is None
        else [*list(read_roots or []), *required_read_roots]
    )
    opt_candidates = list(optional_read_roots or [])

    validated_required: list[Path] = []
    seen_roots: set[Path] = {ws_resolved}
    for root in req_candidates:
        rp = validate_sandbox_read_root(root)
        if rp not in seen_roots:
            seen_roots.add(rp)
            validated_required.append(rp)

    validated_optional: list[Path] = []
    for root in opt_candidates:
        rp = validate_sandbox_read_root(root)
        if rp not in seen_roots:
            seen_roots.add(rp)
            validated_optional.append(rp)

    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    userenv = ctypes.WinDLL("userenv", use_last_error=True)

    # Constants
    CREATE_SUSPENDED = 0x00000004
    CREATE_NO_WINDOW = 0x08000000
    CREATE_UNICODE_ENVIRONMENT = 0x00000400
    EXTENDED_STARTUPINFO_PRESENT = 0x00080000
    STARTF_USESTDHANDLES = 0x00000100
    PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x00020002
    PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES = 0x00020009
    HANDLE_FLAG_INHERIT = 0x00000001
    WAIT_TIMEOUT = 0x00000102
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
    JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
    JobObjectExtendedLimitInformation = 9

    SE_FILE_OBJECT = 1
    DACL_SECURITY_INFORMATION = 0x00000004
    GRANT_ACCESS = 1
    REVOKE_ACCESS = 4
    OBJECT_INHERIT_ACE = 0x1
    CONTAINER_INHERIT_ACE = 0x2
    FILE_ALL_ACCESS = 0x001F01FF
    FILE_READ_EXEC = 0x001200A9  # FILE_GENERIC_READ | FILE_GENERIC_EXECUTE
    TRUSTEE_IS_SID = 0
    TRUSTEE_IS_UNKNOWN = 0

    class SECURITY_ATTRIBUTES(ctypes.Structure):
        _fields_ = [
            ("nLength", wintypes.DWORD),
            ("lpSecurityDescriptor", ctypes.c_void_p),
            ("bInheritHandle", wintypes.BOOL),
        ]

    class SECURITY_CAPABILITIES(ctypes.Structure):
        _fields_ = [
            ("AppContainerSid", ctypes.c_void_p),
            ("Capabilities", ctypes.c_void_p),
            ("CapabilityCount", wintypes.DWORD),
            ("Reserved", wintypes.DWORD),
        ]

    class STARTUPINFOW(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR),
            ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD),
            ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD),
            ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD),
            ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD),
            ("cbReserved2", wintypes.WORD),
            ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
            ("hStdInput", wintypes.HANDLE),
            ("hStdOutput", wintypes.HANDLE),
            ("hStdError", wintypes.HANDLE),
        ]

    class STARTUPINFOEXW(ctypes.Structure):
        _fields_ = [
            ("StartupInfo", STARTUPINFOW),
            ("lpAttributeList", ctypes.c_void_p),
        ]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("hProcess", wintypes.HANDLE),
            ("hThread", wintypes.HANDLE),
            ("dwProcessId", wintypes.DWORD),
            ("dwThreadId", wintypes.DWORD),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    class TRUSTEE_W(ctypes.Structure):
        _fields_ = [
            ("pMultipleTrustee", ctypes.c_void_p),
            ("MultipleTrusteeOperation", ctypes.c_int),
            ("TrusteeForm", ctypes.c_int),
            ("TrusteeType", ctypes.c_int),
            ("ptstrName", ctypes.c_void_p),
        ]

    class EXPLICIT_ACCESS_W(ctypes.Structure):
        _fields_ = [
            ("grfAccessPermissions", wintypes.DWORD),
            ("grfAccessMode", ctypes.c_int),
            ("grfInheritance", wintypes.DWORD),
            ("Trustee", TRUSTEE_W),
        ]

    class ACL_SIZE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("AceCount", wintypes.DWORD),
            ("AclBytesInUse", wintypes.DWORD),
            ("AclBytesFree", wintypes.DWORD),
        ]

    class ACE_HEADER(ctypes.Structure):
        _fields_ = [
            ("AceType", ctypes.c_uint8),
            ("AceFlags", ctypes.c_uint8),
            ("AceSize", ctypes.c_uint16),
        ]

    class ACCESS_ALLOWED_ACE_PREFIX(ctypes.Structure):
        _fields_ = [
            ("Header", ACE_HEADER),
            ("Mask", wintypes.DWORD),
        ]

    # Configure signatures carefully for 64-bit pointers/handles
    userenv.CreateAppContainerProfile.argtypes = [
        wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p),
    ]
    userenv.CreateAppContainerProfile.restype = ctypes.c_long
    userenv.DeleteAppContainerProfile.argtypes = [wintypes.LPCWSTR]
    userenv.DeleteAppContainerProfile.restype = ctypes.c_long
    userenv.DeriveAppContainerSidFromAppContainerName.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
    userenv.DeriveAppContainerSidFromAppContainerName.restype = ctypes.c_long

    advapi32.FreeSid.argtypes = [ctypes.c_void_p]
    advapi32.FreeSid.restype = ctypes.c_void_p
    advapi32.GetNamedSecurityInfoW.argtypes = [
        wintypes.LPCWSTR, ctypes.c_int, wintypes.DWORD,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi32.GetNamedSecurityInfoW.restype = wintypes.DWORD
    advapi32.SetEntriesInAclW.argtypes = [
        wintypes.ULONG, ctypes.POINTER(EXPLICIT_ACCESS_W), ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)
    ]
    advapi32.SetEntriesInAclW.restype = wintypes.DWORD
    advapi32.SetNamedSecurityInfoW.argtypes = [
        wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    ]
    advapi32.SetNamedSecurityInfoW.restype = wintypes.DWORD
    is_real_windll = isinstance(ctypes.WinDLL, type) and isinstance(advapi32, ctypes.WinDLL)
    if is_real_windll:
        advapi32.ConvertStringSidToSidW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
        advapi32.ConvertStringSidToSidW.restype = wintypes.BOOL
        advapi32.GetAclInformation.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.c_int,
        ]
        advapi32.GetAclInformation.restype = wintypes.BOOL
        advapi32.GetAce.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)]
        advapi32.GetAce.restype = wintypes.BOOL
        advapi32.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        advapi32.EqualSid.restype = wintypes.BOOL

    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateJobObject.restype = wintypes.BOOL
    kernel32.InitializeProcThreadAttributeList.argtypes = [
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_size_t)
    ]
    kernel32.InitializeProcThreadAttributeList.restype = wintypes.BOOL
    kernel32.UpdateProcThreadAttribute.argtypes = [
        ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t,
        ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p,
    ]
    kernel32.UpdateProcThreadAttribute.restype = wintypes.BOOL
    kernel32.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
    kernel32.DeleteProcThreadAttributeList.restype = None
    kernel32.CreatePipe.argtypes = [
        ctypes.POINTER(wintypes.HANDLE), ctypes.POINTER(wintypes.HANDLE),
        ctypes.POINTER(SECURITY_ATTRIBUTES), wintypes.DWORD,
    ]
    kernel32.CreatePipe.restype = wintypes.BOOL
    kernel32.SetHandleInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
    kernel32.SetHandleInformation.restype = wintypes.BOOL
    kernel32.CreateProcessW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
        wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
        ctypes.POINTER(STARTUPINFOEXW), ctypes.POINTER(PROCESS_INFORMATION),
    ]
    kernel32.CreateProcessW.restype = wintypes.BOOL
    kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel32.ResumeThread.restype = wintypes.DWORD
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    container_name = f"aksa.skill.{uuid.uuid4().hex[:16]}"
    app_container_sid = ctypes.c_void_p()
    profile_created = False
    modified_acls: list[tuple[Path, bool]] = []
    h_job = None
    pi = PROCESS_INFORMATION()
    attr_buf = None
    attr_initialized = False
    handles_to_close: list[Any] = []
    engine_root_dir = Path(__file__).resolve().parent.parent.parent

    def _modify_acl(
        target_path: Path,
        access_mask: int,
        mode: int,
        *,
        target_sid: Any = None,
        inherit: bool = True,
    ) -> bool:
        path_str = str(target_path.resolve())
        old_dacl = ctypes.c_void_p()
        sd = ctypes.c_void_p()
        err = advapi32.GetNamedSecurityInfoW(
            path_str, SE_FILE_OBJECT, DACL_SECURITY_INFORMATION,
            None, None, ctypes.byref(old_dacl), None, ctypes.byref(sd),
        )
        if err != 0:
            return False
        new_dacl = ctypes.c_void_p()
        try:
            ea = EXPLICIT_ACCESS_W()
            ea.grfAccessPermissions = access_mask
            ea.grfAccessMode = mode
            ea.grfInheritance = (OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE) if inherit else 0
            ea.Trustee.MultipleTrusteeOperation = 0
            ea.Trustee.TrusteeForm = TRUSTEE_IS_SID
            ea.Trustee.TrusteeType = TRUSTEE_IS_UNKNOWN
            ea.Trustee.ptstrName = app_container_sid if target_sid is None else target_sid
            err = advapi32.SetEntriesInAclW(1, ctypes.byref(ea), old_dacl, ctypes.byref(new_dacl))
            if err != 0:
                return False
            err = advapi32.SetNamedSecurityInfoW(
                ctypes.create_unicode_buffer(path_str),
                SE_FILE_OBJECT, DACL_SECURITY_INFORMATION,
                None, None, new_dacl, None,
            )
            return err == 0
        finally:
            if new_dacl:
                kernel32.LocalFree(new_dacl)
            if sd:
                kernel32.LocalFree(sd)

    def _dacl_has_sid_rx(old_dacl: ctypes.c_void_p, target_sid: ctypes.c_void_p) -> bool:
        if not old_dacl or not target_sid:
            return False
        size_info = ACL_SIZE_INFORMATION()
        if not advapi32.GetAclInformation(old_dacl, ctypes.byref(size_info), ctypes.sizeof(size_info), 2):
            return False
        for idx in range(int(size_info.AceCount)):
            ace_ptr = ctypes.c_void_p()
            if not advapi32.GetAce(old_dacl, idx, ctypes.byref(ace_ptr)) or not ace_ptr.value:
                continue
            ace = ACCESS_ALLOWED_ACE_PREFIX.from_address(ace_ptr.value)
            # ACCESS_ALLOWED_ACE_TYPE == 0; skip INHERIT_ONLY_ACE (0x8)
            if ace.Header.AceType != 0 or (ace.Header.AceFlags & 0x8):
                continue
            if (ace.Header.AceFlags & (OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE)) != (
                OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE
            ):
                continue
            if (ace.Mask & FILE_READ_EXEC) != FILE_READ_EXEC:
                continue
            sid_addr = ctypes.c_void_p(ace_ptr.value + ctypes.sizeof(ACCESS_ALLOWED_ACE_PREFIX))
            if advapi32.EqualSid(sid_addr, target_sid):
                return True
        return False

    def _is_global_python_runtime_root(target_path: Path) -> bool:
        if not is_real_windll:
            return False
        try:
            resolved = target_path.resolve()
            base_py = Path(sys.base_prefix).resolve()
            if resolved != base_py:
                return False
            if resolved == ws_resolved or resolved == engine_root_dir:
                return False
            return (resolved / "Lib" / "os.py").is_file() or (resolved / "python.exe").is_file()
        except Exception:
            return False

    def _ensure_global_python_runtime_rx(target_path: Path) -> bool:
        """Grant idempotent ALL APPLICATION PACKAGES (S-1-15-2-1) RX once on read-only Python base runtime."""
        pkg_sid = ctypes.c_void_p()
        if not advapi32.ConvertStringSidToSidW("S-1-15-2-1", ctypes.byref(pkg_sid)) or not pkg_sid.value:
            return False
        try:
            old_dacl = ctypes.c_void_p()
            sd = ctypes.c_void_p()
            err = advapi32.GetNamedSecurityInfoW(
                str(target_path.resolve()),
                SE_FILE_OBJECT,
                DACL_SECURITY_INFORMATION,
                None,
                None,
                ctypes.byref(old_dacl),
                None,
                ctypes.byref(sd),
            )
            already_present = False
            try:
                if err == 0 and old_dacl.value:
                    already_present = _dacl_has_sid_rx(old_dacl, pkg_sid)
            finally:
                if sd:
                    kernel32.LocalFree(sd)
            if already_present:
                return True
            return _modify_acl(target_path, FILE_READ_EXEC, GRANT_ACCESS, target_sid=pkg_sid, inherit=True)
        finally:
            kernel32.LocalFree(pkg_sid)

    def _grant_read_root(root: Path) -> tuple[bool, bool]:
        """Grant RX for read root cleanly, scoping engine_root & caching global Python base_prefix."""
        if _is_global_python_runtime_root(root) and _ensure_global_python_runtime_rx(root):
            return True, False  # Persistent runtime RX; no per-run revoke tree-walk needed
        if is_real_windll and root == engine_root_dir and (engine_root_dir / "app" / "__init__.py").is_file():
            app_dir = engine_root_dir / "app"
            ok_root = _modify_acl(engine_root_dir, FILE_READ_EXEC, GRANT_ACCESS, inherit=False)
            if not ok_root:
                return False, False
            modified_acls.append((engine_root_dir, False))
            ok_app = _modify_acl(app_dir, FILE_READ_EXEC, GRANT_ACCESS, inherit=True)
            if not ok_app:
                return False, False
            modified_acls.append((app_dir, True))
            return True, True
        ok_std = _modify_acl(root, FILE_READ_EXEC, GRANT_ACCESS, inherit=True)
        if ok_std:
            modified_acls.append((root, True))
        return ok_std, ok_std

    try:
        # 1. Create zero-capability AppContainer (network + arbitrary user dirs denied by kernel)
        hr = userenv.CreateAppContainerProfile(
            container_name, "AKSA Skill Sandbox", "Isolated execution",
            None, 0, ctypes.byref(app_container_sid),
        )
        if hr == 0:
            profile_created = True
        elif hr == -2147024713:  # HRESULT_FROM_WIN32(ERROR_ALREADY_EXISTS)
            hr = userenv.DeriveAppContainerSidFromAppContainerName(
                container_name, ctypes.byref(app_container_sid)
            )
            if hr != 0:
                raise WindowsSandboxError(f"DeriveAppContainerSid gagal: HRESULT {hr:#x}")
        else:
            raise WindowsSandboxError(f"CreateAppContainerProfile gagal: HRESULT {hr:#x}")

        # 2. Grant workspace R/W (or strictly R/X when read_only_workspace=True),
        #    required_read_roots R/X ACL (fail-closed), and optional_read_roots R/X ACL.
        ws_access_mask = FILE_READ_EXEC if read_only_workspace else FILE_ALL_ACCESS
        if not _modify_acl(ws_resolved, ws_access_mask, GRANT_ACCESS):
            logger.warning(
                "windows_sandbox.acl_workspace_denied target=%s",
                redact_path_for_log(ws_resolved),
            )
            raise WindowsSandboxError(
                f"Gagal memasang ACL AppContainer pada workspace {redact_path_for_log(ws_resolved)}."
            )
        modified_acls.append((ws_resolved, True))

        req_granted = 0
        for root in validated_required:
            if not root.exists():
                logger.warning(
                    "windows_sandbox.acl_required_missing target=%s",
                    redact_path_for_log(root),
                )
                raise WindowsSandboxError(
                    f"Root runtime wajib tidak ditemukan untuk sandbox AppContainer: {redact_path_for_log(root)}."
                )
            ok_req, _tracked = _grant_read_root(root)
            if not ok_req:
                logger.warning(
                    "windows_sandbox.acl_required_failed target=%s",
                    redact_path_for_log(root),
                )
                raise WindowsSandboxError(
                    f"Gagal memasang ACL read/exec wajib pada {redact_path_for_log(root)}."
                )
            req_granted += 1

        opt_granted = 0
        opt_skipped = 0
        for root in validated_optional:
            if root.exists():
                ok_opt, _tracked = _grant_read_root(root)
                if ok_opt:
                    opt_granted += 1
                    continue
            opt_skipped += 1
            logger.debug(
                "windows_sandbox.acl_optional_skipped target=%s exists=%s",
                redact_path_for_log(root),
                root.exists(),
            )

        logger.info(
            "windows_sandbox.acl_applied required_granted=%d optional_granted=%d optional_skipped=%d",
            req_granted,
            opt_granted,
            opt_skipped,
        )

        # 3. Prepare Job Object BEFORE process resumes
        h_job = kernel32.CreateJobObjectW(None, None)
        if not h_job:
            raise WindowsSandboxError(f"CreateJobObjectW gagal: err={_win_last_error()}")

        job_info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        job_info.BasicLimitInformation.LimitFlags = (
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            | JOB_OBJECT_LIMIT_PROCESS_MEMORY
        )
        job_info.BasicLimitInformation.ActiveProcessLimit = 1
        job_info.ProcessMemoryLimit = 512 * 1024 * 1024
        if not kernel32.SetInformationJobObject(
            h_job, JobObjectExtendedLimitInformation, ctypes.byref(job_info), ctypes.sizeof(job_info)
        ):
            raise WindowsSandboxError(f"SetInformationJobObject gagal: err={_win_last_error()}")

        # 4. Inheritable pipes for configured stdio ONLY (restrict child handle inheritance explicitly)
        sa = SECURITY_ATTRIBUTES(ctypes.sizeof(SECURITY_ATTRIBUTES), None, True)
        h_out_r, h_out_w = wintypes.HANDLE(), wintypes.HANDLE()
        h_err_r, h_err_w = wintypes.HANDLE(), wintypes.HANDLE()
        h_in_r, h_in_w = wintypes.HANDLE(), wintypes.HANDLE()
        if not kernel32.CreatePipe(ctypes.byref(h_out_r), ctypes.byref(h_out_w), ctypes.byref(sa), 0):
            raise WindowsSandboxError("Gagal membuat stdout pipe.")
        handles_to_close.extend([h_out_r, h_out_w])
        if not kernel32.CreatePipe(ctypes.byref(h_err_r), ctypes.byref(h_err_w), ctypes.byref(sa), 0):
            raise WindowsSandboxError("Gagal membuat stderr pipe.")
        handles_to_close.extend([h_err_r, h_err_w])
        if stdin_bytes is not None:
            if not kernel32.CreatePipe(ctypes.byref(h_in_r), ctypes.byref(h_in_w), ctypes.byref(sa), 0):
                raise WindowsSandboxError("Gagal membuat stdin pipe.")
            handles_to_close.extend([h_in_r, h_in_w])

        for read_h in (h_out_r, h_err_r):
            if not kernel32.SetHandleInformation(read_h, HANDLE_FLAG_INHERIT, 0):
                raise WindowsSandboxError(f"SetHandleInformation read pipe gagal: err={_win_last_error()}")
        for write_h in (h_out_w, h_err_w):
            if not kernel32.SetHandleInformation(write_h, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT):
                raise WindowsSandboxError(f"SetHandleInformation write pipe gagal: err={_win_last_error()}")
        if stdin_bytes is not None:
            if not kernel32.SetHandleInformation(h_in_w, HANDLE_FLAG_INHERIT, 0):
                raise WindowsSandboxError(f"SetHandleInformation stdin write pipe gagal: err={_win_last_error()}")
            if not kernel32.SetHandleInformation(h_in_r, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT):
                raise WindowsSandboxError(f"SetHandleInformation stdin read pipe gagal: err={_win_last_error()}")

        # 5. Build StartupInfoEx with BOTH AppContainer SECURITY_CAPABILITIES and explicit HANDLE_LIST
        attr_size = ctypes.c_size_t(0)
        kernel32.InitializeProcThreadAttributeList(None, 2, 0, ctypes.byref(attr_size))
        attr_buf = (ctypes.c_byte * attr_size.value)()
        if not kernel32.InitializeProcThreadAttributeList(attr_buf, 2, 0, ctypes.byref(attr_size)):
            raise WindowsSandboxError(f"InitializeProcThreadAttributeList gagal: err={_win_last_error()}")
        attr_initialized = True

        sec_caps = SECURITY_CAPABILITIES(
            AppContainerSid=app_container_sid, Capabilities=None, CapabilityCount=0, Reserved=0
        )
        if not kernel32.UpdateProcThreadAttribute(
            attr_buf, 0, PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES,
            ctypes.byref(sec_caps), ctypes.sizeof(sec_caps), None, None,
        ):
            raise WindowsSandboxError(f"UpdateProcThreadAttribute SECURITY_CAPABILITIES gagal: err={_win_last_error()}")

        # Keep inherit_handle_list referenced until CreateProcessW + DeleteProcThreadAttributeList complete
        if stdin_bytes is not None:
            inherit_handle_list = (wintypes.HANDLE * 3)(h_in_r.value, h_out_w.value, h_err_w.value)
        else:
            inherit_handle_list = (wintypes.HANDLE * 2)(h_out_w.value, h_err_w.value)
        if not kernel32.UpdateProcThreadAttribute(
            attr_buf,
            0,
            PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
            inherit_handle_list,
            ctypes.sizeof(inherit_handle_list),
            None,
            None,
        ):
            raise WindowsSandboxError(f"UpdateProcThreadAttribute HANDLE_LIST gagal: err={_win_last_error()}")

        si_ex = STARTUPINFOEXW()
        si_ex.StartupInfo.cb = ctypes.sizeof(STARTUPINFOEXW)
        si_ex.StartupInfo.dwFlags = STARTF_USESTDHANDLES
        si_ex.StartupInfo.hStdInput = h_in_r if stdin_bytes is not None else wintypes.HANDLE(0)
        si_ex.StartupInfo.hStdOutput = h_out_w
        si_ex.StartupInfo.hStdError = h_err_w
        si_ex.lpAttributeList = ctypes.cast(attr_buf, ctypes.c_void_p)

        cmdline = subprocess.list2cmdline(cmd)
        env_block = _escape_env_block(env)
        creation_flags = (
            CREATE_SUSPENDED | EXTENDED_STARTUPINFO_PRESENT | CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT
        )

        # 6. Spawn SUSPENDED inside AppContainer
        ok = kernel32.CreateProcessW(
            None, ctypes.create_unicode_buffer(cmdline), None, None, True,
            creation_flags, env_block, str(cwd), ctypes.byref(si_ex), ctypes.byref(pi),
        )
        # Close child-owned pipe ends in parent immediately
        kernel32.CloseHandle(h_out_w)
        kernel32.CloseHandle(h_err_w)
        handles_to_close = [h_out_r, h_err_r]
        if stdin_bytes is not None:
            kernel32.CloseHandle(h_in_r)
            handles_to_close.append(h_in_w)

        if not ok:
            raise WindowsSandboxError(f"CreateProcessW AppContainer gagal: err={_win_last_error()}")

        # 7. Attach suspended process to Job Object BEFORE ResumeThread (fail-closed)
        if not kernel32.AssignProcessToJobObject(h_job, pi.hProcess):
            err = _win_last_error()
            kernel32.TerminateProcess(pi.hProcess, 1)
            raise WindowsSandboxError(f"AssignProcessToJobObject gagal (proses dihentikan): err={err}")

        # 8. Drain pipes via streaming threads (enforcing hard output limits) and ResumeThread
        out_chunks: list[bytes] = []
        err_chunks: list[bytes] = []
        eff_stderr_hard = max_output_bytes if max_stderr_bytes is None else max(1, int(max_stderr_bytes))
        eff_stderr_retain = eff_stderr_hard if stderr_retain_bytes is None else min(eff_stderr_hard, max(0, int(stderr_retain_bytes)))
        exceeded: dict[str, Any] = {}
        exceed_lock = threading.Lock()

        def _drain(handle: int, sink: list[bytes], stream_name: str, retain_limit: int, hard_limit: int) -> None:
            import msvcrt  # type: ignore[import-not-found]
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY)
            kept = 0
            total = 0
            # open_osfhandle transfers OS handle ownership to the CRT file descriptor
            with os.fdopen(fd, "rb", closefd=True) as fp:
                while True:
                    chunk = fp.read(8192)
                    if not chunk:
                        break
                    total += len(chunk)
                    if kept < retain_limit:
                        slice_b = chunk[: retain_limit - kept]
                        sink.append(slice_b)
                        kept += len(slice_b)
                    if abort_on_output_limit and total > hard_limit:
                        with exceed_lock:
                            if "stream" not in exceeded:
                                exceeded["stream"] = stream_name
                                exceeded["limit"] = hard_limit
                                kernel32.TerminateJobObject(h_job, 1)
                        break

        def _feed_stdin(handle: int, data: bytes) -> None:
            import msvcrt  # type: ignore[import-not-found]
            fd = msvcrt.open_osfhandle(handle, os.O_WRONLY)
            with os.fdopen(fd, "wb", closefd=True) as fp:
                try:
                    if data:
                        fp.write(data)
                        fp.flush()
                except OSError:
                    pass

        # Ownership of parent read/write pipe handles is transferred to worker threads (closed via fdopen)
        handles_to_close = []
        t_out = threading.Thread(
            target=_drain,
            args=(int(h_out_r.value), out_chunks, "stdout", max_output_bytes, max_output_bytes),
            daemon=True,
        )
        t_err = threading.Thread(
            target=_drain,
            args=(int(h_err_r.value), err_chunks, "stderr", eff_stderr_retain, eff_stderr_hard),
            daemon=True,
        )
        t_out.start()
        t_err.start()
        t_in: threading.Thread | None = None
        if stdin_bytes is not None:
            t_in = threading.Thread(
                target=_feed_stdin,
                args=(int(h_in_w.value), stdin_bytes),
                daemon=True,
            )
            t_in.start()

        if kernel32.ResumeThread(pi.hThread) == 0xFFFFFFFF:
            err = _win_last_error()
            kernel32.TerminateJobObject(h_job, 1)
            raise WindowsSandboxError(f"ResumeThread gagal (proses dihentikan): err={err}")

        # 9. Wait for completion under Job Object handle kept alive
        wait_res = kernel32.WaitForSingleObject(pi.hProcess, max(1, int(timeout * 1000)))
        if wait_res == WAIT_TIMEOUT and "stream" not in exceeded:
            kernel32.TerminateJobObject(h_job, 1)
            t_out.join(timeout=2)
            t_err.join(timeout=2)
            if t_in is not None:
                t_in.join(timeout=1)
            raise TimeoutError(f"Eksekusi sandbox Windows melebihi batas waktu ({timeout}s).")

        exit_code = wintypes.DWORD(1)
        kernel32.GetExitCodeProcess(pi.hProcess, ctypes.byref(exit_code))
        t_out.join(timeout=2)
        t_err.join(timeout=2)
        if t_in is not None:
            t_in.join(timeout=1)

        return {
            "exit_code": int(exit_code.value),
            "stdout": b"".join(out_chunks),
            "stderr": b"".join(err_chunks),
            "output_limit_exceeded": exceeded.get("stream"),
            "output_limit_bytes": exceeded.get("limit"),
        }
    finally:
        if attr_initialized and attr_buf is not None:
            kernel32.DeleteProcThreadAttributeList(attr_buf)
        if pi.hThread:
            kernel32.CloseHandle(pi.hThread)
        if pi.hProcess:
            kernel32.CloseHandle(pi.hProcess)
        if h_job:
            kernel32.CloseHandle(h_job)
        for h in handles_to_close:
            if h:
                kernel32.CloseHandle(h)
        for p, inherit_acl in reversed(modified_acls):
            _modify_acl(p, 0, REVOKE_ACCESS, inherit=inherit_acl)
        if profile_created:
            userenv.DeleteAppContainerProfile(container_name)
        if app_container_sid:
            advapi32.FreeSid(app_container_sid)
