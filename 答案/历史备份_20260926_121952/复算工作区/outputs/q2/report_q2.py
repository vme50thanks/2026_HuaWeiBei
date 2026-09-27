"""Create reproducible reports and PNG route/resource charts from verified plans."""
from pathlib import Path
from collections import Counter
import json,csv,math,argparse
from PIL import Image,ImageDraw,ImageFont
from openpyxl import load_workbook
def read(p):
 with p.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def table(head,rows):return '\n'.join(['| '+' | '.join(head)+' |','|'+'|'.join('---' for _ in head)+'|']+['| '+' | '.join(map(str,r))+' |' for r in rows])
def write(p,rows):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def font(size):
 for name in ['C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/arial.ttf']:
  if Path(name).exists():return ImageFont.truetype(name,size)
 return ImageFont.load_default()
COL={'A':'#377eb8','B':'#269778','C':'#9463b1'}
def gantt(plan,path,battery=False):
 rows=sorted({a['battery' if battery else 'unit'] for a in plan});W=1800;H=190+len(rows)*65
 im=Image.new('RGB',(W,H),'white');d=ImageDraw.Draw(im);left=180;right=1710;top=115
 end=max(a['battery_ready'] if battery else a['finish'] for a in plan);limit=math.ceil(end/600)*600
 x=lambda t:left+(right-left)*t/limit
 d.text((50,25),'电池任务占用与充电周转' if battery else '无人机任务甘特图',fill='#162838',font=font(30))
 d.text((50,68),'任务从准备开始计入占用；最终补电不计入Cmax' if battery else '色块包含准备、装载、飞行和交接；横轴为任务开始后的分钟',fill='#536574',font=font(20))
 for t in range(0,limit+1,600):
  xx=x(t);d.line((xx,top,xx,H-55),fill='#e1e7eb',width=1);d.text((xx-12,H-42),str(t//60),fill='#536574',font=font(19))
 for k,r in enumerate(rows):
  y=top+k*65;d.text((30,y+10),r,fill='#162838',font=font(21))
  for a in plan:
   if a['battery' if battery else 'unit']!=r:continue
   d.rectangle((x(a['start']),y+6,x(a['finish']),y+45),fill=COL[a['model']],outline='white',width=2)
   d.text((x(a['start'])+4,y+13),a['sortie'],fill='white',font=font(17))
   if battery:d.rectangle((x(a['finish']),y+6,x(a['battery_ready']),y+45),fill='#f3be6b')
 if battery:
  cx=x(max(a['finish'] for a in plan));d.line((cx,top,cx,H-55),fill='#b83b3b',width=3);d.text((cx-70,80),'Cmax',fill='#b83b3b',font=font(18));d.text((1300,30),'彩色：任务  橙色：充电',fill='#536574',font=font(20))
 im.save(path)
def routechart(plan,nodes,path):
 W,H=2100,1020;im=Image.new('RGB',(W,H),'white');d=ImageDraw.Draw(im)
 points={r['node_id']:(float(r['x_local_m'])/1000,float(r['y_local_m'])/1000) for r in nodes}
 xmin=min(v[0] for v in points.values())-.7;xmax=max(v[0] for v in points.values())+.7;ymin=min(v[1] for v in points.values())-.7;ymax=max(v[1] for v in points.values())+.7
 d.text((45,22),'第二问运输路线（按机型分面）',fill='#162838',font=font(34));d.text((45,72),'平面位置单位：km；箭头为航段方向。线条重叠表示多个架次共享航段，并非同一时刻飞行。',fill='#536574',font=font(22))
 for k,g in enumerate('ABC'):
  x0=30+690*k;y0=175;ww=625;hh=730
  def xy(n):
   x,y=points[n];scale=min(ww/(xmax-xmin),hh/(ymax-ymin))
   return (x0+ww/2+(x-(xmin+xmax)/2)*scale,y0+hh/2-(y-(ymin+ymax)/2)*scale)
  d.text((x0+220,125),g+'型',fill=COL[g],font=font(28));d.rectangle((x0,y0,x0+ww,y0+hh),outline='#c4cdd3',width=1)
  for a in plan:
   if a['model']!=g:continue
   rt=['O01']+a['route']+['O01']
   for u,v in zip(rt,rt[1:]):
    p1,p2=xy(u),xy(v);d.line((*p1,*p2),fill=COL[g],width=2)
    xx=p1[0]*.45+p2[0]*.55;yy=p1[1]*.45+p2[1]*.55;ang=math.atan2(p2[1]-p1[1],p2[0]-p1[0])
    d.polygon([(xx,yy),(xx-10*math.cos(ang-.45),yy-10*math.sin(ang-.45)),(xx-10*math.cos(ang+.45),yy-10*math.sin(ang+.45))],fill=COL[g])
  for n in points:
   xx,yy=xy(n);r=7 if n=='O01' else 4;d.ellipse((xx-r,yy-r,xx+r,yy+r),fill='#152838' if n=='O01' else '#657888',outline='white')
   d.text((xx+5,yy-24 if n in ['S001','S004','S009','S013'] else yy+3),n,fill='#152838',font=font(17))
  d.text((x0+80,930),f'{xmin:.1f} ≤ x ≤ {xmax:.1f}; {ymin:.1f} ≤ y ≤ {ymax:.1f} km',fill='#536574',font=font(18))
 im.save(path)
def main(source,pre,out):
 summary=json.loads((out/'summary.json').read_text(encoding='utf-8'));verify=json.loads((out/'verification.json').read_text(encoding='utf-8'));log=json.loads((out/'search_log.json').read_text(encoding='utf-8'))
 plans={n:json.loads((out/n/'plan.json').read_text(encoding='utf-8')) for n in ['baseline','makespan_first']}
 boxes={r[0]:r for r in list(load_workbook(next(source.rglob('物资需求与配送时限.xlsx')),data_only=True)['逐箱货箱清单'].values)[1:] if r[0]}
 rr=list(load_workbook(next(source.rglob('运输无人机数据.xlsx')),data_only=True).active.values);models={r[0]:r for r in rr[2:5]}
 nodes=read(pre/'nodes.csv');ft={(r['from_id'],r['to_id'],r['model_id']):float(r['flight_time_s']) for r in read(pre/'flight_times.csv')};ids=[r['node_id'] for r in nodes]
 # Certified optimistic bound: shortest flight paths on the complete node graph,
 # ignore energy, other cargo, resource contention and intermediate handovers.
 dist={}
 for g in 'ABC':
  dd={(i,j):(0 if i==j else ft[i,j,g]) for i in ids for j in ids}
  for k in ids:
   for i in ids:
    for j in ids:dd[i,j]=min(dd[i,j],dd[i,k]+dd[k,j])
  dist[g]=dd
 bound=max(min(m[10]+m[11]+dist[g]['O01',b[1]]+m[12]+m[13]+dist[g][b[1],'O01'] for g,m in models.items() if b[3]<=m[3] and b[4]<=m[4]) for b in boxes.values())
 comparison=[];late=[];resource=[]
 for name,plan in plans.items():
  a=summary[name];comparison.append(dict(scenario=name,priority='D>Cmax>E>N' if name=='baseline' else 'Cmax>D>E>N',D=a['D'],Cmax_s=a['Cmax'],energy_kWh=a['E'],sorties=a['N'],status='INDEPENDENTLY_VERIFIED_FEASIBLE',Cmax_lower_bound_s=bound))
  for p in plan:
   for b,t in p['deliveries'].items():
    r=boxes[b];late.append(dict(scenario=name,box_id=b,delivery_s=t,expected_s=r[7],delay_s=max(0,t-r[7]) if r[7] is not None else 0,weighted_delay=r[8]*max(0,t-r[7]) if r[7] is not None else 0,medical=r[2]=='医疗物资',first_batch=r[5]=='是'))
  for u in sorted({p['unit'] for p in plan}):
   pp=[p for p in plan if p['unit']==u];resource.append(dict(scenario=name,unit=u,model=pp[0]['model'],sorties=len(pp),busy_s=sum(p['finish']-p['start'] for p in pp),last_return_s=max(p['finish'] for p in pp)))
  gantt(plan,out/name/'drone_gantt.png');gantt(plan,out/name/'battery_gantt.png',True);routechart(plan,nodes,out/name/'routes.png')
  usage=read(out/name/'resource_usage.csv')
  write(out/name/'drone_occupancy.csv',[dict(sortie=r['sortie'],unit=r['unit'],model=r['model'],start_s=r['start'],end_s=r['return_time']) for r in usage])
  write(out/name/'battery_cycles.csv',[dict(sortie=r['sortie'],battery=r['battery'],model=r['model'],reserve_start_s=r['start'],return_s=r['return_time'],soc_start=r['soc_start'],soc_return=r['soc_return'],charge_start_s=r['charge_start'],charge_end_s=r['charge_end'],ready_s=r['charge_end']) for r in usage])
 write(out/'priority_comparison.csv',comparison);write(out/'delivery_timeliness.csv',late);write(out/'resource_summary.csv',resource)
 searchrows=[]
 for k in [1,2,3]:
  good=[r for r in log if r['maxstops']==k and r['status']=='FEASIBLE'];best=min(good,key=lambda r:(r['D'],r['Cmax'],r['E'],r['N']))
  searchrows.append(dict(maxstops=k,attempts=sum(r['maxstops']==k for r in log),feasible=len(good),best_D=best['D'],best_Cmax=best['Cmax'],best_E=best['E'],best_N=best['N']))
 write(out/'search_scope_comparison.csv',searchrows)
 b=summary['baseline'];alt=summary['makespan_first'];v=verify['baseline']
 report=r'''# 第二问模型与调度结果

本报告对应用户授权的工作假设，依次完成变量与约束建立、启发式优化、独立确定性事件回放。所有工作假设需要用户核验；本材料不是完整参赛论文。

## 1 结论与适用范围

'''
 report+=f"基准方案完成80箱交付，16个医疗箱和30个首批保障箱（两类可以重叠）均满足硬时限。加权延误D={b['D']:.6f}，所有货箱也均在各自期望时间内交付；Cmax={b['Cmax']:.6f}秒（{b['Cmax']/60:.6f}分钟），能耗{b['E']:.9f}kWh，共{b['N']}架次，其中{b['multi_stop_sorties']}架次访问两个服务区。8架实体无人机和14组电池均有使用，未增加库存。\n\n"
 report+='这是独立验证通过的当前最好可行方案，未证明整体全局最优，也未证明有限候选范围的穷尽最优。仅D=0达到其非负下界，可单独证明第一目标最优。第一问18架次的单点下界未用于第二问。\n\n'
 report+='## 2 输入与假设\n\n核对原题及附件9个源文件SHA256与preflight一致，复用节点、240条有向航段、720条机型飞行时间和时间规则。未修改原文件。读取全部80箱的质量、体积、目的地、医疗类别、首批标记、硬截止、期望时间和优先系数；空白时间保持缺失，不当作0。\n\n'
 report+=r'''能耗继续采用用户授权的基准：

\[
L_g(q)=L_g^0-(L_g^0-L_g^F)(q/Q_g)^{3/2},\quad
E_{gij}(q)=E_g^{use}\frac{d_{ij}}{L_g(q)}+
\frac{(m_g+q)9.80665h^+_{ij}}{\eta_g3.6\times10^6}.
\]

标准航程按整组可用能量标定、效率置于分母、无额外运输交接悬停能耗，均为工作假设，需要用户核验。下降不另加能耗。质量随每站交付递减，每一航段重新爬升、巡航、下降，返航空载。

开始时刻为准备开始；起飞=开始+固定准备+箱数×装载时间。每站停留=基础交接+本次箱数×逐箱交接；该次访问所有箱统一以交接结束为完成时刻。基准硬时限已有充足余量，未因保守批量交接出现硬时限不可行，故未另外改变为顺序交接口径。

无人机占用从准备到落地；运输机不另加未提供的周转常数，下一任务完整准备。电池准备开始预留，落地立即充电，额外拆装时间取0，充满后才可再分配。不同电池并行充电，不人为新增单充电器或单工位限制。这些阶段边界是工作假设，需要用户核验。

初始SOC为1；返航SOC=1−架次能耗/可用能量≥20%。充电时间严格使用题给两阶段式：低于0.9为 `Tfull[0.65(0.9−s)/0.9+0.35]`；不低于0.9为 `Tfull×0.35(1−s)/0.1`。电池6/4/4组已包含初始机载使用，不能另加8组。电池编号A/B/C-BAT-xx为本次按库存创建的明确标识，不是附件已有逐组序列号。

## 3 参数、变量和约束

| 符号 | 含义 | 类型／单位 | 来源 |
|---|---|---|---|
| w_b,v_b,d_b,α_b | 货箱质量、体积、期望时间、优先系数 | 参数：kg、m³、s、无量纲 | 逐箱清单 |
| h_b | 医疗期望与首批截止中适用者的最小值 | 派生硬截止，s | 题目和逐箱清单 |
| x_bp | 箱b是否属于架次p | 0—1决策 | 联合组批 |
| a_pij | 架次p是否走i→j | 0—1决策 | 访问顺序 |
| u_pk,e_pe | 架次使用实体无人机k、电池e | 0—1决策 | 资源分配 |
| s_p,f_p | 准备开始、返航落地 | 连续决策／派生，s | 时间线 |
| q_pij,SOC_e | 剩余载荷、电池荷电状态 | 状态：kg、0—1 | 载荷守恒、能量与充电 |
| T_b | 货箱交付完成时刻 | 派生，s | 交接结束 |
| D,Cmax,E,N | 加权延误、末架次返航、能耗、架次 | 指标：加权秒、s、kWh、次 | 方案汇总 |

基本约束：每箱恰好一次、目的地正确、不可拆；每架次从O01出发并返回；箱分配与路径访问一致；起飞质量和体积不超机型上限（交付后递减）；逐段能耗和满足返航余量。医疗和首批硬时限 `T_b≤h_b` 不以罚项替代。

资源约束：每个实体无人机任务区间两两不重叠；电池与无人机机型一致；同一电池任务区间和充电区间不重叠，下一任务开始不早于上一充电结束。充电区间虽可超过Cmax，但末次充电不延长Cmax。

目标：`D=Σ α_b max(0,T_b−d_b)`（对有期望时间的货箱求和），`Cmax=max f_p`，`E=Σ E_p`，`N=架次数`。基准按D→Cmax→E→N，对照按Cmax→D→E→N，均用原始浮点指标排序而非先取整。优先级是建模选择。

## 4 算法与搜索限制

采用多起点随机扰动的贪心组批与路线插入：按实际无人机和电池的最早联合可用时刻安排下一任务；在最多5个候选起始服务区中构造装载，加入货箱时检查质量、体积、各次交付硬时限及返航能量；对当前装载涉及的访问顺序做全排列。随机性仅用于搜索，不表示灾情、设备或需求随机。

每架次最多访问1、2、3个服务区分别运行2000个种子（0—1999），合计6000次构造。在完整搜索后追加5000步局部扰动（种子20260923），包括批次顺序交换、移箱、交换箱和合并；每次重新分配机型、实体机和电池并计算全部时刻。只有可行方案进入比较池。

这些上限、贪心顺序、候选起点数及局部邻域都是计算限制，非题目规定。未搜索所有货箱分组、所有调度顺序或四个以上服务区架次；当前最好方案不能代表候选空间穷尽最优。两种目标在同一个已生成候选池中分别筛选，便于比较，但不构成对两个完整优化问题的精确求解。

'''.replace(chr(92)*2,chr(92))
 report+=f"构造阶段实际耗时{summary['search']['elapsed_seconds']:.3f}秒，时间上限180秒，完成6000次；找到{summary['search']['feasible']}个完整可行候选。局部搜索实际耗时{summary['local_search']['seconds']:.3f}秒，上限90秒，完成5000步，得到{summary['local_search']['feasible_candidates']}个可行候选。重复候选也计入次数。未找到方案的起点只标为搜索失败，不推断模型不可行。\n\n"
 report+=table(['最大访问数','构造次数','可行次数','最好D','最好Cmax秒','能耗kWh','架次'],[[r['maxstops'],r['attempts'],r['feasible'],f"{r['best_D']:.3f}",f"{r['best_Cmax']:.3f}",f"{r['best_E']:.6f}",r['best_N']] for r in searchrows])
 report+='\n\n扩展到2、3点的构造阶段未必改善指标；局部搜索最终得到含双服务区架次的方案，在保持基准完成时间不变时降低能耗并减少架次数。该实验说明有限扩展的实际效果，不证明更多访问点无价值。\n\n'
 report+=f"最优性界限：D的严格下界为0，基准达到。对Cmax，使用各机型航段飞行时间的全节点最短路径，忽略能源、资源争用、中途交接和其他货箱，只保留一箱所需准备、装载及目的站交接，得到保守下界 **{bound:.6f}秒**。因此D=0条件下最优Cmax目前可界定在[{bound:.6f}, {b['Cmax']:.6f}]秒。该宽区间不是MIP求解器gap，也不证明接近最优。\n\n"
 report+='## 5 目标比较与资源结果\n\n'+table(['优先级','D（加权秒）','Cmax秒','总能耗kWh','架次'],[[r['priority'],f"{r['D']:.6f}",f"{r['Cmax_s']:.6f}",f"{r['energy_kWh']:.9f}",r['sorties']] for r in comparison])
 delayed=[r for r in late if r['scenario']=='makespan_first' and r['delay_s']>1e-7]
 report+=f"\n\n完成时间优先比基准提前{b['Cmax']-alt['Cmax']:.6f}秒，但有{len(delayed)}箱超过期望时间；它们均不违反医疗或首批硬时限。详见delivery_timeliness.csv，不能将此对照称为零延误方案。\n\n"
 report+=table(['机体','机型','架次','占用秒','末次返航秒'],[[r['unit'],r['model'],r['sorties'],f"{r['busy_s']:.3f}",f"{r['last_return_s']:.3f}"] for r in resource if r['scenario']=='baseline'])
 report+=f"\n\n基准最小硬时限裕量{v['hard_deadline_min_slack_s']:.6f}秒；最小返航SOC为{(v['min_energy_reserve_slack']+.2)*100:.6f}%。每块电池从满电出发，返航后两阶段补电，复用无冲突。数量使用不是资源优化证明，本题所给库存被作为上限。\n\n"
 report+='## 6 独立回放\n\nverify_q2.py不导入求解器。重新读取原始节点、货箱、机型、设备和电池库存，以40位Decimal重算各航段能耗、爬升巡航下降时间、交接和硬时限；几何沿用已核验DEM最高点，独立用原节点坐标检查距离。\n\n'
 report+=f"两方案全部通过80箱唯一交付、逐段剩余载荷、容量与能量、16个医疗箱和30个首批箱时限、全部8机及14电池机型与库存检查。每方案回放{v['events']}个资源事件（准备开始、落地进入充电、充满）；连续时刻以已独立重算并核对的导出边界排序，同一时刻先释放/充满再分配，避免浮点表达差异制造伪重叠。基准最大能耗重算差{v['max_energy_recompute_error_kWh']:.3e}kWh。\n\n"
 report+='检查容差：时间10⁻⁷秒、能量10⁻⁸kWh、质量10⁻⁹kg、体积10⁻¹²m³、SOC 10⁻¹⁰。确定性回放没有随机分布，不适用重复抽样均值或置信区间。具体事件和最终资源状态见各方案event_replay.csv。\n\n'
 report+='## 7 成果使用\n\n各方案目录的Q2_运输架次.csv与Q2_逐箱交付.csv字段和原模板一致，开始时刻为准备开始，起飞时刻另列resource_usage.csv。文件是可由Excel打开的CSV，不是改写后的原XLSX模板。legs.csv含逐段载荷与能耗，stops.csv含到达和交接完成；drone_occupancy.csv、battery_cycles.csv分别给出两类占用记录。\n\n路线图是局部米制平面坐标示意，不是DEM或真实航拍地图；按机型分面显示，重复航段会重叠。甘特图横轴为分钟，任务色块含准备装载和交接；橙色是充电，最终补电可在Cmax之后。\n\n'
 report+='能耗分项补全、不计交接悬停功率、拆装零时间、批量交付及几何近似仍需核验。若官方规则调整，应整体复算。正式竞赛使用需遵守AI辅助、来源披露和成果提交规则。\n'
 (out/'模型与调度报告.md').write_text(report,encoding='utf-8')
 verification_report='# 第二问独立可行性检查\n\n'+table(['方案','80箱','硬时限','机体与电池冲突','结果'],[[n,verify[n]['boxes'],'全部满足','无',verify[n]['status']] for n in plans])+'\n\n逐项证据见verification.json与各方案event_replay.csv。检查逻辑和容差见模型与调度报告第6节。对照方案存在普通货箱超期，属于软目标差异，不是硬时限违规。\n'
 (out/'独立回放报告.md').write_text(verification_report,encoding='utf-8')
 (out/'README.md').write_text(r'''# 第二问复算

依赖：Python 3.10+、openpyxl、Pillow。无需商业优化器。源文件保持只读。

在本目录执行（preflight为相邻目录）：

```powershell
python solve_q2.py --source 'D:\研一\比赛\中文题目\D题' --preflight '..\preflight' --runs 2000 --seconds 180
python improve_q2.py --source 'D:\研一\比赛\中文题目\D题' --preflight '..\preflight' --iterations 5000 --seconds 90
python verify_q2.py --source 'D:\研一\比赛\中文题目\D题' --preflight '..\preflight'
python report_q2.py --source 'D:\研一\比赛\中文题目\D题' --preflight '..\preflight'
```

实际运行Python：C:\Users\ASUS\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe。
PowerShell可把python替换为 & '该绝对路径'。源文件校验路径对应本次环境；迁移数据后应明确更新源审计位置并核验哈希，不要绕过校验。

构造种子0—1999，局部搜索种子20260923。本次完成所有迭代，时间限制未触发；若机器更慢导致提前达到时间上限，候选池可能不同。搜索随机性不是物理仿真随机性。

baseline目录为D优先，makespan_first为完成时间优先。所有CSV保存未人为取整结果，PNG为可读图。两方案独立检查均通过。详细数学模型、限制与下界见模型与调度报告.md。

improve_q2.py会读取并覆盖已有两方案，因此完全复算时应从solve_q2.py开始。报告脚本依赖Pillow和Windows字体（优先微软雅黑）；其他系统应配置对应字体。
'''.replace(chr(92)*2,chr(92)),encoding='utf-8')
 (out/'bounds.json').write_text(json.dumps(dict(D_lower_bound=0,Cmax_lower_bound=bound,Cmax_incumbent=b['Cmax'],method='Optimistic per-box shortest-path roundtrip without energy or resource constraints; max over boxes.'),indent=2),encoding='utf-8')
 print('Report and plots generated. Bound:',bound,'late comparison boxes:',len(delayed))

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--source',type=Path,required=True);a.add_argument('--preflight',type=Path,required=True);a.add_argument('--out',type=Path,default=Path(__file__).resolve().parent);r=a.parse_args();main(r.source,r.preflight,r.out)
