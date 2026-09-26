# BloodRayne 2 Terminal Cut 简体中文补丁

本仓库保存当前汉化测试版、翻译表、构建工具和每次修订的验证记录。当前版本使用俄语文本槽显示中文；配音仍为英语。游戏由玩家自行启动和测试。

## 安装当前测试版

1. 在 Steam 中备份游戏目录的 `LANGUAGE.POD` 和已有的 `dinput8.dll`（若有）。
2. 解压 `dist/BloodRayne2_CN_current.zip` 到《BloodRayne 2 Terminal Cut》游戏根目录，允许覆盖对应文件。
3. 游戏语言选择 Russian。补丁只提供 `LANGUAGE.POD`、`dinput8.dll` 和 `video/*_RU.srt`；不替换 `W32ART.POD` 或 `W32ENSND.POD`。
4. 玩家进游戏测试；测试前请退出游戏再更换文件。

补丁依赖当前 Terminal Cut 游戏版本。压缩包内的 `SHA256SUMS.txt` 列出了每个安装文件的校验值。需要撤销时，将第 1 步备份的文件还原，并移除本补丁新增的 `video/*_RU.srt`（仅限原本不存在的文件）。

## 源文件与版本记录

- `translation/`：翻译表、术语表、视频中文源文本。
- `video_subtitles/`：当前视频中文字幕文件，编码适配游戏字体载体。
- `proxy/`：`dinput8.dll` 代理源代码。
- `tools/`：POD 分析、导出、构建与校验工具。
- `releases/`：各次修订脚本、差异和验证记录；庞大的游戏原始归档与临时副本不进仓库。
- `dist/`：当前可安装测试版压缩包。

当前缺失字幕修订的范围与未确认音频清单详见 `releases/missing-dialogue-20260926/VERIFICATION.txt`。不能把离线脚本覆盖率当作全游戏人工测试结果。

在本目录运行 `python build_release_zip.py` 可从本机游戏目录重新生成 `dist/BloodRayne2_CN_current.zip` 和校验清单。此命令只读取游戏文件，不启动游戏。
