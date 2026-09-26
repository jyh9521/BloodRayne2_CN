from __future__ import annotations

import argparse
import re
from pathlib import Path

from pod3 import Pod3, patch_entries_fixed_capacity, sha256_file


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "_cn_project"
BASELINE = PROJECT / "baseline" / "LANGUAGE.POD"

EXPECTED_SHA256 = (
    "2E3E0797E147E58B7308D3FCEDBDF0A06CB433FB099FC24B8FB38943D8B358E4"
)
MSGLIST_NAME = r"WORLD\RU\MSGLIST.TXT"
PAIR_RE = re.compile(rb'"((?:[^"\\]|\\.)*)", "((?:[^"\\]|\\.)*)"')
ORIGINAL_CP932_FONT = bytes.fromhex(
    "82 6C 82 72 20 82 6F 83 53 83 56 83 62 83 4E"
)

MENU_PROBE_CP932 = {
    "New Game": "日本語",
    "Load Game": "漢字",
    "Options": "仮名",
    "Extras": "追加",
    "Quit": "終了",
}

MENU_PROBE_GBK = {
    "New Game": "新游戏",
    "Load Game": "载入游戏",
    "Options": "选项",
    "Extras": "额外内容",
    "Quit": "退出",
}

LEVEL_PROBE_CP932 = {
    r"WORLD\RU\0COMBAT.TXT": {
        "ost_single": "日本語",
        "ost_double": "漢字",
        "ost_triple": "仮名",
        "ost_quadruple": "追加",
    },
}

LEVEL_PROBE_GBK = {
    r"WORLD\RU\0COMBAT.TXT": {
        "ost_single": "中文显示测试",
        "ost_double": "简体中文",
        "ost_triple": "系统字体",
        "ost_quadruple": "编码路径正常",
    },
}

DIALOGUE_PROBE_GBK = {
    r"WORLD\RU\A1_MANSION_PART1.TXT": {
        "a1s1_mdhampir_1.wav": "达姆皮尔：简体中文显示测试。",
        "a1s1_rayne_12.wav": "莱恩：字幕编码路径正常。",
    },
}


def ascii_scrub(data: bytes) -> bytes:
    return bytes(byte if byte < 0x80 else ord("?") for byte in data)


def split_newline(line: bytes) -> tuple[bytes, bytes]:
    if line.endswith(b"\r\n"):
        return line[:-2], b"\r\n"
    if line.endswith(b"\n"):
        return line[:-1], b"\n"
    return line, b""


def set_header(lines: list[bytes], name: bytes, value: bytes) -> None:
    quoted_name = b'"' + name + b'"'
    for index, line in enumerate(lines[:-1]):
        body, newline = split_newline(line)
        if body.strip() not in {name, quoted_name}:
            continue
        _, value_newline = split_newline(lines[index + 1])
        lines[index + 1] = value + (value_newline or newline)
        return
    raise ValueError(f"Header not found: {name!r}")


def build_msglist(
    source: bytes, font: str, encoding: str, menu_probe: dict[str, str]
) -> bytes:
    lines = ascii_scrub(source).splitlines(keepends=True)
    set_header(lines, b"Double byte support", b'"1"')
    if font == "original":
        font_bytes = ORIGINAL_CP932_FONT
    else:
        font_bytes = font.encode("ascii")
    set_header(lines, b"Double byte font", b'"' + font_bytes + b'"')
    scrubbed = b"".join(lines)

    def replace_pair(match: re.Match[bytes]) -> bytes:
        key_bytes = match.group(1)
        try:
            key = key_bytes.decode("ascii")
        except UnicodeDecodeError:
            return match.group(0)
        value = menu_probe.get(key)
        if value is None:
            return match.group(0)
        return b'"' + key_bytes + b'", "' + value.encode(encoding) + b'"'

    return PAIR_RE.sub(replace_pair, scrubbed)


def build_level(
    source: bytes, translations: dict[str, str], encoding: str
) -> bytes:
    pending = dict(translations)
    result: list[bytes] = []
    for line in ascii_scrub(source).splitlines(keepends=True):
        body, newline = split_newline(line)
        if b",," not in body:
            result.append(line)
            continue
        key_bytes, _ = body.split(b",,", 1)
        key = key_bytes.decode("ascii", errors="strict")
        if key not in pending:
            result.append(line)
            continue
        result.append(
            key_bytes + b",," + pending.pop(key).encode(encoding) + newline
        )
    if pending:
        raise ValueError(f"Level keys were not found: {sorted(pending)}")
    return b"".join(result)


def build_dialogue(
    source: bytes, translations: dict[str, str], encoding: str
) -> bytes:
    pending = dict(translations)
    result: list[bytes] = []
    for line in ascii_scrub(source).splitlines(keepends=True):
        body, newline = split_newline(line)
        columns = body.split(b",", 2)
        if len(columns) != 3:
            result.append(line)
            continue
        key = columns[0].decode("ascii", errors="strict")
        if key not in pending:
            result.append(line)
            continue
        result.append(
            columns[0]
            + b","
            + columns[1]
            + b","
            + pending.pop(key).encode(encoding)
            + newline
        )
    if pending:
        raise ValueError(f"Dialogue keys were not found: {sorted(pending)}")
    return b"".join(result)


def build(font: str, encoding: str, build_name: str) -> None:
    if not BASELINE.exists():
        raise FileNotFoundError(f"Missing baseline: {BASELINE}")
    actual = sha256_file(BASELINE)
    if actual != EXPECTED_SHA256:
        raise ValueError(
            f"Baseline hash mismatch: expected={EXPECTED_SHA256} actual={actual}"
        )
    source = BASELINE.read_bytes()
    pod = Pod3(source)
    if encoding == "cp932":
        menu_probe = MENU_PROBE_CP932
        level_probe = LEVEL_PROBE_CP932
        dialogue_probe: dict[str, dict[str, str]] = {}
    elif encoding == "gbk":
        menu_probe = MENU_PROBE_GBK
        level_probe = LEVEL_PROBE_GBK
        dialogue_probe = DIALOGUE_PROBE_GBK
    else:
        raise ValueError(f"Unsupported probe encoding: {encoding}")
    replacements = {
        MSGLIST_NAME: build_msglist(
            pod.read_entry(MSGLIST_NAME), font, encoding, menu_probe
        ),
    }
    for name, translations in level_probe.items():
        replacements[name] = build_level(
            pod.read_entry(name), translations, encoding
        )
    for name, translations in dialogue_probe.items():
        replacements[name] = build_dialogue(
            pod.read_entry(name), translations, encoding
        )
    build_path = PROJECT / "build" / build_name / "LANGUAGE.POD"
    build_path.parent.mkdir(parents=True, exist_ok=True)
    build_path.write_bytes(patch_entries_fixed_capacity(source, replacements))
    print(f"Built {build_path}")
    print(f"SHA-256: {sha256_file(build_path)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--font",
        default="original",
        help='Use "original" for the CP932 name or an ASCII face name',
    )
    parser.add_argument(
        "--encoding",
        choices=("cp932", "gbk"),
        default="cp932",
    )
    parser.add_argument("--build-name", default="dbcs_probe")
    args = parser.parse_args()
    if args.encoding == "gbk" and args.font == "original":
        parser.error("--encoding gbk requires an ASCII --font")
    build(args.font, args.encoding, args.build_name)


if __name__ == "__main__":
    main()
