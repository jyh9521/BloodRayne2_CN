"""Static voice-subtitle checks; never starts the game."""
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import pefile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "_cn_project" / "tools"))
from pod3 import Pod3
from build_full_translation import encode_text

MANIFEST = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def main(mode):
    originals = MANIFEST["before"]
    for name in ("COMMON.POD", "W32ENSND.POD"):
        assert sha(ROOT / name) == originals[name], name
    scripted = rows(ROOT / "_cn_project/releases/speech-inventory-20260927/scripted_other_speech.tsv")
    categories = rows(ROOT / "_cn_project/releases/speech-inventory-20260927/engine_rayne_categories.tsv")
    source = rows(ROOT / "_cn_project/releases/speech-inventory-20260927/engine_rayne_samples.tsv")
    assert len(scripted) == 127 and all(r["current_chinese"] for r in scripted)
    assert len(categories) == 72 and len(source) == 253
    assert len({r["audio_entry"].upper() for r in source}) == 253
    game = pefile.PE(str(ROOT / "rayne2.exe"), fast_load=True)
    assert game.FILE_HEADER.Machine == 0x14C
    assert game.get_data(0x151F72, 5) == bytes.fromhex("E8D9C5EFFF")
    if mode == "baseline":
        assert sha(ROOT / "dinput8.dll") == originals["dinput8.dll"]
        assert sha(ROOT / "LANGUAGE.POD") == originals["LANGUAGE.POD"]
        print("BASELINE_OK scripted_chinese=127 categories=72 voice_samples=253 game_hook_bytes=E8D9C5EFFF live_payload=original")
        return
    assert mode == "modified"
    translated = rows(HERE / "voice_subtitles_zh.tsv")
    assert len(translated) == 253
    assert [r["audio_entry"] for r in translated] == [r["audio_entry"] for r in source]
    assert all(r["translation_zh"] for r in translated)
    mapping = json.loads((HERE / "character_map.json").read_text(encoding="utf-8"))
    assert len(mapping) < 2914
    assert max(len(encode_text(r["translation_zh"], mapping)) for r in translated) == 52
    assert all(len(encode_text(r["translation_zh"], mapping)) <= 96 for r in translated)
    header = (HERE / "source/voice_subtitles.h").read_text(encoding="ascii")
    assert len(re.findall(r"^static const char kVoiceText\d+\[\]", header, re.M)) == 253
    for r in translated:
        stem = r["audio_entry"].split("\\")[-1][:-4]
        assert f'{{"{stem}", kVoiceText' in header, stem
    dll = HERE / "payload/dinput8.dll"
    assert sha(dll) == "D525CB5521FADC0373641E6CF7EDBF988E5FB178EC65B61670CD85A5139A09DC"
    proxy = pefile.PE(str(dll))
    assert proxy.FILE_HEADER.Machine == 0x14C
    exports = {e.name.decode() for e in proxy.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
    assert {"DirectInput8Create", "DllCanUnloadNow", "DllGetClassObject"} <= exports
    assert b"voice_captions=%s" in dll.read_bytes()
    assert b"RAYNE_ALERT_1" in dll.read_bytes()
    old_path = ROOT / "LANGUAGE.POD"
    if sha(old_path) != originals["LANGUAGE.POD"]:
        old_path = ROOT / "_cn_project/test_backup/engine_voice_subtitles_20260927/LANGUAGE.POD"
    assert sha(old_path) == originals["LANGUAGE.POD"]
    old = Pod3.read(old_path)
    new = Pod3.read(HERE / "payload/LANGUAGE.POD")
    assert sha(HERE / "payload/LANGUAGE.POD") == MANIFEST["language_after"]
    assert not new.verify_crcs()
    assert [e.name for e in old.entries] == [e.name for e in new.entries]
    changed = [e.name for e in old.entries if old.read_entry(e.name) != new.read_entry(e.name)]
    assert changed == ["ART\\GOTHICTITLE_RU.TEX"]
    print("MODIFIED_OK scripted_chinese=127 categories=72 voice_captions=253 max_bytes=52 font_entries_changed=1 proxy_exports=ok archive_crc=ok")


if __name__ == "__main__":
    main(sys.argv[1])
