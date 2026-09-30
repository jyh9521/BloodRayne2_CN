# 预渲染视频 RU 中文字幕重新打轴（2026-09-30）

本版处理 `video` 目录的 15 个 `*_RU.srt`，共 222 条字幕。只替换 ASCII 时间码，字幕正文的原始字节、载体字库编码、标点、顺序、数量和单条文本长度全部保留。视频、音轨、其他语言字幕、DLL、POD 均保持原样。没有启动游戏。

依据：从当前 BIK 的第一路英语音轨提取 16 kHz PCM；faster-whisper medium 提取词级时间；音乐/低声片段做无 VAD 二次分析；4 处疑难窗口以 large-v3 交叉复核；人工按既有中文内容对应英语语句；使用附近语音边界收紧静音，加入短暂可读余量，并将前一字幕截在后一字幕出现之前。模型结果用于打轴，不用于替换译文。完整音轨、分词证据及人工区间均保存在本地发布目录。

原版存在 78 处相邻字幕重叠，7 条字幕尾部超过视频长度。本版为 0 重叠、0 越界。所有 222 条正文逐字节一致。

### 明确标记的例外

- `A1S01P06:1` 是屏幕标题“硫磺会总部，法国，1939年”，依场景保留，尾部避开第一句对白。
- `A2S02P16:1`“莱恩，刚才那是埃菲梅拉，对吧？”：当前英语音轨只识别出“Rayne? Where'd you end up?”；medium/large-v3 两次独立结果一致，没有完整的埃菲梅拉问句。按用户保留译文要求，将该条保留在对白前的场景空档至称呼结束，并在 `timing_review.tsv` 中标记 `reference_text_no_full_audio_match`。这条不是已经证实的逐句英语匹配。
- `A2S02P16:2` 按同一英语句中“Where'd you end up?”的词边界显示。

### 文件和使用

- `payload/video` 是供游戏使用的 15 个载体编码 RU 文件。
- `source/*_ZH.utf8.srt` 仅供中文阅读复核，不用于覆盖游戏 RU 文件。
- `timing_review.tsv` 记录每条原时间、新时间、位移、正文和证据类别。
- `baseline.json` 保存全部视频目录文件及关键游戏文件的原 SHA-256。
- `manifest.json` 保存 15 个字幕原 SHA-256、新 SHA-256、时长和例外。
- `install.ps1` 预检全部原哈希、备份后安装；失败时恢复。
- `ROLLBACK.sh`（Git Bash）或 `rollback.ps1` 恢复安装前 15 个字幕。

复现：`python transcribe.py` → `python review_windows.py` → `python review_critical.py` → `python build.py` → `python verify.py modified`。读取已保留的音频/ASR证据时可直接执行 `build.py`。重跑需要本机 Python 的 PyAV、faster-whisper、imageio-ffmpeg 和已缓存模型。

`MODIFIED_FILE.zip` 是安装包，包含载体字幕、清单和安装/回滚脚本。游戏内观感由用户测试。
