# Scripted-dialogue subtitle coverage test

This test build adds a `dbBoxedDisplay` immediately before each qualifying unboxed `dbSay` call. It adds 417 calls in 32 `COMMON.POD` SCB scripts. `LANGUAGE.POD` gains matching Chinese text for four formerly unmatched audio keys and one reused debug-scene RU text resource. It preserves English audio and does not modify `W32ART.POD` or `W32ENSND.POD`.

Static audit: 502 scripted speech calls, 82 already boxed, 417 newly boxed, 3 intentionally unboxed (two have no Chinese or source dialogue, one has no matching audio). `audit.tsv` records each decision. The original Club Strages fix remains present. This is not a claim that every scene has been visually tested in-game.

The ZIP's `payload/COMMON.POD` and `payload/LANGUAGE.POD` are the modified files. This release's `install.ps1` verifies both original hashes, backs up both files, then installs the payloads. `ROLLBACK.sh` invokes `rollback.ps1` to restore both originals from that backup. Close the game before installing or rolling back.
