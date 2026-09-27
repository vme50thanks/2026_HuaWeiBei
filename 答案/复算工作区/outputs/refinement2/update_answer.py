"""Deploy verified second-round artifacts; back up old results, preserve source inputs."""
from pathlib import Path
import shutil,json,csv,hashlib,zipfile,datetime,sys,subprocess
W=Path(__file__).resolve().parents[2];S=Path(__file__).resolve().parent;T=Path('D:/研一/比赛/中文题目/D题/答案').resolve()
stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S');backup=T/('历史备份_'+stamp)
load=lambda p:json.loads(p.read_text(encoding='utf-8'))
assert load(S/'q2/verification.json')['baseline']['status']=='PASS'
assert all(x['failed_points']==0 for x in load(S/'q3/joint_verification.json')['baseline']['scans'])
assert load(S/'q4/verification.json')['source_unchanged']
backup.mkdir()
def inside(p):assert p.resolve().is_relative_to(T) and p.resolve()!=T
for name in ['q2','q3','q4','paper','复算工作区','代码','独立回放输出','00_成果总索引.md','文件清单_SHA256.csv','更新结果表.xlsx','优化结果说明.md','新旧结果对比.csv','问题二三四优化成果.zip','复算验证.py','复算说明.md','requirements.txt']:
 p=T/name
 if p.exists():inside(p);inside(backup/name);shutil.move(str(p),str(backup/name))
copied=[]
def copy(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
 assert hashlib.sha256(src.read_bytes()).digest()==hashlib.sha256(dst.read_bytes()).digest();copied.append(str(dst.relative_to(T)))
for q in ['q2','q3','q4']:
 for p in (S/q).rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:copy(p,T/q/p.relative_to(S/q))
for name in ['更新结果表.xlsx','优化结果说明.md','新旧结果对比.csv','问题二三四优化成果.zip','复算说明.md','requirements.txt']:copy(S/name,T/name)
runtime=T/'复算工作区';runtime.mkdir()
with zipfile.ZipFile(S/'问题二三四优化成果.zip') as z:
 for info in z.infolist():assert (runtime/info.filename).resolve().is_relative_to(runtime.resolve())
 z.extractall(runtime)
for p in S.glob('*.py'):
 if p.name!='update_answer.py':copy(p,T/'代码'/p.name)
for q in ['q2','q3','q4']:
 for p in (W/'outputs'/q).glob('*.py'):copy(p,T/'代码'/q/p.name)
 for p in (S/q).rglob('*.png'):copy(p,T/'paper/当前结果图'/q/p.relative_to(S/q))
(T/'paper/说明.md').write_text('图表对应本轮结果。论文tex/pdf未自动修改；前轮LaTeX片段在历史备份，不能直接套用其中数值。第一问未变，其图可从历史备份取用。',encoding='utf-8')
original=load(T/'q4/freeze_manifest.json');copy(T/'q4/freeze_manifest.json',T/'q4/freeze_manifest_工作区原始.json');relocated=[]
for row in original:
 p=Path(row['path'])
 if p.is_relative_to(S/'q3'):p=T/'q3'/p.relative_to(S/'q3')
 elif p.is_relative_to(W/'outputs/preflight'):p=T/'preflight'/p.relative_to(W/'outputs/preflight')
 assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],str(p)
 relocated.append(dict(path=str(p.resolve()),sha256=row['sha256']))
(T/'q4/freeze_manifest.json').write_text(json.dumps(relocated,ensure_ascii=False,indent=2),encoding='utf-8')
# Reuse the verified standalone replay entry point from the backed-up deployment.
copy(backup/'复算验证.py',T/'复算验证.py')
s2=load(T/'q2/summary.json')['baseline'];s3=load(T/'q3/summary.json')['baseline'];s4=load(T/'q4/summary.json')
index=f'''# D题当前成果

更新时间：{stamp}。q2/q3/q4为第二轮扩大搜索后的结果；旧版完整备份在`{backup.name}`。第一问和预处理数据未修改。

|入口|说明|
|---|---|
|q2|{s2['N']}架次，{s2['Cmax']/60:.6f}分钟，{s2['E']:.6f}kWh|
|q3|{s3['N']}运输+{s3['relay_N']}中继架次，{s3['C_joint']/60:.6f}分钟，{s3['total_E']:.6f}kWh|
|q4|冻结本轮q3的baseline；K2缺口{s4['results']['K2_baseline']['gap']}，K3缺口{s4['results']['K3_baseline']['gap']}|
|更新结果表.xlsx|Q2/Q3运输、逐箱表分别保存，中继/通信/Q4模板汇总|
|优化结果说明.md|新旧对照、目标权衡、假设及验证范围|
|paper/当前结果图|当前甘特图、路线图、通信与资源图|
|代码|阅读副本；运行使用完整复算工作区|
|复算工作区/outputs/refinement2|本轮完整代码与数据布局|
|复算验证.py|直接验证本答案目录的当前方案|

八类资源顺序：A/B/C运输机、A/B/C电池、中继机、中继能源组件。前轮方案较省能、少一个运输架次；当前方案按既定时间优先目标更快，不能称为所有指标全面改善。两问80箱均按期、D=0；第三问仅在所述时空分辨率下未发现中断，无连续通信证明。第二、三问无全局最优证明；第四问为指定冻结及解释口径下的完整枚举最优。

本轮Q2和Q3运输计划不同，禁止互换。q4冻结清单仅明确映射文件路径，全部内容哈希一致。复算工作区的outputs/refinement和outputs/q2/q3是初始化或依赖，不是当前结果入口。

运行：`python 复算验证.py`，详细解释器路径与依赖见复算说明。论文未自动修改，前轮LaTeX片段在备份中，采用新结果时须同时更新文字、表和图。
'''
(T/'00_成果总索引.md').write_text(index,encoding='utf-8')
print('COPIED',len(copied),'backup',backup,flush=True)
subprocess.run([sys.executable,str(T/'复算验证.py')],check=True)
rows=[]
for p in T.rglob('*'):
 if p.is_file() and not any(x.startswith('历史备份_') for x in p.relative_to(T).parts) and '__pycache__' not in p.parts and p.name!='文件清单_SHA256.csv':rows.append(dict(path=str(p.relative_to(T)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
with (T/'文件清单_SHA256.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(rows)
print('UPDATE COMPLETE',len(rows),'manifest entries',flush=True)
