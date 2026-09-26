from __future__ import annotations

import argparse
import struct
from pathlib import Path

from PIL import Image


HEADER_SIZE = 32


def read_tex(path: Path) -> tuple[bytes, Image.Image]:
    data = path.read_bytes()
    if len(data) < HEADER_SIZE:
        raise ValueError(f"TEX header is truncated: {path}")
    width, height = struct.unpack_from("<II", data, 8)
    expected = HEADER_SIZE + width * height * 4
    if len(data) != expected:
        raise ValueError(
            f"Unexpected TEX size: actual={len(data)} expected={expected}"
        )
    image = Image.frombytes(
        "RGBA", (width, height), data[HEADER_SIZE:], "raw", "BGRA"
    )
    return data[:HEADER_SIZE], image


def write_tex(path: Path, header: bytes, image: Image.Image) -> None:
    if len(header) != HEADER_SIZE:
        raise ValueError("TEX header must be 32 bytes")
    width, height = struct.unpack_from("<II", header, 8)
    rgba = image.convert("RGBA")
    if rgba.size != (width, height):
        raise ValueError(
            f"Image size mismatch: actual={rgba.size} expected={(width, height)}"
        )
    pixels = rgba.tobytes("raw", "BGRA")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + pixels)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Decode or encode BloodRayne 2 raw BGRA TEX files"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    decode = subparsers.add_parser("decode")
    decode.add_argument("tex", type=Path)
    decode.add_argument("png", type=Path)
    decode.add_argument(
        "--dark-preview",
        action="store_true",
        help="Composite the texture over dark gray for visual inspection",
    )

    encode = subparsers.add_parser("encode")
    encode.add_argument("template", type=Path)
    encode.add_argument("png", type=Path)
    encode.add_argument("tex", type=Path)

    args = parser.parse_args()
    if args.command == "decode":
        _, image = read_tex(args.tex)
        if args.dark_preview:
            background = Image.new("RGBA", image.size, (32, 32, 32, 255))
            image = Image.alpha_composite(background, image)
        args.png.parent.mkdir(parents=True, exist_ok=True)
        image.save(args.png)
        print(f"Decoded {args.tex} -> {args.png} ({image.width}x{image.height})")
    else:
        header, _ = read_tex(args.template)
        with Image.open(args.png) as image:
            write_tex(args.tex, header, image)
        print(f"Encoded {args.png} -> {args.tex}")


if __name__ == "__main__":
    main()
