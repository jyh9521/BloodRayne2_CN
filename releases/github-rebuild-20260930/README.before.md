# BloodRayne 2 Terminal Cut 简体中文补丁

本仓库保存当前汉化测试版、翻译表、构建工具和每次修订的验证记录。当前版本使用俄语文本槽显示中文；配音仍为英语。游戏由玩家自行启动和测试。

## 安装 Release v1.0.0（2026-09-30）

完整解压 `dist/BloodRayne2_CN_v1.0.0_20260930.zip` 到独立目录，双击 `INSTALL.cmd`，输入 Steam 游戏根目录。安装器校验游戏版本、自动备份被覆盖文件并记录新增文件，再安装 17 个汉化文件。玩家自行从 Steam 启动游戏，选择 Russian 文本并开启字幕，配音仍为英语。

只安装 `LANGUAGE.POD`、`dinput8.dll`、15 个 `video/*_RU.srt`，不替换 `W32ART.POD`、`W32ENSND.POD`、`COMMON.POD`、视频或存档。无需源工程、Python 或安装字体。若已有其他 `dinput8.dll`，会停止安装而不覆盖。用 `UNINSTALL.cmd` 恢复安装器在 `_cn_backup_release_20260930` 中保存的原文件。

压缩包内 `README.zh-CN.txt` 包含干净 Steam 安装、回滚、测试检查点及已知复核项。`dist/BloodRayne2_CN_current.zip` 为同版本别名；请勿按旧版直接覆盖安装说明操作。

## 源文件与版本记录

- `translation/`：翻译表、术语表、视频中文源文本。
- `video_subtitles/`：当前视频中文字幕文件，编码适配游戏字体载体。
- `proxy/`：`dinput8.dll` 代理源代码。
- `tools/`：POD 分析、导出、构建与校验工具。
- `releases/`：各次修订脚本、差异和验证记录；庞大的游戏原始归档与临时副本不进仓库。
- `dist/`：当前可安装测试版压缩包。

当前缺失字幕修订的范围与未确认音频清单详见 `releases/missing-dialogue-20260926/VERIFICATION.txt`。不能把离线脚本覆盖率当作全游戏人工测试结果。

在本目录运行 `python build_release_zip.py` 可从本机游戏目录重新生成 `dist/BloodRayne2_CN_current.zip` 和校验清单。此命令只读取游戏文件，不启动游戏。

## 后续推送

今后的改动先在此仓库本地提交；交付时附上本次提交号和可直接复制的推送命令，由仓库使用者执行。当前分支为 `main`，远端为 `origin`。通用命令：

```powershell
git -C 'C:\Program Files (x86)\Steam\steamapps\common\BloodRayne 2 Terminal Cut\_cn_project' push origin main
```

每次修改后都要重新构建并校验安装包，再提交源文件、差异记录及对应的 `dist/` 文件；单独推送翻译表而漏掉测试包会使仓库版本与游戏实装版不一致。
