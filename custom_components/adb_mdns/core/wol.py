"""Wake-on-LAN packet sender for Android TV ADB."""

from __future__ import annotations

import asyncio
import logging
import socket

_LOGGER = logging.getLogger(__name__)


def _build_magic_packet(mac: str) -> bytes:
    """Build a standard Wake-on-LAN magic packet."""
    cleaned = mac.replace(":", "").replace("-", "").replace(".", "").strip()
    if len(cleaned) != 12:
        raise ValueError(f"Invalid MAC address: {mac}")
    mac_bytes = bytes.fromhex(cleaned)
    return b"\xff" * 6 + mac_bytes * 16


def send_magic_packet_sync(
    mac: str,
    ip_address: str = "255.255.255.255",
    port: int = 9,
) -> None:
    """Send a Wake-on-LAN magic packet synchronously."""
    packet = _build_magic_packet(mac)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(packet, (ip_address, port))


async def async_send_magic_packet(
    mac: str,
    ip_address: str = "255.255.255.255",
    port: int = 9,
) -> bool:
    """Send a Wake-on-LAN magic packet asynchronously in an executor thread."""
    if not mac:
        return False
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, send_magic_packet_sync, mac, ip_address, port)
        _LOGGER.debug("Sent Wake-on-LAN packet to %s (via %s:%s)", mac, ip_address, port)
        return True
    except Exception as err:
        _LOGGER.warning("Failed to send Wake-on-LAN packet to %s: %s", mac, err)
        return False
