"""SPAKE2 implementation over Edwards25519 for Android 11+ Wireless Debugging Pairing.

Direct Python translation of Android BoringSSL SPAKE2 curve points and protocol.
"""

from __future__ import annotations

import hashlib
import os
from typing import NamedTuple


class Pt(NamedTuple):
    x: int
    y: int
    z: int
    t: int


P = (1 << 255) - 19
L = (1 << 252) + 27742317777372353535851937790883648493
D = (-121665 * pow(121666, -1, P)) % P
D2 = (D << 1) % P
SQRT_M1 = pow(2, (P - 1) >> 2, P)
ZERO = Pt(0, 1, 1, 0)


def _le(b: bytes) -> int:
    return int.from_bytes(b, byteorder="little")


def _encode_y(y: int, odd: bool) -> bytes:
    raw = y.to_bytes((y.bit_length() + 7) // 8 or 1, byteorder="little")[:32]
    out = bytearray(raw.ljust(32, b"\x00"))
    if odd:
        out[31] |= 0x80
    return bytes(out)


def _add(a: Pt, b: Pt) -> Pt:
    aa = ((a.y - a.x) * (b.y - b.x)) % P
    bb = ((a.y + a.x) * (b.y + b.x)) % P
    cc = (a.t * D2 * b.t) % P
    dd = ((a.z << 1) * b.z) % P
    e = (bb - aa) % P
    f = (dd - cc) % P
    g = (dd + cc) % P
    h = (bb + aa) % P
    return Pt((e * f) % P, (g * h) % P, (f * g) % P, (e * h) % P)


def _neg(a: Pt) -> Pt:
    return Pt((-a.x) % P, a.y, a.z, (-a.t) % P)


def _mul(a: Pt, k: int) -> Pt:
    r = ZERO
    q = a
    bit_len = k.bit_length()
    for i in range(bit_len):
        if (k >> i) & 1:
            r = _add(r, q)
        q = _add(q, q)
    return r


def _encode(a: Pt) -> bytes:
    zi = pow(a.z, -1, P)
    x = (a.x * zi) % P
    y = (a.y * zi) % P
    return _encode_y(y, bool(x & 1))


def _decode(b: bytes) -> Pt | None:
    if len(b) != 32:
        return None
    odd = bool(b[31] & 0x80)
    c = bytearray(b)
    c[31] &= 0x7F
    y = int.from_bytes(c, "little")
    if y >= P:
        return None
    yy = (y * y) % P
    u = (yy - 1) % P
    v = (D * yy + 1) % P
    x = (u * pow(v, P - 2, P)) % P
    x = pow(x, (P + 3) >> 3, P)
    if (v * x * x - u) % P != 0:
        x = (x * SQRT_M1) % P
        if (v * x * x - u) % P != 0:
            return None
    if bool(x & 1) != odd:
        x = (-x) % P
    return Pt(x, y, 1, (x * y) % P)


M = _decode(bytes.fromhex("932581b409222652499d92cdece394a3ae5e1cb85cb870ac3030bbe477112ed1"))
assert M is not None
N = _decode(bytes.fromhex("2d803ae3e80adc51cab57648e5becb4bef79f45fd130ca4f497ddb623b76ce84"))
assert N is not None
_base_y = (4 * pow(5, -1, P)) % P
BASE = _decode(_encode_y(_base_y, False))
assert BASE is not None


class Spake2:
    """SPAKE2 over edwards25519 (BoringSSL implementation).

    Used in Android 11+ adb pair.
    """

    def __init__(
        self,
        alice: bool,
        my_name: bytes,
        their_name: bytes,
        random_secret: bytes | None = None,
    ) -> None:
        self.alice = alice
        self.my_name = my_name
        self.their_name = their_name
        rnd = random_secret if random_secret is not None else os.urandom(64)
        self.secret = (_le(rnd) % L) << 3
        self.my_msg: bytes | None = None
        self.password_hash: bytes | None = None
        self.password_scalar: int | None = None

    def generate(self, password: bytes) -> bytes:
        if self.my_msg is not None:
            raise RuntimeError("already generated")
        pw_hash = hashlib.sha512(password).digest()
        self.password_hash = pw_hash
        w = _le(pw_hash) % L
        self.password_scalar = w
        mask = _mul(M if self.alice else N, w)
        msg = _encode(_add(_mul(BASE, self.secret), mask))
        self.my_msg = msg
        return msg

    def process(self, their_msg: bytes) -> bytes:
        if self.my_msg is None or self.password_scalar is None or self.password_hash is None:
            raise RuntimeError("generate first")
        if len(their_msg) != 32:
            raise ValueError("bad pairing message size")
        q = _decode(their_msg)
        if q is None:
            raise ValueError("bad pairing message point")
        unmasked = _add(q, _neg(_mul(N if self.alice else M, self.password_scalar)))
        shared = _encode(_mul(unmasked, self.secret))

        sha = hashlib.sha512()

        def part(b: bytes) -> None:
            n = len(b).to_bytes(8, byteorder="little")
            sha.update(n)
            sha.update(b)

        if self.alice:
            part(self.my_name)
            part(self.their_name)
            part(self.my_msg)
            part(their_msg)
        else:
            part(self.their_name)
            part(self.my_name)
            part(their_msg)
            part(self.my_msg)

        part(shared)
        part(self.password_hash)
        return sha.digest()
