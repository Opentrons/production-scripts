from __future__ import annotations


# Keep the protocol's load names and the hardware's names in one display group.
# Unknown names remain distinct, including unrecognised 96-channel models.
_PRODUCT_NAMES = {
    "P50S": ("flex_1channel_50", "p50_single_flex"),
    "P50M": ("flex_8channel_50", "p50_multi_flex"),
    "P1000S": ("flex_1channel_1000", "p1000_single_flex", "P1KS"),
    "P1000M": ("flex_8channel_1000", "p1000_multi_flex", "P1KM"),
    "P200-96": ("flex_96channel_200",),
    "P1000-96": ("flex_96channel_1000",),
}
_ALIASES = {
    alias.casefold(): product
    for product, aliases in _PRODUCT_NAMES.items()
    for alias in (product, *aliases)
}
_SERIAL_PREFIXES = {
    "P50S": "P50S", "P50M": "P50M", "P1KS": "P1000S",
    "P1KM": "P1000M", "P2HH": "P200-96", "P1KH": "P1000-96",
}


def normalize_product(value: object) -> str:
    name = str(value or "").strip()
    return _ALIASES.get(name.casefold(), name)


def product_from_serial(serial: str) -> str:
    serial = serial.strip().upper()
    return next((product for prefix, product in _SERIAL_PREFIXES.items() if serial.startswith(prefix)), "Unknown")
