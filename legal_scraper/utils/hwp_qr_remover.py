"""HWP 파일의 BinData 이미지를 흰색 1x1 BMP로 교체 (QR 코드 제거).

의존성: olefile (pip install olefile)
사용법:
    from utils.hwp_qr_remover import remove_qr
    cleaned_bytes = remove_qr(original_hwp_bytes)
"""
import shutil
import struct
import tempfile
import zlib
from pathlib import Path

import olefile


def _make_1x1_bmp() -> bytes:
    """1x1 흰색 BMP 바이너리 생성 (58바이트)."""
    pixel_data = b"\xff\xff\xff\x00"  # BGR 24bit + 행 4바이트 정렬 패딩
    dib_header_size = 40
    pixel_offset = 14 + dib_header_size
    file_size = pixel_offset + len(pixel_data)
    bmp_header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, pixel_offset)
    dib_header = struct.pack(
        "<IiiHHIIiiII",
        dib_header_size, 1, 1, 1, 24, 0, len(pixel_data), 2835, 2835, 0, 0,
    )
    return bmp_header + dib_header + pixel_data


# 모듈 로드 시 1회만 생성 (raw deflate, zlib 헤더/체크섬 제거)
_MINI_BMP_COMPRESSED = zlib.compress(_make_1x1_bmp())[2:-4]


def remove_qr(hwp_bytes: bytes) -> bytes:
    """HWP 바이트에서 BinData 이미지를 모두 제거하여 반환.

    OLE2 BinData 스트림을 1x1 흰색 BMP(raw deflate)로 교체.
    원본 스트림 크기보다 작으면 null 패딩으로 맞춤.
    """
    with tempfile.NamedTemporaryFile(suffix=".hwp", delete=False) as f:
        f.write(hwp_bytes)
        src = Path(f.name)

    dst = src.with_suffix(".out.hwp")
    try:
        shutil.copy2(src, dst)
        ole = olefile.OleFileIO(str(dst), write_mode=True)
        for stream in ole.listdir():
            if stream[0] != "BinData":
                continue
            path = "/".join(stream)
            orig_size = ole.get_size(path)
            if orig_size < len(_MINI_BMP_COMPRESSED):
                continue  # 교체 데이터보다 작은 스트림은 건드리지 않음
            replacement = _MINI_BMP_COMPRESSED + b"\x00" * (orig_size - len(_MINI_BMP_COMPRESSED))
            ole.write_stream(path, replacement)
        ole.close()
        return dst.read_bytes()
    finally:
        src.unlink(missing_ok=True)
        dst.unlink(missing_ok=True)
