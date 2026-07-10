"""IDs estáticos: crc32 do nome (determinístico entre execuções/máquinas)."""
import zlib


def sid(name: str) -> int:
    return zlib.crc32(name.encode("utf-8"))
