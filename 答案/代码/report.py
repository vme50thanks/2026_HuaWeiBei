from pathlib import Path
import sys,json,csv,subprocess
from openpyxl import Workbook
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
load=lambda p:json.loads(p.read_text(encoding='utf-8'))
def read(p):
 with p.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def write(p,rows):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
sys.path.insert(0,str(ROOT/'outputs/q2'))
from report_q2 import gantt,routechart
q2=load(OUT/'q2/summary.json');q3=load(OUT/'q3/summary.json');q4=load(OUT/'q4/summary.json');v2=load(OUT/'q2/verification.json');v3=load(OUT/'q3/joint_verification.json');v4=load(OUT/'q4/verification.json')
rows=[]
for q,new,ck,ek in [('q2',q2,'Cmax','E'),('q3',q3,'C_joint','total_E')]:
 old=load(ROOT/'outputs/refinement'/q/'summary.json')['baseline'];s=new['baseline']
 rows.append(dict(question=q,previous_min=old[ck]/60,current_min=s[ck]/60,saved_s=old[ck]-s[ck],previous_kWh=old[ek],current_kWh=s[ek],energy_change_kWh=s[ek]-old[ek],previous_transport_N=old['N'],current_transport_N=s['N'],D=s['D']))
write(OUT/'新旧结果对比.csv',rows)
text='# 第二轮搜索：结果、权衡与复算\n\n全部数值来自保存方案的独立回放；未覆盖原始附件。\n\n|问题|前轮时间min|本轮时间min|节省s|前轮能耗kWh|本轮能耗kWh|运输架次|\n|---|---:|---:|---:|---:|---:|---|\n'
for r in rows:text+=f"|{r['question']}|{r['previous_min']:.6f}|{r['current_min']:.6f}|{r['saved_s']:.6f}|{r['previous_kWh']:.6f}|{r['current_kWh']:.6f}|{r['previous_transport_N']}→{r['current_transport_N']}|\n"
text+='\n第二问以所有运输机返航计算Cmax，第三问包含中继返航。两问各80箱、D=0，普通期望时限、医疗及首批硬时限均通过。字典序仍为D→完成时间→能耗→架次数，时间改善允许后续目标变差；因此不能把所有指标都称为改善。前轮方案保存在outputs/refinement，可作为能耗与架次对照。\n\n'
for q,s,v in [('Q2',q2,v2),('Q3',q3,load(OUT/'q3/verification.json'))]:
 a=v['baseline'];text+=f"{q}：运输机{len(a['used_units'])}架，电池{len(a['used_batteries'])}组；最小硬时限余量{a['hard_deadline_min_slack_s']:.6f}s；最低返航SOC{100*(.2+a['min_energy_reserve_slack']):.6f}%。\n\n"
j=v3['baseline'];text+=f"Q3中继{j['relay_sorties']}架次，实体机{len(j['relay_units'])}架，能源组件{len(j['relay_components'])}组，中继能耗{j['relay_energy_kWh']:.9f}kWh。\n\n"
text+='## 搜索方法与局限\n\nQ2以先前方案热启动，加入三架次重组、整服务区货箱转移，以及机型、排序、拆分和合并邻域；第一轮240秒，种子2026092601，最多4个访问点；第二轮240秒，种子2026092602，最多5点，并扩大退火扰动。扩大范围后未再降低已找到的字典序目标，不等于全局最优。Q3先搜索悬停位置与高度，再进行含货箱重组的服务日历联合搜索，240秒、种子2026092603、最多4点；几何缓存按2秒检查、候选匹配按0.5秒检查，最终由另一套代码加密验证。后续位置细化和路线比较见日志。限制三中继架次、两实体机的结构是搜索限制；没有枚举任意架次数或连续位置，不能证明全局最优。\n\n只有D≥0且达到0构成首层目标的最优性证据。两种目标优先级在当前候选池中的结果见各问summary.json，不能据相同结果断言所有目标等价。\n\n'
text+='## 第四问重新冻结与分区\n\n资源顺序：A/B/C运输机、A/B/C电池、中继机、中继能源组件；库存4/2/2/6/4/4/2/6。\n\n|K|需求向量|缺口向量|归一化缺口G|归一化配置S|工作量CV|\n|---|---|---|---:|---:|---:|\n'
old4=load(ROOT/'outputs/refinement/q4/summary.json')
group_notes=[]
for K in [2,3]:
 x=q4['results'][f'K{K}_baseline'];text+=f"|{K}|{x['total_resources']}|{x['gap']}|{x['G']:.6f}|{x['S']:.6f}|{x['CV']:.6f}|\n"
 group_notes.append(f'\nK={K}：\n')
 for g in x['groups']:group_notes.append(f"\n{g['group']}：{'、'.join(sorted(g['sites']))}。\n")
 group_notes.append(f"\n合法无标签分区{x['all_partitions']}种，全部枚举。前轮G={old4['results'][f'K{K}_baseline']['G']}，本轮G={x['G']}。\n")
