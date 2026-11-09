"""Tests for ADB protocol packet framing."""

from __future__ import annotations

import pytest

from custom_components.adb_mdns.core.protocol import (
    A_VERSION,
    CNXN,
    MAX_PAYLOAD,
    OPEN,
    decode_header,
    encode_packet,
)


def test_packet_encoding_and_decoding() -> None:
    """Test standard packet header packing and unpacking."""
    payload = b"shell:getprop ro.product.model\x00"
    pkt = encode_packet(OPEN, 1, 0, payload)

    assert len(pkt) == 24 + len(payload)

    cmd, arg0, arg1, length = decode_header(pkt[:24])
    assert cmd == OPEN
    assert arg0 == 1
    assert arg1 == 0
    assert length == len(payload)
    assert pkt[24:] == payload


def test_corrupt_packet_header() -> None:
    """Test that a corrupt magic raises ValueError."""
    pkt = bytearray(encode_packet(CNXN, A_VERSION, MAX_PAYLOAD, b""))
    # Corrupt magic in last 4 bytes of header
    pkt[20] ^= 0xFF

    with pytest.raises(ValueError, match="Corrupt packet header magic"):
        decode_header(bytes(pkt[:24]))
