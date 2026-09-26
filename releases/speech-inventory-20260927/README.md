# Speech inventory for review (2026-09-27)

This is **only an extraction and review pack**. It does not install subtitles, alter PODs, or start the game.

- `scripted_other_speech.tsv`: the 127 newly boxed `dbStartSay` occurrences not classified as Rayne. There are 119 unique audio keys. Each row includes script/line, actor token, the original English subtitle, and the current Chinese caption decoded from the installed `LANGUAGE.POD` carrier encoding. Repeated keys remain separate because they occur in different scripts.
- `engine_rayne_categories.tsv`: all 72 engine voice-table IDs, their prefix, broad meaning, WAV count, and filenames. These IDs contain three duplicated prefixes (`Rayne_XerxBDie`, `Rayne_XerxBGetHurt`, `Rayne_XerxBTaunt`); hence 69 distinct prefixes. Twenty-four IDs have no matching English WAV in the current archive.
- `engine_rayne_samples.tsv`: all 253 distinct matching WAVs. The 72 IDs account for 262 sample references because the XerxB samples are referenced twice. A small-model English ASR pass supplied **draft text**, not authoritative dialogue. Seven recordings yielded no speech; some grunts/screams produce hallucinated words. Use the category, duration and archive filename when reviewing. Only one WAV key appears in the shipped English text resources; the rest are audio-only and cannot be recovered as official script text from `LANGUAGE.POD`.

`source_hashes.json` records the read-only inputs. `verify.py` rechecks output counts and unchanged input hashes. `ROLLBACK.sh` deletes only these generated reports from a specified absolute directory; it does not alter game files.

The 72 categories are **not** currently captioned by the existing `dbStartSay` patch. This report is intended for deciding which engine-selected speech should receive a separate caption path. In particular, ambient, hint, alert, attack, kill, and taunt categories contain many full spoken lines, while other categories contain nonverbal effort/pain sounds.
