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
import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any


class WindowsSandboxError(PermissionError):
    """Raised when Windows AppContainer or Job Object confinement fails (fail-closed)."""


def _escape_env_block(env: dict[str, str]) -> ctypes.Array[ctypes.c_wchar]:
    """Encode environment dict as double-null-terminated UTF-16 block for CreateProcessW."""
    items = [f"{k}={v}" for k, v in env.items()]
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
    read_roots: list[Path],
    timeout: float = 15.0,
    max_output_bytes: int = 1024 * 1024,
) -> dict[str, Any]:
    """Execute ``cmd`` inside a zero-capability Windows AppContainer + Job Object.

    Raises ``WindowsSandboxError`` if not running on Windows or if any isolation
    primitive fails to attach before ``ResumeThread``.
    """
    if sys.platform != "win32":
        raise WindowsSandboxError("Windows AppContainer sandbox hanya dapat dijalankan di Windows.")

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
    PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES = 0x0002000B
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
    modified_acls: list[Path] = []
    h_job = None
    pi = PROCESS_INFORMATION()
    attr_buf = None
    attr_initialized = False
    handles_to_close: list[Any] = []

    def _modify_acl(target_path: Path, access_mask: int, mode: int) -> bool:
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
            ea.grfInheritance = OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE
            ea.Trustee.MultipleTrusteeOperation = 0
            ea.Trustee.TrusteeForm = TRUSTEE_IS_SID
            ea.Trustee.TrusteeType = TRUSTEE_IS_UNKNOWN
            ea.Trustee.ptstrName = app_container_sid
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

        # 2. Grant workspace R/W ACL (mandatory) and read_roots R/X ACL (best-effort if system-owned)
        if not _modify_acl(workspace, FILE_ALL_ACCESS, GRANT_ACCESS):
            raise WindowsSandboxError(f"Gagal memasang ACL AppContainer pada workspace '{workspace}'.")
        modified_acls.append(workspace)
        for root in read_roots:
            if root.exists() and _modify_acl(root, FILE_READ_EXEC, GRANT_ACCESS):
                modified_acls.append(root)

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

        # 4. Build StartupInfoEx with AppContainer SECURITY_CAPABILITIES (0 capabilities)
        attr_size = ctypes.c_size_t(0)
        kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(attr_size))
        attr_buf = (ctypes.c_byte * attr_size.value)()
        if not kernel32.InitializeProcThreadAttributeList(attr_buf, 1, 0, ctypes.byref(attr_size)):
            raise WindowsSandboxError(f"InitializeProcThreadAttributeList gagal: err={_win_last_error()}")
        attr_initialized = True

        sec_caps = SECURITY_CAPABILITIES(
            AppContainerSid=app_container_sid, Capabilities=None, CapabilityCount=0, Reserved=0
        )
        if not kernel32.UpdateProcThreadAttribute(
            attr_buf, 0, PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES,
            ctypes.byref(sec_caps), ctypes.sizeof(sec_caps), None, None,
        ):
            raise WindowsSandboxError(f"UpdateProcThreadAttribute gagal: err={_win_last_error()}")

        # 5. Inheritable pipes for stdout/stderr
        sa = SECURITY_ATTRIBUTES(ctypes.sizeof(SECURITY_ATTRIBUTES), None, True)
        h_out_r, h_out_w = wintypes.HANDLE(), wintypes.HANDLE()
        h_err_r, h_err_w = wintypes.HANDLE(), wintypes.HANDLE()
        if not kernel32.CreatePipe(ctypes.byref(h_out_r), ctypes.byref(h_out_w), ctypes.byref(sa), 0):
            raise WindowsSandboxError("Gagal membuat stdout pipe.")
        handles_to_close.extend([h_out_r, h_out_w])
        if not kernel32.CreatePipe(ctypes.byref(h_err_r), ctypes.byref(h_err_w), ctypes.byref(sa), 0):
            raise WindowsSandboxError("Gagal membuat stderr pipe.")
        handles_to_close.extend([h_err_r, h_err_w])
        kernel32.SetHandleInformation(h_out_r, HANDLE_FLAG_INHERIT, 0)
        kernel32.SetHandleInformation(h_err_r, HANDLE_FLAG_INHERIT, 0)

        si_ex = STARTUPINFOEXW()
        si_ex.StartupInfo.cb = ctypes.sizeof(STARTUPINFOEXW)
        si_ex.StartupInfo.dwFlags = STARTF_USESTDHANDLES
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
        # Close child write pipe ends in parent immediately
        kernel32.CloseHandle(h_out_w)
        kernel32.CloseHandle(h_err_w)
        handles_to_close = [h_out_r, h_err_r]

        if not ok:
            raise WindowsSandboxError(f"CreateProcessW AppContainer gagal: err={_win_last_error()}")

        # 7. Attach suspended process to Job Object BEFORE ResumeThread (fail-closed)
        if not kernel32.AssignProcessToJobObject(h_job, pi.hProcess):
            err = _win_last_error()
            kernel32.TerminateProcess(pi.hProcess, 1)
            raise WindowsSandboxError(f"AssignProcessToJobObject gagal (proses dihentikan): err={err}")

        # 8. Drain pipes asynchronously and ResumeThread
        out_chunks: list[bytes] = []
        err_chunks: list[bytes] = []

        def _drain(handle: int, sink: list[bytes]) -> None:
            import msvcrt  # type: ignore[import-not-found]
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY)
            total = 0
            # open_osfhandle transfers OS handle ownership to the CRT file descriptor
            with os.fdopen(fd, "rb", closefd=True) as fp:
                while True:
                    chunk = fp.read(8192)
                    if not chunk:
                        break
                    if total < max_output_bytes:
                        sink.append(chunk[: max_output_bytes - total])
                        total += len(chunk)

        # Ownership of h_out_r / h_err_r is transferred to reader threads (closed via fdopen)
        handles_to_close = []
        t_out = threading.Thread(target=_drain, args=(int(h_out_r.value), out_chunks), daemon=True)
        t_err = threading.Thread(target=_drain, args=(int(h_err_r.value), err_chunks), daemon=True)
        t_out.start()
        t_err.start()

        if kernel32.ResumeThread(pi.hThread) == 0xFFFFFFFF:
            err = _win_last_error()
            kernel32.TerminateJobObject(h_job, 1)
            raise WindowsSandboxError(f"ResumeThread gagal (proses dihentikan): err={err}")

        # 9. Wait for completion under Job Object handle kept alive
        wait_res = kernel32.WaitForSingleObject(pi.hProcess, max(1, int(timeout * 1000)))
        if wait_res == WAIT_TIMEOUT:
            kernel32.TerminateJobObject(h_job, 1)
            t_out.join(timeout=2)
            t_err.join(timeout=2)
            raise TimeoutError(f"Eksekusi sandbox Windows melebihi batas waktu ({timeout}s).")

        exit_code = wintypes.DWORD(1)
        kernel32.GetExitCodeProcess(pi.hProcess, ctypes.byref(exit_code))
        t_out.join(timeout=2)
        t_err.join(timeout=2)

        return {
            "exit_code": int(exit_code.value),
            "stdout": b"".join(out_chunks),
            "stderr": b"".join(err_chunks),
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
        for p in reversed(modified_acls):
            _modify_acl(p, 0, REVOKE_ACCESS)
        if profile_created:
            userenv.DeleteAppContainerProfile(container_name)
        if app_container_sid:
            advapi32.FreeSid(app_container_sid)
