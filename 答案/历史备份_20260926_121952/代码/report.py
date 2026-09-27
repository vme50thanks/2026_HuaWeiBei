from pathlib import Path
import sys,json,csv,hashlib,zipfile,importlib.util
from PIL import Image,ImageDraw,ImageFont
from openpyxl import Workbook
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
load=lambda p:json.loads(p.read_text(encoding='utf-8'))
def read(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def write(p,rows):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
sys.path.insert(0,str(ROOT/'outputs/q2'))
from report_q2 import gantt,routechart
q2=load(OUT/'q2/summary.json');q3=load(OUT/'q3/summary.json');q4=load(OUT/'q4/summary.json');v2=load(OUT/'q2/verification.json');v3=load(OUT/'q3/joint_verification.json');v4=load(OUT/'q4/verification.json')
old2=load(ROOT/'outputs/q2/summary.json')['baseline'];old3=load(ROOT/'outputs/q3/summary.json')['baseline'];old4=load(ROOT/'outputs/q4/summary.json')
comparisons=[]
for name,s,old in [('Q2',q2['baseline'],old2),('Q3',q3['baseline'],old3)]:
 ck='Cmax' if name=='Q2' else 'C_joint';ek='E' if name=='Q2' else 'total_E'
 comparisons.append(dict(question=name,old_minutes=old[ck]/60,new_minutes=s[ck]/60,time_reduction_percent=100*(old[ck]-s[ck])/old[ck],old_kWh=old[ek],new_kWh=s[ek],energy_reduction_percent=100*(old[ek]-s[ek])/old[ek],old_transport_sorties=old['N'],new_transport_sorties=s['N'],D=s['D']))
write(OUT/'新旧结果对比.csv',comparisons)
text='# 问题二、三、四追加优化：结果与限制\n\n第二、三问已获得独立验证的新方案；第四问在新冻结方案下完成完整枚举，但资源缺口指标变差。旧版成果均保留，未覆盖原附件或原q2/q3/q4目录。\n\n'
text+='|问题|原完成时间min|新完成时间min|提速比例|原能耗kWh|新能耗kWh|运输架次变化|\n|---|---:|---:|---:|---:|---:|---|\n'
for r in comparisons:text+=f"|{r['question']}|{r['old_minutes']:.4f}|{r['new_minutes']:.4f}|{r['time_reduction_percent']:.2f}%|{r['old_kWh']:.4f}|{r['new_kWh']:.4f}|{r['old_transport_sorties']}→{r['new_transport_sorties']}|\n"
text+=f"\nQ2按全部运输返回O01计算，Q3按运输与中继全部返回计算。两问D=0、80箱全部达到期望交付时间；医疗16箱、首批30箱的硬时限均满足。最小硬时限余量{v2['baseline']['hard_deadline_min_slack_s']:.6f}s，最低运输返航SOC为{100*(.2+v2['baseline']['min_energy_reserve_slack']):.6f}%。使用8架运输机、14组电池；第三问另用2架中继机、3组组件、3个中继架次，中继能耗{q3['baseline']['relay_E']:.9f}kWh。\n\n"
text+='## 第四问：更快调度的资源代价\n\n资源向量顺序为A/B/C运输机、A/B/C电池、中继机、中继能源组件；库存4/2/2/6/4/4/2/6。每类缺口独立计算，不用富余抵消短缺。\n\n|K|新总需求向量|新缺口向量|旧G|新G|\n|---|---|---|---:|---:|\n'
for K in [2,3]:
 r=q4['results'][f'K{K}_baseline'];o=old4['results'][f'K{K}_baseline'];text+=f"|{K}|{' / '.join(map(str,r['total_resources']))}|{' / '.join(map(str,r['gap']))}|{o['G']}|{r['G']}|\n"
 text+= '\n'+ '；'.join(f"{g['group']}：{'、'.join(g['sites'])}" for g in r['groups'])+'。\n\n'
text+=f"新方案有{q4['block_count']}个不可拆分服务区块。K=2枚举{q4['results']['K2_baseline']['all_partitions']}种、K=3枚举{q4['results']['K3_baseline']['all_partitions']}种无标签非空分区，并经第二套完整枚举核对最优目标。按G→S→工作量CV与G→CV→S得到相同基准结果。这个最优性只针对本次冻结调度、完整中继复制及组内资源可重新编号的口径。未分区最小需求为{' / '.join(map(str,q4['pooled_minimum']))}。\n\n"
for K in [2,3]:
 r=q4['results'][f'K{K}_baseline'];text+=f"K={K}额外中继任务{r['extra_relay_N']}次，新增中继能耗{r['extra_relay_E']:.9f}kWh，额外机体占用{r['extra_relay_body_work_s']:.3f}s，额外组件占用{r['extra_relay_energy_occupied_s']:.3f}s。资源峰值任务与时段见q4/K{K}_baseline/peak_evidence.csv，资源编号分配和充电事件见同目录。\n\n"
text+='不允许复制中继时，所有15个服务区被实际保障关系连成一个块，因此K=2、K=3均无合法非空分区。这是禁止复制解释下的无解，不是原题一般无解。绑定证据见q4/binding_blocks.json。\n\n**选择建议：重视救援完成速度，采用本次Q2、Q3并如实报告其新Q4资源缺口；重视原先缺口优先的分区指标，旧版Q3→Q4组合更有利。不能把旧Q4分区表接到新Q3调度后面。**\n\n'
text+='## 实际搜索与最优性\n\nQ2新增显式机型与批次顺序的模拟退火，允许移箱、换箱、合批、拆批、两批重组、按服务区重新分批。三轮各180秒，种子20260925/26/27；第一轮最多3点、后两轮最多4点。第二轮结果103.4781分钟，第三轮未实质改善。随后将Q3优化得到的同完成时间、更低运输能耗方案纳入Q2，重新独立验证。Q2两种目标排序在1e-7秒比较容差下采用同一最终方案。\n\nQ3先以49个位置和1904组三架次结构重新匹配新Q2，未成功；随后将中继服务日历纳入运输排序与机型搜索，约180秒、种子20260928。两组初始组批来自旧方案和改进Q2，服务窗口可变，采用位置130/511/489及一架主中继、另一架两次接续的搜索结构。没有穷举连续位置、任意组批或更多中继架次，未证明全局最优。两问D≥0且达到0，只有第一层目标有零下界证据，不能据此证明整个字典序最优。\n\n'
text+='## 与截图的关系\n\n截图Q2声称94.8872分钟、Q3声称98.9958分钟；本轮尚未达到这些时间。截图没有完整路线、逐箱交付、能耗和资源回放，不能据它核验相同建模口径。我们未将截图数值写入求解结果，也未为接近它减少安全余量、遗漏箱子、放宽医疗或首批时限。\n\n'
text+='## 假设与验证范围\n\n仍沿用用户授权工作假设：标准航程与可用电池能量标定、爬升效率按势能转换解释、未计缺少功率参数的运输交接悬停能耗；均需要用户核验。中继并发容量与零切换耗时未作真实网络认证。原始DEM与节点高度差异保持。\n\n'
z=v3['baseline']['scans'][-1];text+=f"独立通信回放：1秒/5米、0.5秒/2.5米、0.5秒/全穿越像元三档均通过；最后一档含{z['points']}个点，低裕量或切换处细化至0.05秒，最差所选链路裕量{z['worst']['margin_db']:.9f}dB。结论仅为‘在所述时空分辨率下未发现中断’，未数学证明连续通信。原始文件SHA-256核对、冻结清单以及第四问回放均通过。\n\n"
text+='## 成果位置\n\n- q2：模板运输表、80箱交付表、航段、资源事件和独立verification.json。\n- q3：新运输/中继/通信保障表，三维轨迹、逐资源状态、通信采样与独立joint_verification.json。\n- q4：K=2/K=3模板、全部解释口径对比、绑定与冻结哈希、组内资源分配、峰值证据及独立verification.json。\n- 复算说明.md：运行环境、命令与搜索限制。\n\n结果可用于模型分析与复算；不构成完整代写论文，正式竞赛应遵守赛事规则。\n'
(OUT/'优化结果说明.md').write_text(text,encoding='utf-8')
for name in ['baseline','makespan_first']:
 p=load(OUT/'q2'/name/'plan.json');gantt(p,OUT/'q2'/name/'无人机任务甘特图.png');gantt(p,OUT/'q2'/name/'电池周转图.png',True);routechart(p,read(ROOT/'outputs/preflight/nodes.csv'),OUT/'q2'/name/'运输路线图.png')
# Reuse only the data-driven chart and energy-cycle part of the old report;
# its old narrative contains fixed old numbers and must not be copied.
source=(ROOT/'outputs/q4/report_q4.py').read_text(encoding='utf-8').split(" b2=s['results']['K2_baseline']")[0]
source+="\nif __name__=='__main__':\n import argparse\n a=argparse.Namespace(out=Path(__file__).resolve().parent/'q4',pre=Path(__file__).resolve().parents[2]/'outputs/preflight');main(a)\n"
(OUT/'q4_charts.py').write_text(source,encoding='utf-8')
spec=importlib.util.spec_from_file_location('new_q4_charts',OUT/'q4_charts.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
from argparse import Namespace
mod.main(Namespace(out=OUT/'q4',pre=ROOT/'outputs/preflight'))
(OUT/'q4/模型与结果说明.md').write_text(text,encoding='utf-8');(OUT/'q2/模型与结果说明.md').write_text(text,encoding='utf-8')
wb=Workbook();wb.remove(wb.active)
for sheet,path in [('Q2_运输架次',OUT/'q2/baseline/Q2_运输架次.csv'),('Q2_逐箱交付',OUT/'q2/baseline/Q2_逐箱交付.csv'),('Q3_中继架次',OUT/'q3/baseline/Q3_中继架次.csv'),('Q3_通信保障',OUT/'q3/baseline/Q3_通信保障.csv'),('Q4_分区配置',OUT/'q4/Q4_分区配置.csv')]:
 rows=read(path);ws=wb.create_sheet(sheet);ws.append(list(rows[0]));[ws.append(list(r.values())) for r in rows];ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
wb.save(OUT/'更新结果表.xlsx')
print(json.dumps(comparisons,ensure_ascii=False));print('Reports and charts generated')
