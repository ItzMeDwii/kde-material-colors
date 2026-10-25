"""Chromium ``Local Storage`` LevelDB: read one value, append a newer one.

Chromium keeps web storage in ``<profile>/Local Storage/leveldb`` - a plain
LevelDB database.  Map entries are ``"_" + <serialized storage key> + <map
separator> + <script key>`` with the script string behind a one-byte encoding
tag as value (``local_storage_leveldb.{h,cc}``, database version 1 under the
``META:`` keys).

Two operations are needed, so two are implemented:

``LocalStorage.read(key)``
    Newest value on disk.  Write-ahead logs (``*.log``) are replayed and, for
    values that were already compacted, the ``.ldb`` tables are searched
    through their index blocks - including Snappy-compressed blocks.

``LocalStorage.write(key, value)``
    Appends one properly framed log record with a sequence number above both
    the manifest's last sequence and the newest sequence in the logs, which
    LevelDB replays when it opens the database next.  The log file used is the
    manifest's current log number; a record that would cross the 32 KiB log
    block boundary is preceded by zero padding, as LevelDB itself does.

Writing requires the database to be closed: Chromium holds an ``fcntl`` lock on
``LOCK`` and keeps its own file offset, so a concurrent append can be truncated
or overwritten (``locked()`` reports that).
"""

from __future__ import annotations

import fcntl
import os
import struct
from pathlib import Path

LOG_BLOCK_SIZE = 32768
_HEADER = 7
_FULL, _FIRST, _MIDDLE, _LAST, _ZERO = 1, 2, 3, 4, 0
_NO_COMPRESSION, _SNAPPY = 0, 1
_TABLE_MAGIC = 0xDB4775248B80FB57


class StorageError(RuntimeError):
    """The LevelDB directory cannot be read or patched."""


# --- CRC32C (leveldb's table checksum, Castagnoli poly, reflected) -----------


def _crc32c_table() -> tuple[int, ...]:
    table = []
    for index in range(256):
        crc = index
        for _ in range(8):
            crc = (crc >> 1) ^ 0x82F63B78 if crc & 1 else crc >> 1
        table.append(crc)
    return tuple(table)


_CRC_TABLE = _crc32c_table()


