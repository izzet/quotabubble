from __future__ import annotations

import ctypes
from dataclasses import dataclass

_UTF8 = 0x08000100
_NO_ERR = 0

_core_foundation = ctypes.CDLL(
    "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
)
_security = ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")

_core_foundation.CFStringCreateWithCString.argtypes = [
    ctypes.c_void_p,
    ctypes.c_char_p,
    ctypes.c_uint32,
]
_core_foundation.CFStringCreateWithCString.restype = ctypes.c_void_p
_core_foundation.CFStringGetLength.argtypes = [ctypes.c_void_p]
_core_foundation.CFStringGetLength.restype = ctypes.c_long
_core_foundation.CFStringGetMaximumSizeForEncoding.argtypes = [
    ctypes.c_long,
    ctypes.c_uint32,
]
_core_foundation.CFStringGetMaximumSizeForEncoding.restype = ctypes.c_long
_core_foundation.CFStringGetCString.argtypes = [
    ctypes.c_void_p,
    ctypes.c_char_p,
    ctypes.c_long,
    ctypes.c_uint32,
]
_core_foundation.CFStringGetCString.restype = ctypes.c_bool
_core_foundation.CFDictionaryCreateMutable.argtypes = [
    ctypes.c_void_p,
    ctypes.c_long,
    ctypes.c_void_p,
    ctypes.c_void_p,
]
_core_foundation.CFDictionaryCreateMutable.restype = ctypes.c_void_p
_core_foundation.CFDictionarySetValue.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
]
_core_foundation.CFDictionaryGetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_core_foundation.CFDictionaryGetValue.restype = ctypes.c_void_p
_core_foundation.CFArrayGetCount.argtypes = [ctypes.c_void_p]
_core_foundation.CFArrayGetCount.restype = ctypes.c_long
_core_foundation.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
_core_foundation.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
_core_foundation.CFArrayGetTypeID.restype = ctypes.c_ulong
_core_foundation.CFGetTypeID.argtypes = [ctypes.c_void_p]
_core_foundation.CFGetTypeID.restype = ctypes.c_ulong
_core_foundation.CFDataGetLength.argtypes = [ctypes.c_void_p]
_core_foundation.CFDataGetLength.restype = ctypes.c_long
_core_foundation.CFDataGetBytePtr.argtypes = [ctypes.c_void_p]
_core_foundation.CFDataGetBytePtr.restype = ctypes.POINTER(ctypes.c_ubyte)
_core_foundation.CFDateGetAbsoluteTime.argtypes = [ctypes.c_void_p]
_core_foundation.CFDateGetAbsoluteTime.restype = ctypes.c_double
_core_foundation.CFRelease.argtypes = [ctypes.c_void_p]

_security.SecItemCopyMatching.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
_security.SecItemCopyMatching.restype = ctypes.c_int32


def _constant(library: ctypes.CDLL, name: str) -> ctypes.c_void_p:
    return ctypes.c_void_p.in_dll(library, name)


_K_CF_BOOLEAN_TRUE = _constant(_core_foundation, "kCFBooleanTrue")
_K_SEC_CLASS = _constant(_security, "kSecClass")
_K_SEC_CLASS_GENERIC_PASSWORD = _constant(_security, "kSecClassGenericPassword")
_K_SEC_ATTR_SERVICE = _constant(_security, "kSecAttrService")
_K_SEC_ATTR_ACCOUNT = _constant(_security, "kSecAttrAccount")
_K_SEC_ATTR_MODIFICATION_DATE = _constant(_security, "kSecAttrModificationDate")
_K_SEC_RETURN_ATTRIBUTES = _constant(_security, "kSecReturnAttributes")
_K_SEC_RETURN_DATA = _constant(_security, "kSecReturnData")
_K_SEC_MATCH_LIMIT = _constant(_security, "kSecMatchLimit")
_K_SEC_MATCH_LIMIT_ALL = _constant(_security, "kSecMatchLimitAll")


@dataclass(frozen=True)
class _Item:
    service: str
    account: str | None
    modified: float


def _string(value: str) -> ctypes.c_void_p:
    return ctypes.c_void_p(
        _core_foundation.CFStringCreateWithCString(None, value.encode("utf-8"), _UTF8)
    )


