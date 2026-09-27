"""Package verified Q3 records before Q4 freezes their hashes."""
from pathlib import Path
import sys,json,hashlib,csv
ROOT=Path(__file__).resolve().parents[2];out=Path(__file__).parent/'q3';sys.path.insert(0,str(ROOT/'outputs/q3'))
from communication import World,csvout,dump
from report_joint import charts
load=lambda p:json.loads(p.read_text(encoding='utf-8'))
s=load(out/'summary.json');v=load(out/'verification.json');j=load(out/'joint_verification.json');audit=load(ROOT/'outputs/preflight/audit.json');manifest=[]
for x in audit['sources']:
 h=hashlib.sha256(Path(x['path']).read_bytes()).hexdigest();assert h==x['sha256'];manifest.append(dict(path=x['path'],original_sha256=h,current_sha256=h,unchanged=True))
dump(out/'source_consistency.json',dict(sources=manifest,source_files_modified=False))
w=World(Path('D:/研一/比赛/中文题目/D题'),ROOT/'outputs/preflight');checks={};report='# 新第三问：实际优化与独立回放\n\n'
for name in ['baseline','makespan_first']:
 d=out/name;p=load(d/'plan.json');r=load(d/'relay_plan.json');assert v[name]['status']=='PASS' and all(x['failed_points']==0 for x in j[name]['scans'])
 charts(w,p,r,d)
 phases=load(d/'independent_transport_phases.json')+load(d/'relay_phases.json')
 csvout(d/'trajectory_segments.csv',[dict(sortie=x['sortie'],phase=x['phase'],start_s=x['start'],end_s=x['end'],x0=x['a'][0],y0=x['a'][1],z0=x['a'][2],x1=x['b'][0],y1=x['b'][1],z1=x['b'][2]) for x in phases])
 rows=list(csv.DictReader((d/'Q3_通信保障.csv').open(encoding='utf-8-sig')));rp={x['sortie']:x for x in r}
 for pp in p:
  rr=sorted([x for x in rows if x['运输架次编号']==pp['sortie']],key=lambda x:float(x['开始时刻（s）']))
  assert abs(float(rr[0]['开始时刻（s）'])-pp['takeoff'])<1e-7 and abs(float(rr[-1]['结束时刻（s）'])-pp['finish'])<1e-7
  assert all(abs(float(x['结束时刻（s）'])-float(y['开始时刻（s）']))<1e-7 for x,y in zip(rr,rr[1:]))
 for x in rows:
  if x['中继架次编号']:
   r0=rp[x['中继架次编号']];assert float(x['开始时刻（s）'])>=r0['service_start']-1e-7 and float(x['结束时刻（s）'])<=r0['service_end']+1e-7
 checks[name]=dict(coverage_contiguous=True,within_service=True,boxes=80)
 s[name]['status']='VERIFIED_AT_REPORTED_RESOLUTIONS_NO_GLOBAL_PROOF'
 report+=f"## {name}\n\nD={s[name]['D']}; C_joint={s[name]['C_joint']:.9f}s; 运输能耗={s[name]['E']:.9f}kWh；中继能耗={s[name]['relay_E']:.9f}kWh；运输/中继架次={len(p)}/{len(r)}。80箱全部按期交付，医疗16箱和首批30箱硬时限通过。\n\n"
 report+='|时间步长s|空间检查|点数|失败点|最差裕量dB|\n|---|---|---:|---:|---:|\n'
 for scan in j[name]['scans']:report+=f"|{scan['dt_s']}|{scan['spatial_spacing_m']}|{scan['points']}|{scan['failed_points']}|{scan['worst']['margin_db']:.9g}|\n"
report+='''
## 模型与搜索限制

沿用原先能耗与时间规则。标准航程按整组可用能量标定、爬升效率按势能转换解释、不计缺少功率参数的运输交接悬停能耗，均为工作假设，需要用户核验。满电复用、半开资源占用区间、服务交接完成计算交付；原库存与硬时限保持不变。

新增通信服务日历参与运输机型、顺序和开始时刻选择。使用旧方案与新Q2组批作为两组初始候选，不固定原Q2任务时刻。中继位置来自原597个地形候选；先检查49位置的1904组旧三架次结构，再在位置130/511/489上优化两次接续中继服务窗口与运输顺序。未进行无限位置或任意中继架次数的全域搜索。搜索日历暂要求全部期望时限满足，这是求D=0可行解的搜索限制，不将普通物资期望时间改称题目硬时限。优化状态仅为当前搜索得到的最好方案，无全局最优证明。

中继支持多机且切换无额外耗时仍为工作假设；未验证真实带宽/干扰容量。第四问必须冻结本目录baseline，不能混用旧Q3或替代方案。

## 独立检查与精度

verify_joint.py独立重读原始表格，运输能耗用40位Decimal重新计算，并回放机体和电池事件；中继另行遍历DEM射线、计算飞行与服务能耗、充电和周转。1秒/5米、0.5秒/2.5米及0.5秒/全穿越像元三组对比，低裕量或切换附近加密至0.05秒；切换点二分至1e-7秒。所有运输阶段仍列入uncertified_continuous_intervals.csv。

结论严格表述为：**在所述时空分辨率下未发现中断**。尚未数学证明连续通信，不把失败采样点数0写成已证明的中断时长0。时间容差1e-7s、能耗1e-8kWh、SOC1e-10、质量1e-9kg、体积1e-12m³、链路1e-9dB。
'''
(out/'模型与结果说明.md').write_text(report,encoding='utf-8');(out/'独立检查报告.md').write_text(report,encoding='utf-8');dump(out/'export_check.json',checks);dump(out/'summary.json',s)
print('Q3 ready for freezing')