def crc32c(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for byte in data:
        crc = _CRC_TABLE[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF


def _mask_crc(crc: int) -> int:
    return (((crc >> 15) | (crc << 17)) + 0xA282EAD8) & 0xFFFFFFFF


# --- primitives --------------------------------------------------------------


def _varint(buf: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7


def _put_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


# --- write-ahead logs --------------------------------------------------------


def _log_records(data: bytes) -> list[bytes]:
    """Reassembled records of one log file (a truncated tail is ignored)."""
    records: list[bytes] = []
    buffered = b""
    fragmented = False
    pos = 0
    while pos + _HEADER <= len(data):
        in_block = pos % LOG_BLOCK_SIZE
        remaining = LOG_BLOCK_SIZE - in_block
        if remaining < _HEADER:
            pos += remaining
            continue
        _, length, kind = struct.unpack_from("<IHB", data, pos)
        if kind == _ZERO and length == 0:  # padding to the next block
            pos += remaining
            continue
        if length > remaining - _HEADER:
            break
        payload = data[pos + _HEADER : pos + _HEADER + length]
        pos += _HEADER + length
        if kind == _FULL:
            records.append(payload)
        elif kind == _FIRST:
            buffered, fragmented = payload, True
        elif kind == _MIDDLE and fragmented:
            buffered += payload
        elif kind == _LAST and fragmented:
            records.append(buffered + payload)
            buffered, fragmented = b"", False
        else:
            buffered, fragmented = b"", False
    return records


def _batch_entries(payload: bytes):
    """Yield ``(sequence, key, value)`` of one WriteBatch (values may be None)."""
    if len(payload) < 12:
        return
    sequence = struct.unpack_from("<Q", payload, 0)[0]
    count = struct.unpack_from("<I", payload, 8)[0]
    pos = 12
    for _ in range(count):
        if pos >= len(payload):
            return
        kind = payload[pos]
        pos += 1
        klen, pos = _varint(payload, pos)
        key = payload[pos : pos + klen]
        pos += klen
        if kind != 1:
            yield sequence, key, None
            continue
        vlen, pos = _varint(payload, pos)
        yield sequence, key, payload[pos : pos + vlen]
        pos += vlen


def _log_entries(data: bytes):
    for payload in _log_records(data):
        try:
            yield from _batch_entries(payload)
        except (IndexError, ValueError):
            continue


# --- Snappy (raw format, as used for table blocks) ---------------------------


def snappy_decompress(data: bytes) -> bytes:
    length, pos = _varint(data, 0)
    out = bytearray()
    end = len(data)
    while len(out) < length:
        if pos >= end:
            raise StorageError("snappy: truncated block")
        tag = data[pos]
        pos += 1
        kind = tag & 3
        if kind == 0:  # literal
            size = tag >> 2
            if size < 60:
                size += 1
            else:
                extra = size - 59
                size = int.from_bytes(data[pos : pos + extra], "little") + 1
                pos += extra
            out += data[pos : pos + size]
            pos += size
            continue
        if kind == 1:
            size = ((tag >> 2) & 0x7) + 4
            offset = ((tag >> 5) << 8) | data[pos]
            pos += 1
        elif kind == 2:
            size = (tag >> 2) + 1
            offset = int.from_bytes(data[pos : pos + 2], "little")
            pos += 2
        else:
            size = (tag >> 2) + 1
            offset = int.from_bytes(data[pos : pos + 4], "little")
            pos += 4
        start = len(out) - offset
        if start < 0:
            raise StorageError("snappy: offset before the output start")
        if offset >= size:  # fast path: no overlap
            out += out[start : start + size]
        else:
            for index in range(size):
                out.append(out[start + index])
    return bytes(out)


# --- tables (``.ldb``) -------------------------------------------------------


def _block(data: bytes, offset: int, size: int) -> bytes:
    raw = data[offset : offset + size]
    if len(raw) != size:
        raise StorageError("truncated table block")
    kind = data[offset + size]
    if kind == _NO_COMPRESSION:
        return raw
    if kind == _SNAPPY:
        return snappy_decompress(raw)
    raise StorageError(f"unknown block compression {kind}")


def _entries(block: bytes):
    """Yield ``(key, value)`` pairs of a block (data or index)."""
    count = struct.unpack_from("<I", block, len(block) - 4)[0]
    limit = len(block) - 4 - count * 4
    if limit < 0:
        raise StorageError("bad block restart array")
    pos = 0
    key = b""
    while pos < limit:
        shared, pos = _varint(block, pos)
        fresh, pos = _varint(block, pos)
        vlen, pos = _varint(block, pos)
        key = key[:shared] + block[pos : pos + fresh]
        pos += fresh
        yield key, block[pos : pos + vlen]
        pos += vlen


def _handle_at(buf: bytes, pos: int) -> tuple[tuple[int, int], int]:
    offset, pos = _varint(buf, pos)
    size, pos = _varint(buf, pos)
    return (offset, size), pos


def _handle(value: bytes) -> tuple[int, int]:
    handle, pos = _handle_at(value, 0)
    if pos != len(value):
        raise StorageError("not a block handle")
    return handle


def _table_newest(path: Path, data: bytes, marker: bytes) -> tuple[int, bytes] | None:
    """Newest table entry for ``marker``, located through the index block."""
    footer = data[-48:]
    if struct.unpack_from("<Q", footer, 40)[0] != _TABLE_MAGIC:
        raise StorageError(f"{path.name}: not a table file")
    _, pos = _handle_at(footer, 0)  # metaindex handle: filter policy, unused here
    index, _ = _handle_at(footer, pos)

    # LevelDB keeps one index block whose keys are the last key of each data
    # block, so the block that can hold ``marker`` is the first one whose key is
    # not smaller than it.
    entries = _entries(_block(data, *index))
    handle = None
    for key, value in entries:
        if key >= marker:
            handle = _handle(value)
            break
    if handle is None:
        return None

    newest: tuple[int, bytes] | None = None
    for key, value in _entries(_block(data, *handle)):
        if key[: len(marker)] != marker or len(key) != len(marker) + 8:
            continue
        sequence = int.from_bytes(key[len(marker) :], "little") >> 8
        if newest is None or sequence > newest[0]:
            newest = (sequence, value)
    return newest


# --- manifest ----------------------------------------------------------------


_MANIFEST_TAGS = {2: "log_number", 3: "next_file_number", 4: "last_sequence", 9: "prev_log_number"}


def _manifest(db_dir: Path) -> dict[str, int]:
    """Log number, last sequence, … of the current database state."""
    current = db_dir / "CURRENT"
    try:
        name = current.read_text(encoding="utf-8").strip()
        data = (db_dir / name).read_bytes()
    except OSError as exc:
        raise StorageError(f"cannot read {current}: {exc}") from exc
    state: dict[str, int] = {}
    for payload in _log_records(data):
        pos = 0
        try:
            while pos < len(payload):
                tag, pos = _varint(payload, pos)
                if tag in (1, 5):  # comparator / compact pointer: length-prefixed
                    length, pos = _varint(payload, pos)
                    pos += length
                elif tag in (2, 3, 4, 9):  # log number / next file / last seq / prev log
                    state[_MANIFEST_TAGS[tag]], pos = _varint(payload, pos)
                elif tag == 6:  # deleted file
                    _, pos = _varint(payload, pos)
                    _, pos = _varint(payload, pos)
                elif tag == 7:  # new file
                    for _ in range(3):
                        _, pos = _varint(payload, pos)
                    for _ in range(2):
                        length, pos = _varint(payload, pos)
                        pos += length
                else:
                    break
        except (IndexError, ValueError):
            continue
    return state


# --- public API --------------------------------------------------------------


class LocalStorage:
    """One Chromium Local Storage LevelDB directory."""

    def __init__(self, directory: Path | str):
        self.directory = Path(directory)

    # -- state ---------------------------------------------------------------
    def locked(self) -> bool:
        """True while a process (Chromium) holds the database lock."""
        lock = self.directory / "LOCK"
        if not lock.exists():
            return False
        try:
            with open(lock, "r+b") as handle:
                fcntl.lockf(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.lockf(handle, fcntl.LOCK_UN)
        except OSError:
            return True
        return False

    def _scan(self, marker: bytes) -> tuple[tuple[int, bytes] | None, int]:
        """Newest entry for ``marker`` and the highest sequence number seen."""
        newest: tuple[int, bytes] | None = None
        highest = 0
        for path in sorted(self.directory.glob("*.log")):
            data = path.read_bytes()
            if marker not in data:
                continue
            for sequence, key, value in _log_entries(data):
                highest = max(highest, sequence)
                if value is not None and key.startswith(marker):
                    if newest is None or sequence > newest[0]:
                        newest = (sequence, value)
        for path in sorted(self.directory.glob("*.ldb")):
            data = path.read_bytes()
            if marker not in data:
                continue
            found = _table_newest(path, data, marker)
            if found and (newest is None or found[0] > newest[0]):
                newest = found
        return newest, highest

    # -- reading/writing -----------------------------------------------------
    def read(self, marker: bytes) -> bytes | None:
        """Newest stored value for a key prefix (``None`` when absent)."""
        newest, _ = self._scan(marker)
        return newest[1] if newest else None

    def _log_number(self, state: dict[str, int]) -> int:
        """Current log file number; a fresh one when the manifest is unusable."""
        number = state.get("log_number")
        if number:
            return number
        numbers = []
        for path in self.directory.iterdir():
            if path.suffix in (".log", ".ldb"):
                try:
                    numbers.append(int(path.stem))
                except ValueError:
                    continue
        return max(numbers, default=0) + 1

    def write(self, marker: bytes, value: bytes) -> int:
        """Append ``value`` for ``marker``; returns the new sequence number."""
        existing, highest = self._scan(marker)
        state = _manifest(self.directory)
        sequence = max(highest, state.get("last_sequence", 0), existing[0] if existing else 0) + 1
        path = self.directory / f"{self._log_number(state):06d}.log"
        record = struct.pack("<QI", sequence, 1) + b"\x01"
        record += _put_varint(len(marker)) + marker
        record += _put_varint(len(value)) + value
        padding = b""
        size = path.stat().st_size if path.exists() else 0
        remainder = size % LOG_BLOCK_SIZE
        if remainder and LOG_BLOCK_SIZE - remainder < _HEADER + len(record):
            padding = b"\x00" * (LOG_BLOCK_SIZE - remainder)
        header = struct.pack("<IHB", _mask_crc(crc32c(bytes([_FULL]) + record)), len(record), _FULL)
        descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(descriptor, padding + header + record)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return sequence

    def verify(self, marker: bytes, expected: bytes) -> None:
        """Raise unless ``marker`` reads back as ``expected``."""
        found = self.read(marker)
        if found != expected:
            raise StorageError(f"patched value does not read back ({len(found) if found else 0} bytes)")