def _text(value: ctypes.c_void_p) -> str | None:
    if not value:
        return None
    length = _core_foundation.CFStringGetLength(value)
    maximum = _core_foundation.CFStringGetMaximumSizeForEncoding(length, _UTF8) + 1
    buffer = ctypes.create_string_buffer(maximum)
    if not _core_foundation.CFStringGetCString(value, buffer, maximum, _UTF8):
        return None
    return buffer.value.decode("utf-8")


def _query(
    *, service: str | None = None, account: str | None = None
) -> tuple[ctypes.c_void_p, list[ctypes.c_void_p]]:
    query = ctypes.c_void_p(
        _core_foundation.CFDictionaryCreateMutable(None, 0, None, None)
    )
    values: list[ctypes.c_void_p] = []
    _core_foundation.CFDictionarySetValue(query, _K_SEC_CLASS, _K_SEC_CLASS_GENERIC_PASSWORD)
    for key, value in ((_K_SEC_ATTR_SERVICE, service), (_K_SEC_ATTR_ACCOUNT, account)):
        if value is not None:
            string = _string(value)
            values.append(string)
            _core_foundation.CFDictionarySetValue(query, key, string)
    return query, values


def _release_query(query: ctypes.c_void_p, values: list[ctypes.c_void_p]) -> None:
    for value in values:
        _core_foundation.CFRelease(value)
    _core_foundation.CFRelease(query)


def _copy_matching(query: ctypes.c_void_p) -> ctypes.c_void_p | None:
    result = ctypes.c_void_p()
    if _security.SecItemCopyMatching(query, ctypes.byref(result)) != _NO_ERR:
        return None
    return result


def _copy_data(service: str, account: str | None = None) -> bytes | None:
    query, values = _query(service=service, account=account)
    try:
        _core_foundation.CFDictionarySetValue(query, _K_SEC_RETURN_DATA, _K_CF_BOOLEAN_TRUE)
        result = _copy_matching(query)
        if result is None:
            return None
        try:
            length = _core_foundation.CFDataGetLength(result)
            pointer = _core_foundation.CFDataGetBytePtr(result)
            return ctypes.string_at(pointer, length) if pointer else None
        finally:
            _core_foundation.CFRelease(result)
    finally:
        _release_query(query, values)


def _items() -> list[_Item]:
    query, values = _query()
    try:
        _core_foundation.CFDictionarySetValue(query, _K_SEC_RETURN_ATTRIBUTES, _K_CF_BOOLEAN_TRUE)
        _core_foundation.CFDictionarySetValue(query, _K_SEC_MATCH_LIMIT, _K_SEC_MATCH_LIMIT_ALL)
        result = _copy_matching(query)
        if result is None:
            return []
        try:
            dictionaries: list[ctypes.c_void_p]
            if _core_foundation.CFGetTypeID(result) == _core_foundation.CFArrayGetTypeID():
                dictionaries = [
                    _core_foundation.CFArrayGetValueAtIndex(result, index)
                    for index in range(_core_foundation.CFArrayGetCount(result))
                ]
            else:
                dictionaries = [result]

            items: list[_Item] = []
            for dictionary in dictionaries:
                service = _text(
                    _core_foundation.CFDictionaryGetValue(dictionary, _K_SEC_ATTR_SERVICE)
                )
                if service is None:
                    continue
                account = _text(
                    _core_foundation.CFDictionaryGetValue(dictionary, _K_SEC_ATTR_ACCOUNT)
                )
                modified_value = _core_foundation.CFDictionaryGetValue(
                    dictionary, _K_SEC_ATTR_MODIFICATION_DATE
                )
                modified = (
                    _core_foundation.CFDateGetAbsoluteTime(modified_value)
                    if modified_value
                    else 0.0
                )
                items.append(_Item(service, account, modified))
            return sorted(items, key=lambda item: item.modified, reverse=True)
        finally:
            _core_foundation.CFRelease(result)
    finally:
        _release_query(query, values)


def read_generic_credential(target: str) -> bytes | None:
    service, separator, account = target.partition(":")
    return _copy_data(service, account if separator else None)


def enumerate_generic_credentials(name_contains: str) -> list[tuple[str, bytes]]:
    needle = name_contains.lower()
    results: list[tuple[str, bytes]] = []
    for item in _items():
        target = f"{item.service}:{item.account}" if item.account else item.service
        if needle not in target.lower():
            continue
        data = _copy_data(item.service, item.account)
        if data:
            results.append((target, data))
    return results
