"""Async ADB client supporting Android 11+ TLS 1.3 Wireless Debugging."""

from __future__ import annotations

import asyncio
import logging
import os
import ssl
import tempfile
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from .crypto import generate_self_signed_cert
from .protocol import (
    A_VERSION,
    AUTH,
    CLSE,
    CNXN,
    MAX_PAYLOAD,
    OKAY,
    OPEN,
    STLS,
    WRTE,
    AdbMessage,
    decode_header,
    encode_packet,
)

_LOGGER = logging.getLogger(__name__)


class AdbError(Exception):
    """Base error for ADB communication."""


class AdbConnectionError(AdbError):
    """Raised when connection cannot be established or is broken."""


class AdbAuthError(AdbError):
    """Raised when the device refuses the client certificate or is not paired."""


class AdbTimeoutError(AdbError):
    """Raised when an operation times out."""


class _AdbStream:
    def __init__(self, local_id: int) -> None:
        self.local_id = local_id
        self.remote_id: int | None = None
        self.opened = asyncio.Event()
        self.done = asyncio.Event()
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()


class AndroidTvAdbClient:
    """Async ADB Client for Android TV over TLS 1.3."""

    def __init__(
        self,
        host: str,
        port: int,
        key: rsa.RSAPrivateKey,
    ) -> None:
        self.host = host
        self.port = port
        self.key = key
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._reader_task: asyncio.Task | None = None
        self._streams: dict[int, _AdbStream] = {}
        self._next_stream_id = 1
        self._write_lock = asyncio.Lock()
        self._connected = False
        self._max_payload = MAX_PAYLOAD
        self._ssl_ctx: ssl.SSLContext | None = None
        self._last_heard: float = 0.0

    @property
    def is_connected(self) -> bool:
        return self._connected and self._writer is not None and not self._writer.is_closing()

    @property
    def last_heard(self) -> float:
        """Timestamp of last received packet from the device."""
        return self._last_heard

    def update_port(self, port: int) -> None:
        """Update the dynamic connect port discovered from mDNS."""
        if self.port != port:
            _LOGGER.info("Updating ADB connect port for %s from %s to %s", self.host, self.port, port)
            self.port = port

    def _build_ssl_context(self) -> ssl.SSLContext:
        """Build an SSLContext configured with our client certificate and private key."""
        cert = generate_self_signed_cert(self.key)
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        key_pem = self.key.private_bytes(
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

    async def connect(self, timeout: float = 10.0) -> None:
        """Connect to the device, execute STLS upgrade and complete ADB handshake."""
        if self.is_connected:
            return

        await self.disconnect()

        _LOGGER.debug("Connecting to %s:%s", self.host, self.port)
        try:
            connect_coro = asyncio.open_connection(self.host, self.port)
            self._reader, self._writer = await asyncio.wait_for(connect_coro, timeout=timeout)
        except Exception as err:
            raise AdbConnectionError(f"Failed to connect to {self.host}:{self.port}: {err}") from err

        try:
            # 1. Send plain initial CNXN packet
            await self._send_packet(CNXN, A_VERSION, MAX_PAYLOAD, b"host::\x00")

            # 2. Expect STLS packet
            msg = await self._read_direct_packet(timeout=timeout)
            if msg.cmd == STLS:
                _LOGGER.debug("Received STLS negotiation from %s:%s, upgrading to TLS 1.3", self.host, self.port)
                # Reply with STLS ack
                await self._send_packet(STLS, msg.arg0, 0, b"")

                if self._ssl_ctx is None:
                    loop = asyncio.get_running_loop()
                    self._ssl_ctx = await loop.run_in_executor(None, self._build_ssl_context)

                # Upgrade socket to TLS
                await self._writer.start_tls(self._ssl_ctx)

                # Read CNXN inside TLS
                try:
                    msg = await self._read_direct_packet(timeout=4.0)
                except (TimeoutError, AdbTimeoutError):
                    _LOGGER.debug("Re-sending CNXN over active TLS channel")
                    await self._send_packet(CNXN, A_VERSION, MAX_PAYLOAD, b"host::\x00")
                    msg = await self._read_direct_packet(timeout=timeout)

            if msg.cmd == AUTH:
                raise AdbAuthError("Device rejected connection: not paired with this key")
            if msg.cmd != CNXN:
                raise AdbConnectionError(f"Expected CNXN response, got {msg.cmd_name}")

            self._max_payload = max(4096, min(msg.arg1, MAX_PAYLOAD))
            self._connected = True
            self._last_heard = time.time()
            _LOGGER.info(
                "ADB connection established to %s:%s (max_payload=%s)", self.host, self.port, self._max_payload
            )

            # Start background reader pump
            self._reader_task = asyncio.create_task(self._reader_loop())

        except Exception:
            await self.disconnect()
            raise

    async def disconnect(self) -> None:
        """Close connection and clean up active streams."""
        self._connected = False
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        self._reader_task = None

        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self._reader = None
        self._writer = None

        for stream in self._streams.values():
            stream.done.set()
        self._streams.clear()

    async def _send_packet(self, cmd: int, arg0: int, arg1: int, data: bytes = b"") -> None:
        """Send an ADB packet safely under the write lock."""
        if self._writer is None:
            raise AdbConnectionError("Writer is closed")
        pkt = encode_packet(cmd, arg0, arg1, data)
        async with self._write_lock:
            self._writer.write(pkt)
            await self._writer.drain()

    async def _read_direct_packet(self, timeout: float = 10.0) -> AdbMessage:
        """Read a single packet directly from the stream before starting the pump."""
        if self._reader is None:
            raise AdbConnectionError("Reader is closed")
        try:
            header_bytes = await asyncio.wait_for(self._reader.readexactly(24), timeout=timeout)
            cmd, arg0, arg1, length = decode_header(header_bytes)
            payload = b""
            if length > 0:
                payload = await asyncio.wait_for(self._reader.readexactly(length), timeout=timeout)
            self._last_heard = time.time()
            return AdbMessage(cmd, arg0, arg1, payload)
        except TimeoutError as err:
            raise AdbTimeoutError("Timed out reading ADB packet") from err
        except Exception as err:
            raise AdbConnectionError(f"Error reading direct packet: {err}") from err

    async def _reader_loop(self) -> None:
        """Background pump reading ADB packets and routing them to streams."""
        try:
            while self._connected and self._reader is not None:
                header_bytes = await self._reader.readexactly(24)
                cmd, arg0, arg1, length = decode_header(header_bytes)
                payload = b""
                if length > 0:
                    payload = await self._reader.readexactly(length)

                self._last_heard = time.time()

                stream = self._streams.get(arg1)
                if not stream:
                    if cmd == OKAY and arg0 != 0:
                        # Remote stream opened for something we dropped; send CLSE
                        try:
                            await self._send_packet(CLSE, arg1, arg0, b"")
                        except Exception:
                            pass
                    continue

                if cmd == OKAY:
                    if stream.remote_id is None:
                        stream.remote_id = arg0
                        stream.opened.set()
                elif cmd == WRTE:
                    await stream.queue.put(payload)
                    # Acknowledge data so the device keeps transmitting
                    if stream.remote_id is not None:
                        await self._send_packet(OKAY, stream.local_id, stream.remote_id, b"")
                elif cmd == CLSE:
                    stream.done.set()
                    if stream.remote_id is not None:
                        try:
                            await self._send_packet(CLSE, stream.local_id, stream.remote_id, b"")
                        except Exception:
                            pass
                    self._streams.pop(stream.local_id, None)

        except asyncio.CancelledError:
            pass
        except Exception as err:
            _LOGGER.debug("Reader loop ended for %s:%s: %s", self.host, self.port, err)
        finally:
            self._connected = False
            for s in self._streams.values():
                s.done.set()

    async def _open_service_stream(self, destination: str, timeout: float = 12.0) -> _AdbStream:
        """Open an ADB stream to a named service (e.g. 'shell:<cmd>' or 'exec:<cmd>')."""
        if not self.is_connected:
            await self.connect()

        local_id = self._next_stream_id
        self._next_stream_id += 1

        stream = _AdbStream(local_id)
        self._streams[local_id] = stream

        try:
            payload = f"{destination}\x00".encode()
            await self._send_packet(OPEN, local_id, 0, payload)

            # Wait for stream to be accepted
            try:
                await asyncio.wait_for(stream.opened.wait(), timeout=timeout)
            except TimeoutError as err:
                raise AdbTimeoutError(f"Device did not open stream for service: {destination}") from err

            return stream
        except Exception:
            self._streams.pop(local_id, None)
            raise

    async def _read_stream(self, stream: _AdbStream, timeout: float = 12.0) -> bytes:
        """Accumulate output from an opened stream until CLSE or done."""
        try:
            output = bytearray()
            while not stream.done.is_set() or not stream.queue.empty():
                try:
                    chunk = await asyncio.wait_for(stream.queue.get(), timeout=timeout)
                    output.extend(chunk)
                except TimeoutError:
                    if stream.done.is_set():
                        break
                    raise AdbTimeoutError("Timed out waiting for stream output")
            return bytes(output)
        finally:
            self._streams.pop(stream.local_id, None)

    async def exec_raw(self, command: str, timeout: float = 12.0) -> bytes:
        """Execute a binary command via exec: service (bypasses PTY CRLF mangling)."""
        stream = await self._open_service_stream(f"exec:{command}", timeout=timeout)
        return await self._read_stream(stream, timeout=timeout)

    async def shell_raw(self, command: str, timeout: float = 12.0) -> bytes:
        """Execute a shell command on the device and return raw binary output."""
        stream = await self._open_service_stream(f"shell:{command}", timeout=timeout)
        return await self._read_stream(stream, timeout=timeout)

    async def shell(self, command: str, timeout: float = 10.0) -> str:
        """Execute a shell command on the device and return decoded string output."""
        raw = await self.shell_raw(command, timeout=timeout)
        return raw.decode("utf-8", errors="replace")

    async def alive(self, timeout: float = 3.0) -> bool:
        """Probe connection liveness with a lightweight shell ping."""
        if not self.is_connected:
            return False
        try:
            res = await self.shell("echo 1", timeout=timeout)
            return "1" in res
        except Exception:
            return False
