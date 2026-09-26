# Asynchronous scripted speech subtitle test

This test build inserts `dbBoxedDisplay(key)` immediately before 210 existing `dbStartSay(key)` commands in 28 `COMMON.POD` SCB scripts. It includes 83 Rayne speech occurrences and 127 other scripted speech occurrences. Eleven `dbStartSay` calls already had boxed captions. Three were not patched because two have no caption text in the corresponding Chinese resource and one has no matching English audio. All new captions use the existing `LANGUAGE.POD` translations and the same font path as the preceding scripted-speech patch. No voice archive or font archive is changed.

This release covers SCB-scripted asynchronous speech. `engine_cue_inventory.tsv` separately lists 72 engine-selected Rayne voice categories, including `Rayne_Taunt`, `Rayne_Ambient*` and `Rayne_Kill`. Those are not SCB `dbStartSay` commands and are not covered by this build. A separate runtime cue-to-caption hook would be needed for them.

Use `install.ps1` to verify the previous `COMMON.POD` hash, back it up and install this payload. `ROLLBACK.sh` invokes `rollback.ps1` to restore the prior version. Close the game first. Codex has not launched the game; in-game visual timing remains for the user to test.
