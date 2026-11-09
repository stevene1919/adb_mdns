"""Pairing implementation for Android 11+ Wireless Debugging.

Handles SPAKE2 over TLS 1.3 with Exported Keying Material (EKM) and AES-128-GCM.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import select
import socket
import struct
import time

import OpenSSL
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .crypto import generate_self_signed_cert, get_adb_public_key_string
from .spake2 import Spake2

_LOGGER = logging.getLogger(__name__)

CLIENT_NAME = b"adb pair client\x00"
SERVER_NAME = b"adb pair server\x00"
EKM_LABEL = b"adb-label\x00"
HKDF_INFO = b"adb pairing_auth aes-128-gcm key"

MSG_SPAKE = 0
MSG_PEER_INFO = 1
PEER_INFO_SIZE = 8192
MAX_PAYLOAD = 16384


def hkdf_adb(ikm: bytes, info: bytes, length: int) -> bytes:
    """HKDF-SHA256 with 32-zero salt as used by Android ADB pairing."""
    if length > 32:
        raise ValueError("length cannot exceed 32 bytes")
    prk = hmac.new(b"\x00" * 32, ikm, hashlib.sha256).digest()
    return hmac.new(prk, info + b"\x01", hashlib.sha256).digest()[:length]


def packet(msg_type: int, payload: bytes) -> bytes:
    """Frame an ADB pairing protocol packet (version 1, big-endian)."""
    return struct.pack(">BBI", 1, msg_type, len(payload)) + payload


def ssl_handshake(conn: OpenSSL.SSL.Connection, timeout: float = 10.0) -> None:
    """Complete TLS handshake handling pyOpenSSL non-blocking states."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            conn.do_handshake()
            return
        except OpenSSL.SSL.WantReadError:
            select.select([conn], [], [], max(0.05, deadline - time.time()))
        except OpenSSL.SSL.WantWriteError:
            select.select([], [conn], [], max(0.05, deadline - time.time()))
    raise TimeoutError("TLS handshake timed out")


def ssl_sendall(conn: OpenSSL.SSL.Connection, data: bytes, timeout: float = 10.0) -> None:
    """Send all bytes handling pyOpenSSL non-blocking states."""
    deadline = time.time() + timeout
    total_sent = 0
    while total_sent < len(data) and time.time() < deadline:
        try:
            sent = conn.send(data[total_sent:])
            total_sent += sent
        except OpenSSL.SSL.WantReadError:
            select.select([conn], [], [], max(0.05, deadline - time.time()))
        except OpenSSL.SSL.WantWriteError:
            select.select([], [conn], [], max(0.05, deadline - time.time()))
    if total_sent < len(data):
        raise TimeoutError("TLS send timed out")


def ssl_read_exact(conn: OpenSSL.SSL.Connection, n: int, timeout: float = 10.0) -> bytes:
    """Read exactly n bytes handling pyOpenSSL non-blocking states."""
    deadline = time.time() + timeout
    buf = bytearray()
    while len(buf) < n and time.time() < deadline:
        try:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                raise ConnectionResetError("Connection closed while reading packet")
            buf.extend(chunk)
        except OpenSSL.SSL.WantReadError:
            select.select([conn], [], [], max(0.05, deadline - time.time()))
        except OpenSSL.SSL.WantWriteError:
            select.select([], [conn], [], max(0.05, deadline - time.time()))
    if len(buf) < n:
        raise TimeoutError("TLS read timed out")
    return bytes(buf)


def ssl_read_packet(conn: OpenSSL.SSL.Connection, expected_type: int, timeout: float = 10.0) -> bytes:
    """Read a framed ADB pairing packet."""
    header = ssl_read_exact(conn, 6, timeout=timeout)
    version, msg_type, length = struct.unpack(">BBI", header)
    if version != 1:
        raise ValueError(f"Unexpected packet version: {version}")
    if msg_type != expected_type:
        raise ValueError(f"Expected packet type {expected_type}, got {msg_type}")
    if length > MAX_PAYLOAD:
        raise ValueError(f"Packet payload exceeds limit: {length}")
    return ssl_read_exact(conn, length, timeout=timeout)


def _sync_pair(host: str, port: int, pin: str, key: rsa.RSAPrivateKey, timeout: float = 10.0) -> bool:
    """Synchronous pairing routine over pyOpenSSL."""
    clean_pin = "".join(ch for ch in pin if ch.isdigit())
    if len(clean_pin) != 6:
        raise ValueError(f"Pairing code must be 6 digits, got '{pin}'")

    raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw_sock.settimeout(timeout)
    raw_sock.connect((host, port))

    # Generate and load self-signed client certificate for mTLS
    cert = generate_self_signed_cert(key)
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, cert_pem)
    pkey = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM, key_pem)

    ctx = OpenSSL.SSL.Context(OpenSSL.SSL.TLS_CLIENT_METHOD)
    ctx.set_verify(OpenSSL.SSL.VERIFY_NONE, lambda *args: True)
    ctx.use_certificate(x509)
    ctx.use_privatekey(pkey)

    conn = OpenSSL.SSL.Connection(ctx, raw_sock)
    conn.set_connect_state()

    try:
        ssl_handshake(conn, timeout=timeout)
        ekm = conn.export_keying_material(EKM_LABEL, 64)
        if not ekm or len(ekm) != 64:
            raise RuntimeError("Failed to export keying material from TLS session")

        # 1. SPAKE2 message exchange
        spake = Spake2(alice=True, my_name=CLIENT_NAME, their_name=SERVER_NAME)
        client_spake_msg = spake.generate(clean_pin.encode("utf-8") + ekm)
        ssl_sendall(conn, packet(MSG_SPAKE, client_spake_msg), timeout=timeout)

        server_spake_msg = ssl_read_packet(conn, MSG_SPAKE, timeout=timeout)
        shared_key = spake.process(server_spake_msg)

        # 2. Derive AES key
        aes_key = hkdf_adb(shared_key, HKDF_INFO, 16)
        aesgcm = AESGCM(aes_key)

        # 3. Send Client Peer Info (RSA public key)
        adb_pubkey = get_adb_public_key_string(key)
        info_payload = bytearray(PEER_INFO_SIZE)
        pub_bytes = (adb_pubkey + "\x00").encode("utf-8")
        if len(pub_bytes) > PEER_INFO_SIZE - 1:
            raise ValueError("Public key exceeds peer info buffer")
        info_payload[1 : 1 + len(pub_bytes)] = pub_bytes

        nonce0 = struct.pack("<Q", 0) + b"\x00\x00\x00\x00"
        encrypted_client_info = aesgcm.encrypt(nonce0, bytes(info_payload), None)
        ssl_sendall(conn, packet(MSG_PEER_INFO, encrypted_client_info), timeout=timeout)

        # 4. Read & verify Server Peer Info
        encrypted_server_info = ssl_read_packet(conn, MSG_PEER_INFO, timeout=timeout)
        try:
            aesgcm.decrypt(nonce0, encrypted_server_info, None)
        except Exception as err:
            raise ValueError("Pairing verification failed - invalid pairing code") from err

        _LOGGER.info("Successfully paired with Android TV device at %s:%s", host, port)
        return True

    finally:
        try:
            conn.close()
        except Exception:
            pass
        try:
            raw_sock.close()
        except Exception:
            pass


async def pair_device(
    host: str,
    port: int,
    pin: str,
    key: rsa.RSAPrivateKey,
    timeout: float = 10.0,
) -> bool:
    """Asynchronously pair with an Android 11+ device using its 6-digit code."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_pair, host, port, pin, key, timeout)
