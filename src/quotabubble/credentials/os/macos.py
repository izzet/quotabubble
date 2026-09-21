from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from Security import (
    SecItemCopyMatching,
    SecKeychainSetUserInteractionAllowed,
    errSecSuccess,
    kSecAttrAccount,
    kSecAttrModificationDate,
    kSecAttrService,
    kSecClass,
    kSecClassGenericPassword,
    kSecMatchLimit,
    kSecMatchLimitAll,
    kSecReturnAttributes,
    kSecReturnData,
    kSecUseAuthenticationUI,
    kSecUseAuthenticationUIFail,
)


@dataclass(frozen=True)
class _Item:
    service: str
    account: str | None
    modified: float


def _copy_matching(query: dict[object, object]) -> object | None:
    # Quota polling runs without an interactive application flow. A keychain
    # item that requires approval must fail rather than block that worker.
    SecKeychainSetUserInteractionAllowed(False)
    try:
        status, result = SecItemCopyMatching(
            {**query, kSecUseAuthenticationUI: kSecUseAuthenticationUIFail}, None
        )
    finally:
        SecKeychainSetUserInteractionAllowed(True)
    return result if status == errSecSuccess else None


def _copy_data(service: str, account: str | None = None) -> bytes | None:
    query: dict[object, object] = {
        kSecClass: kSecClassGenericPassword,
        kSecAttrService: service,
        kSecReturnData: True,
    }
    if account is not None:
        query[kSecAttrAccount] = account
    result = _copy_matching(query)
    return bytes(result) if result is not None else None


def _items(service: str) -> list[_Item]:
    result = _copy_matching(
        {
            kSecClass: kSecClassGenericPassword,
            kSecAttrService: service,
            kSecReturnAttributes: True,
            kSecMatchLimit: kSecMatchLimitAll,
        }
    )
    if result is None:
        return []
    dictionaries = result if isinstance(result, Sequence) else [result]
    items: list[_Item] = []
    for dictionary in dictionaries:
        service = dictionary.get(kSecAttrService)
        if not isinstance(service, str):
            continue
        account = dictionary.get(kSecAttrAccount)
        modified = dictionary.get(kSecAttrModificationDate)
        items.append(
            _Item(
                service=service,
                account=account if isinstance(account, str) else None,
                modified=modified.timeIntervalSinceReferenceDate() if modified else 0.0,
            )
        )
    return sorted(items, key=lambda item: item.modified, reverse=True)


def read_generic_credential(target: str) -> bytes | None:
    service, separator, account = target.partition(":")
    return _copy_data(service, account if separator else None)


def enumerate_generic_credentials(name_contains: str) -> list[tuple[str, bytes]]:
    needle = name_contains.lower()
    results: list[tuple[str, bytes]] = []
    # Callers use a known Keychain service name. Searching every generic
    # password can block on an unrelated item that requires authentication.
    for item in _items(name_contains):
        target = f"{item.service}:{item.account}" if item.account else item.service
        if needle not in target.lower():
            continue
        data = _copy_data(item.service, item.account)
        if data:
            results.append((target, data))
    return results
