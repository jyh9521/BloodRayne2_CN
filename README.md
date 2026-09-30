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

## 从 GitHub 随时重建当前项目

### 两种用途

- **玩家安装**：直接使用仓库 `dist/BloodRayne2_CN_current.zip`，不需要编译器或源工程。
- **源码重建**：下面的流程会编译 x86 代理 DLL、以 Steam 原版 LANGUAGE.POD 和仓库内的最终汉化资源重新构建 POD，再打包 15 个已校准视频字幕及安装/卸载器。**不读取本机已汉化的 DLL/POD，不依赖旧工作目录或历史测试备份。**

### 环境与输入

1. Windows 10/11、Git、Python 3.10 或更高版本（只用标准库，不需要 pip 安装依赖）。
2. Visual Studio 2022 Build Tools，安装“使用 C++ 的桌面开发”、MSVC x86/x64 工具和 Windows SDK。脚本通过 vswhere 自动定位。
3. 从 Steam 干净安装 Terminal Cut 后取得原版 `LANGUAGE.POD`，其 SHA-256 必须为：
   `2e3e0797e147e58b7308d3fcedbdf0a06cb433fb099fc24b8fb38943d8b358e4`。
   游戏原始资源由 Steam 提供，不依赖本仓库保存它们。不要拿已安装汉化的 LANGUAGE.POD 当构建输入。

### 克隆、重建、安装

```powershell
git clone https://github.com/jyh9521/BloodRayne2_CN.git
Set-Location BloodRayne2_CN
python rebuild/build.py --base-pod "C:\Program Files (x86)\Steam\steamapps\common\BloodRayne 2 Terminal Cut\LANGUAGE.POD"
```

输出：`build/reproducible/BloodRayne2_CN_rebuilt.zip`。解压后运行 INSTALL.cmd 安装；构建本身不修改 Steam 游戏目录，不启动游戏。

可用 `--output "D:\BR2-build"` 指定独立输出目录；`--base-pod` 接受任意位置保存的、哈希匹配的原版归档。

### 当前权威输入

- `rebuild/runtime/`：当前实装代理的完整 C++ 源码、导出定义、字幕与布局头文件。
- `rebuild/assets/localized_resources.zip`、`resources.json`：最终汉化资源快照，包含 64 个替换项和 7 个新增项；字形图集已包含，无需安装字体。其 SHA-256 与最终 POD 的全部 393 个资源条目都列在清单中。
- `video_subtitles/`：2026-09-30 调轴后的 15 个游戏载体编码 RU SRT。
- `releases/release-20260930/`：玩家安装器、卸载器与原文件/新增文件回滚逻辑。
- `translation/`、历史 `releases/`：可编辑译文、术语表及各次构建/修订证据。

重建使用的是**已定稿汉化资源快照**；并非重新运行所有历史脚本、重新听写或自动把任意 TSV 改动导入。以后修改翻译或功能时，必须同步更新权威资源/源码和相应清单，再重建验证和推送，不能只提交 TSV。

验证以资源内容为准：重建 POD 的全部 393 个条目须与发布资源清单逐条一致，CRC 正确；DLL 须为 x86 且含 5 个代理导出，15 个 SRT 保持原字节。POD 不累积历史废弃数据，容器总哈希会与旧实装 POD 不同；DLL 的整体哈希也可随编译器版本变化，**不承诺所有编译器逐字节同产物**。发布安装包保留了原实装版，重建包与发布包分别标识。

历史 `build_release_zip.py` 是本机当前实装快照打包工具，不是源码重建入口；需要重建请使用 `rebuild/build.py`。

## 版本控制与推送

当前分支 `main`，远端 `origin`。本次及后续修改同时保留源码、定稿资源、验证记录和安装包。用户明确要求推送时，提交后推送并核对远端提交号；后续仍附可复制命令：

```powershell
git push origin main
```

离线安装/回滚与资源一致性验证不代表已完成全游戏人工测试。视频 `A2S02P16` 第一句保留译文与当前英语音轨没有完整对应，仍标记待复核。
