# BloodRayne 2 Terminal Cut 文本提取

本目录由 `tools/export_translation_catalog.py` 从当前纯净基线直接生成。
不要手工修改 `id`、`kind`、`file`、`line`、`key`、`source_en` 或
`source_ru`；翻译只填写 `translation_zh`，并把 `status` 改为
`translated`。

## 文件

- `dialogue.tsv`：2,598 条剧情对白、字幕、目标与提示。
- `menu.tsv`：737 条语言表菜单文本和 3 条最新版 EXE 内置菜单文本。
- `moves.tsv`：94 条招式表文本。
- `credits.tsv`：283 条当前 Terminal Cut 英文演职人员表可见文本。

合并总表位于上一级 `catalog.tsv`，共 3,715 条。

2026-07-31 用户已完成菜单与招式表：

- 菜单 740 行中有 739 条有效译文；另 1 行的原始键和值本来就是空白。
- 招式表 94 条全部完成，`@@...@@` 控制标记和格式占位符已校验。
- 演职人员按要求不翻译，最终构建继续使用英文原件。

对白已在 `../dialogue_deduplicated` 中拆成 1,706 条唯一翻译单元和
2,598 条原始位置映射。后续对白翻译只编辑 `dialogue_unique.tsv`。
完整构建器 `tools/build_full_translation.py` 会读取该唯一表与位置映射，
把每条标记为 `translated` 的译文分别写回所有实装位置。

## 来源

- 剧情英文与俄文：纯净 `_cn_project/baseline/LANGUAGE.POD`。
- 菜单英文键与俄文值：同一纯净 `LANGUAGE.POD`。
- 招式英文原文：纯净 `COMMON.POD` 的 `DATA\MOVELIST.TXT`。
- 演职人员英文原文：纯净 `COMMON.POD` 的 `DATA\CREDITS.TXT`。

2,598 条剧情文本中有 2,590 条自动匹配到英文原文。其余 8 条在
`notes` 中标记为仅俄文版本存在，应结合俄文语义翻译。另有 3 条英文
显示文本本来为空，状态为 `blank`，导入时应清空俄文残留。

招式表第 72、74、98、100 行的俄文版本把重复按键缩写为“3 次”，
导致控制标记数量与英文不同。这四行已在 `notes` 中标记，翻译时以
英文结构和完整的 `@@...@@` 标记序列为准。

## 不可改动内容

- `@@...@@` 控制标记。
- `%d`、`%s` 等格式占位符。
- 对白键、WAV 文件名和脚本资源名。
- 演职人员表开头的 `/b` 格式指令。

所有 TSV 使用 UTF-8 BOM、制表符分隔和 CRLF 行尾，可直接用支持
UTF-8 的表格软件编辑。
