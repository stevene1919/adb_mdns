"""Cryptographic helpers for Android TV ADB.

Generates RSA keypairs, ADB public key wire format, and self-signed X.509 certificates.
"""

from __future__ import annotations

import base64
import datetime
import os
import ssl
import struct
import tempfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_keypair() -> tuple[rsa.RSAPrivateKey, str]:
    """Generate a new 2048-bit RSA key and return (key_object, pem_private_key_str)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    return key, pem


def load_private_key(pem_str: str) -> rsa.RSAPrivateKey:
    """Load an RSA private key from a PEM string."""
    key = serialization.load_pem_private_key(pem_str.encode("utf-8"), password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise ValueError("Key is not an RSA private key")
    return key


def get_adb_public_key_string(key: rsa.RSAPrivateKey, comment: str = "adb_mdns@homeassistant") -> str:
    """Convert an RSA private key's public component into ADB's wire text format.

    Format: base64(524-byte struct) + ' ' + comment
    Structure:
      - uint32: words (64)
      - uint32: n0inv (-1/n mod 2^32)
      - uint32[64]: n (modulus as 64 32-bit little-endian words)
      - uint32[64]: rr (R^2 mod n as 64 32-bit little-endian words, where R = 2^2048)
      - uint32: e (public exponent)
    """
    pub = key.public_key().public_numbers()
    n = pub.n
    e = pub.e

    r32 = 1 << 32
    r = 1 << 2048
    n0inv = (-pow(n % r32, -1, r32)) % r32
    rr = (r * r) % n

    buf = bytearray()
    buf.extend(struct.pack("<II", 64, n0inv))
    for i in range(64):
        buf.extend(struct.pack("<I", (n >> (32 * i)) & 0xFFFFFFFF))
    for i in range(64):
        buf.extend(struct.pack("<I", (rr >> (32 * i)) & 0xFFFFFFFF))
    buf.extend(struct.pack("<I", e))

    b64 = base64.b64encode(buf).decode("ascii")
    return f"{b64} {comment}"


def generate_self_signed_cert(
    key: rsa.RSAPrivateKey,
    common_name: str = "adb_mdns",
) -> x509.Certificate:
    """Generate a self-signed X.509 certificate for TLS 1.3 client authentication."""
    name = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .sign(key, hashes.SHA256())
    )
    return cert


def build_client_ssl_context(key: rsa.RSAPrivateKey) -> ssl.SSLContext:
    """Build an SSLContext configured with our client certificate and private key."""
    cert = generate_self_signed_cert(key)
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    with tempfile.NamedTemporaryFile("wb", delete=False) as f_cert:
        f_cert.write(cert_pem)
        cert_path = f_cert.name

    with tempfile.NamedTemporaryFile("wb", delete=False) as f_key:
        f_key.write(key_pem)
        key_path = f_key.name

    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
        return ctx
    finally:
        try:
            os.unlink(cert_path)
        except Exception:
            pass
        try:
            os.unlink(key_path)
        except Exception:
            pass

