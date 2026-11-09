"""ADB wire protocol constants, packet framing, and definitions."""

from __future__ import annotations

import struct
from dataclasses import dataclass

CNXN = 0x4E584E43
AUTH = 0x48545541
STLS = 0x534C5453
OPEN = 0x4E45504F
OKAY = 0x59414B4F
CLSE = 0x45534C43
WRTE = 0x45545257

CMD_NAMES = {
    CNXN: "CNXN",
    AUTH: "AUTH",
    STLS: "STLS",
    OPEN: "OPEN",
    OKAY: "OKAY",
    CLSE: "CLSE",
    WRTE: "WRTE",
}

A_VERSION = 0x01000001
MAX_PAYLOAD = 1 << 18  # 256KB
HEADER_LEN = 24


@dataclass
class AdbMessage:
    cmd: int
    arg0: int
    arg1: int
    data: bytes

    @property
    def cmd_name(self) -> str:
        return CMD_NAMES.get(self.cmd, f"0x{self.cmd:08X}")


def encode_packet(cmd: int, arg0: int, arg1: int, data: bytes = b"") -> bytes:
    """Encode an ADB message into a wire packet."""
    checksum = sum(data) & 0xFFFFFFFF
    magic = (cmd ^ 0xFFFFFFFF) & 0xFFFFFFFF
    header = struct.pack("<IIIIII", cmd, arg0, arg1, len(data), checksum, magic)
    return header + data


def decode_header(header_bytes: bytes) -> tuple[int, int, int, int]:
    """Decode a 24-byte ADB packet header.

    Returns (cmd, arg0, arg1, length).
    Raises ValueError on invalid checksum/magic.
    """
    if len(header_bytes) != HEADER_LEN:
        raise ValueError(f"Header must be {HEADER_LEN} bytes, got {len(header_bytes)}")
    cmd, arg0, arg1, length, checksum, magic = struct.unpack("<IIIIII", header_bytes)
    if magic != ((cmd ^ 0xFFFFFFFF) & 0xFFFFFFFF):
        raise ValueError(f"Corrupt packet header magic: {magic:#x} vs cmd {cmd:#x}")
    if length > (1 << 20):  # 1MB sanity check
        raise ValueError(f"Packet payload exceeds maximum: {length}")
    return cmd, arg0, arg1, length
