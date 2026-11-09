"""Android TV ADB Core library."""

from .client import AndroidTvAdbClient
from .crypto import (
    generate_keypair,
    generate_self_signed_cert,
    get_adb_public_key_string,
    load_private_key,
)
from .exceptions import (
    AdbAuthError,
    AdbConnectionError,
    AdbError,
    AdbTimeoutError,
)
from .pairing import pair_device
from .wol import async_send_magic_packet, send_magic_packet_sync

__all__ = [
    "AdbAuthError",
    "AdbConnectionError",
    "AdbError",
    "AdbTimeoutError",
    "AndroidTvAdbClient",
    "async_send_magic_packet",
    "generate_keypair",
    "generate_self_signed_cert",
    "get_adb_public_key_string",
    "load_private_key",
    "pair_device",
    "send_magic_packet_sync",
]
