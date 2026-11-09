"""Tests for cryptographic routines in adb_mdns."""

from __future__ import annotations

import base64
import struct

from custom_components.adb_mdns.core.crypto import (
    generate_keypair,
    generate_self_signed_cert,
    get_adb_public_key_string,
    load_private_key,
)
from custom_components.adb_mdns.core.spake2 import Spake2


def test_spake2_boringssl_vector() -> None:
    """Verify SPAKE2 derivation against Android BoringSSL test vector."""
    client = b"adb pair client\x00"
    server = b"adb pair server\x00"
    fixed_secret = bytes([0x11] * 64)

    a = Spake2(alice=True, my_name=client, their_name=server, random_secret=fixed_secret)
    msg = a.generate(b"hello")
    assert msg.hex() == "58ca6e597eb34c8d91f67c8aa6bf5208691779bf3c1b9b198662db0aa8883a16"

    key = a.process(bytes.fromhex("11b38de5b0b77be8743da9b57b1e136d1085e35b6d14493846ef63ebb134fe34"))
    expected_key = "483a95ad39fb481d13f7c228dcad7be002f12d4aeb52dc929b8878836dc7916854461dc3a323ea4c05b080492c3fe3945a270b50cff622bbc8b05dcbbaa01e5a"
    assert key.hex() == expected_key


def test_spake2_mutual_derivation() -> None:
    """Verify that Alice and Bob derive identical shared keys with matching passwords."""
    client = b"adb pair client\x00"
    server = b"adb pair server\x00"

    a = Spake2(alice=True, my_name=client, their_name=server)
    b = Spake2(alice=False, my_name=server, their_name=client)

    ma = a.generate(b"987654")
    mb = b.generate(b"987654")

    assert len(ma) == 32
    assert len(mb) == 32

    ka = a.process(mb)
    kb = b.process(ma)
    assert ka == kb


def test_rsa_and_adb_public_key() -> None:
    """Verify RSA key generation and ADB wire text serialization."""
    key, pem = generate_keypair()
    assert pem.startswith("-----BEGIN PRIVATE KEY-----")

    reloaded_key = load_private_key(pem)
    assert reloaded_key.key_size == 2048

    adb_str = get_adb_public_key_string(key, "test@host")
    assert adb_str.endswith(" test@host")

    raw_b64 = adb_str.split(" ")[0]
    decoded = base64.b64decode(raw_b64)
    assert len(decoded) == 524

    words, n0inv = struct.unpack("<II", decoded[:8])
    assert words == 64

    cert = generate_self_signed_cert(key)
    assert cert.serial_number > 0