text+=''.join(group_notes)
text+=f"\n运输绑定块共{q4['block_count']}个。未分区最小配置{q4['pooled_minimum']}。独立枚举证书{len(v4['optimality_certificate'])}项、事件检查{len(v4['scenarios'])}种解释/目标情景。第四问最优性仅针对本轮冻结方案、完整中继副本及组内允许重新编号的解释。禁止副本时结果：{q4['no_copy']}。每个组、每类资源的同时占用任务和关键时段见peak_evidence.csv；不得用其他型号富余抵消缺口。\n\n"
text+='## 独立验证与假设\n\n时间容差1e-7秒，能耗1e-8kWh，SOC1e-10，质量1e-9kg，体积1e-12m³；未舍入数值用于判定。运输机体从准备开始至返航，电池至充满；中继机体至周转结束、能源组件至充满。任务和充电无重叠，原库存及硬约束未放宽。原始文件SHA-256保持一致。\n\n'
for scan in j['scans']:text+=f"- 通信：dt={scan['dt_s']}s，空间={scan['spatial_spacing_m']}，{scan['points']}点，失败{scan['failed_points']}点，最差裕量{scan['worst']['margin_db']:.9g}dB。\n"
text+=f"\n仅能表述为‘在所述时空分辨率下未发现中断’；仍有{j['uncertified_phase_intervals']}个阶段未给出连续时间数学证书。最差时刻见joint_verification.json。标准航程整组能量标定、爬升效率解释、不计运输交接悬停能耗，以及中继并发与零切换耗时，均是工作假设，需要用户核验；真实无线容量未认证。\n\n论文未自动改写；采用本轮结果时，须同时更新摘要、表格、甘特图以及第四问分区，不能混用前轮任务。截图缺少完整明细，无法确认其与本模型口径一致，本轮没有将截图数值作为结果。正式竞赛请遵守赛事规则。\n"
(OUT/'优化结果说明.md').write_text(text,encoding='utf-8')
for q in ['q2','q4']:
 (OUT/q/'模型与结果说明.md').write_text(text,encoding='utf-8');(OUT/q/'独立检查报告.md').write_text(text,encoding='utf-8')
for name in ['baseline','makespan_first']:
 p=load(OUT/'q2'/name/'plan.json');gantt(p,OUT/'q2'/name/'无人机任务甘特图.png');gantt(p,OUT/'q2'/name/'电池周转图.png',True);routechart(p,read(ROOT/'outputs/preflight/nodes.csv'),OUT/'q2'/name/'运输路线图.png')
subprocess.run([sys.executable,str(OUT/'q4_charts.py')],check=True)
wb=Workbook();wb.remove(wb.active)
for sheet,path in [('Q2_运输架次',OUT/'q2/baseline/Q2_运输架次.csv'),('Q2_逐箱交付',OUT/'q2/baseline/Q2_逐箱交付.csv'),('Q3_运输架次',OUT/'q3/baseline/Q2_运输架次.csv'),('Q3_逐箱交付',OUT/'q3/baseline/Q2_逐箱交付.csv'),('Q3_中继架次',OUT/'q3/baseline/Q3_中继架次.csv'),('Q3_通信保障',OUT/'q3/baseline/Q3_通信保障.csv'),('Q4_分区配置',OUT/'q4/Q4_分区配置.csv')]:
 rows=read(path);ws=wb.create_sheet(sheet);ws.append(list(rows[0]));[ws.append(list(r.values())) for r in rows];ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
wb.save(OUT/'更新结果表.xlsx');print('Reports/charts/workbook ready',flush=True)
