# BloodRayne 2 对白去重翻译表

## 翻译入口

正式翻译只编辑 `dialogue_unique.tsv`：

- 填写或修改 `translation_zh`。
- 完成后把 `status` 改为 `translated`。
- `needs_review` 表示同一句原文在原始表里已经出现多个不同译文；
  当前暂时保留最早出现的版本，需要人工选定统一译文。
- `blank` 表示英语原文就是空显示文本，构建时应清空俄语残留。

不要修改 `unit_id`、`source_en`、`source_ru` 和 occurrence 统计列。

`dialogue_review.xlsx` 是便于筛选和查看冲突的审阅副本。自动导入仍以
TSV 为准，若在 XLSX 中修改，需要把结果同步回 `dialogue_unique.tsv`。

## 去重结果

- 游戏纯净 `LANGUAGE.POD` 内共有 61 个 `WORLD\RU\*.TXT` 关卡文本。
- 原始显示文本共 2,598 条。
- 按完全一致的“英文显示文本 + 俄文显示文本”归并后为 1,706 条。
- 454 个翻译单元出现过不止一次，共消除 892 条重复翻译工作。
- `dialogue_occurrences.tsv` 保留全部 2,598 个实际资源位置。

去重不会删除游戏资源。最终构建会通过 `unit_id`，把一条唯一中文译文
分别写回 `dialogue_occurrences.tsv` 中列出的每个文件、行号和键。
`tools/build_full_translation.py` 已按此映射实施导入：当前 114 个
`translated` 单元对应 145 个实际位置；`needs_review` 和 `pending`
暂时回退英语，待定稿后重新构建即可自动覆盖其全部重复位置。

## 当前状态

- `translated`：114 条。
- `needs_review`：125 条。
- `pending`：1,465 条。
- `blank`：2 条。

以上四项合计 1,706 条。125 个 `needs_review` 都来自已有重复译文措辞
不一致；没有发现当前保留译文丢失 `@@...@@` 控制标记的问题。

## 其他文本策略

- `extracted/menu.tsv`：739 条有效菜单文本已完成，另有 1 条原始空键值。
- `extracted/moves.tsv`：94 条已完成，控制标记已校验。
- 演职人员按要求不翻译，构建时继续使用当前 Terminal Cut 英文原件。

重新检查或同步表格时运行：

`python _cn_project/tools/prepare_translations.py`

脚本会在 `translation/backups` 按输入文件 SHA-256 保存用户表格副本。
已经在 `dialogue_unique.tsv` 中标记为 `translated` 的人工定稿会优先于
旧的重复行，不会在下次同步时被原始冲突覆盖。
