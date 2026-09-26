from pathlib import Path
import sys,subprocess,json
import finish_translation as ft

here=Path(__file__).resolve().parent
records=[]
for mode in ['baseline','modified','rollback']:
    cmd=[sys.executable,'-X','utf8',str(here/'verify.py'),mode]
    result=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,(mode,result.stdout,result.stderr)
    records.append(dict(test=mode.upper(),command=subprocess.list2cmdline(cmd),input=str(ft.ORIGINAL if mode=='baseline' else ft.TARGET),stdout=result.stdout,stderr=result.stderr,exit_status=result.returncode))
fields,rows=ft.read(ft.TARGET)
notes='''翻译范围：dialogue_unique.tsv 全部 1,706 个唯一单元。
已翻译 1,704 条；2 条原本应清空的显示文本保持 blank。
125 个既有冲突全部定稿；译文以英语上下文为主，8 条俄语独有文本参照俄文翻译。
已有人工译文经过复核，修正明显误译、统一术语，并去除英语原文没有的额外说话人前缀。
英语原文自带的说话人标签保留并翻译；冲突 notes 改为 resolved，保留历史备选作为溯源。
原文、ID、行号、资源键、出现次数及 2,598 行位置映射保持不变。
术语表包含 73 项；人名沿用既有项目译法，新增词属于本项目译名，并非官方译名声明。
本轮没有覆盖 menu.tsv、moves.tsv、credits.tsv，也没有生成或安装新的 POD / DLL。
历史 summary.json、dialogue_review.xlsx 和测试包说明并未重新生成；本轮状态以当前 TSV 和本报告为准。
原文遗留标记：XXX 占位项（327、360），Sp_Waterfalls_M（472），ost_Pen_Eats 串行原文（764）。
以上零基索引是审计位置，不是资源 ID。这些源问题被保留，不在本轮擅自拆键或删除资源。
吸血鬼虚构语言（1403 至 1407）使用音译，不虚构具体语义；MAC-10 保留武器型号。
已执行导入选择和全部载荷编码回读测试；未进行游戏画面、配音和字幕排版测试。
回滚在另一份副本上执行，恢复字节及原状态完全一致；正式 TSV 保持新译文。
ROLLBACK.sh 无参数可恢复本轮前的 dialogue_unique.tsv；传入路径则只恢复指定副本。
'''
lines=[notes,'Changed fields: translation_zh, status; notes only for resolved conflicts.',
       'MODIFIED_FILE: '+str(ft.TARGET),'DIFF_FILE: '+str(here/'DIFF_FILE.diff'),
       'VERIFICATION: '+str(here/'VERIFICATION.txt'),'ROLLBACK: '+str(here/'ROLLBACK.sh'),
       'GLOSSARY: '+str(here.parent/'glossary_zh.tsv'),
       'Original SHA256: '+ft.digest(ft.ORIGINAL),'Modified SHA256: '+ft.digest(ft.TARGET)]
for r in records:
    lines+=['',r['test'],'Command: '+r['command'],'Input: '+r['input'],'Literal stdout:',r['stdout'].rstrip(),'Literal stderr: '+repr(r['stderr']),'Exit status: '+str(r['exit_status'])]
(here/'VERIFICATION.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8-sig')
(here/'verification.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
# Reopen the exact deliverables rather than relying on successful writes.
for p in [ft.TARGET,here/'DIFF_FILE.diff',here/'VERIFICATION.txt',here/'ROLLBACK.sh',here.parent/'glossary_zh.tsv',here/'resolved_conflicts.tsv']:
    text=p.read_text(encoding='utf-8-sig'); assert text
    print('REOPEN_OK '+p.name+' bytes='+str(p.stat().st_size))
print('FINAL_OK translated=1704 conflicts_resolved=125 blank=2 tests=3/3')
