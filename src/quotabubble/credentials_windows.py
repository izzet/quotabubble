from __future__ import annotations

import ctypes
from ctypes import wintypes

CRED_TYPE_GENERIC = 1


class _Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


_advapi32 = ctypes.windll.advapi32


def read_generic_credential(target: str) -> bytes | None:
    pointer = ctypes.POINTER(_Credential)()
    ok = _advapi32.CredReadW(
        ctypes.c_wchar_p(target), CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)
    )
    if not ok:
        return None
    try:
        credential = pointer.contents
        if credential.CredentialBlobSize == 0 or not credential.CredentialBlob:
            return None
        return ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
    finally:
        _advapi32.CredFree(pointer)


def enumerate_generic_credentials(name_contains: str) -> list[tuple[str, bytes]]:
    count = wintypes.DWORD(0)
    pointer = ctypes.POINTER(ctypes.POINTER(_Credential))()
    ok = _advapi32.CredEnumerateW(None, 0, ctypes.byref(count), ctypes.byref(pointer))
    if not ok:
        return []
    results: list[tuple[str, bytes]] = []
    try:
        needle = name_contains.lower()
        for index in range(count.value):
            credential = pointer[index].contents
            target = credential.TargetName or ""
            if needle not in target.lower():
                continue
            if credential.CredentialBlobSize == 0 or not credential.CredentialBlob:
                continue
            blob = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
            results.append((target, blob))
    finally:
        _advapi32.CredFree(pointer)
    return results
