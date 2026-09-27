from pathlib import Path
import json,csv,argparse,math,importlib.metadata,sys,zipfile,hashlib
from PIL import Image,ImageDraw,ImageFont
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,x):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(x[0]));w.writeheader();w.writerows(x)
F=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
COL=['#217eab','#d67b28','#7c4da9'];LABELS=['A运输机','B运输机','C运输机','A电池','B电池','C电池','中继机','中继组件']
def main(a):
 s=load(a.out/'summary.json');v=load(a.out/'verification.json');bind=load(a.out/'binding_blocks.json');nodes={x['node_id']:x for x in read(a.pre/'nodes.csv')};comp=[];group_rows=[]
 for key,x in s['results'].items():
  comp.append(dict(scenario=key,K=x['K'],mode=x['mode'],G=x['G'],S=x['S'],CV=x['CV'],**dict(zip(s['resource_order'],x['total_resources'])),gap_vector=';'.join(map(str,x['gap'])),extra_relay_N=x['extra_relay_N'],extra_relay_E=x['extra_relay_E'],extra_relay_body_work_s=x['extra_relay_body_work_s'],extra_relay_energy_occupied_s=x['extra_relay_energy_occupied_s']))
  for g in x['groups']:group_rows.append(dict(scenario=key,**{k:(';'.join(val) if k=='sites' else val) for k,val in g.items() if k not in ['resources','mask']}))
  d=a.out/key;tasks=load(d/'tasks.json');cycles=[]
  for t in tasks:
   p=t['frozen'];relay=t['kind']=='relay';cycles.append(dict(group=t['group'],task=t['copy_id'],original_task=t['original_task'],component=t['energy_component'],reserve_start=p['start'],soc_start=1.0,return_s=p['finish'],soc_return=p['soc'],energy_kWh=p['energy'],charge_start=p['finish'],full_ready=p['component_ready'] if relay else p['battery_ready'],soc_ready=1.0))
  write(d/'energy_cycles.csv',cycles)
 write(a.out/'全部方案指标对比.csv',comp);write(a.out/'各组工作量与任务统计.csv',group_rows)
 for K in [2,3]:
  name=f'K{K}_baseline';x=s['results'][name];d=a.out/name;groups=x['groups'];im=Image.new('RGB',(1400,1050),'white');dr=ImageDraw.Draw(im);dr.text((40,25),f'K={K} 服务区分组（不要求地理连通）',fill='#17334c',font=F(29))
  xs=[float(n['x_local_m']) for n in nodes.values()];ys=[float(n['y_local_m']) for n in nodes.values()];scale=min(1170/(max(xs)-min(xs)),690/(max(ys)-min(ys)));xy=lambda n:(110+(float(n['x_local_m'])-min(xs))*scale,840-(float(n['y_local_m'])-min(ys))*scale)
  for gi,g in enumerate(groups):
   for site in g['sites']:
    xx,yy=xy(nodes[site]);dr.ellipse((xx-7,yy-7,xx+7,yy+7),fill=COL[gi]);dr.text((xx+10,yy-15),site,fill=COL[gi],font=F(20))
   dr.text((45,890+gi*36),f"{g['group']}："+'、'.join(g['sites']),fill=COL[gi],font=F(18))
  xx,yy=xy(nodes['O01']);dr.rectangle((xx-7,yy-7,xx+7,yy+7),fill='#333333');dr.text((xx+12,yy-14),'O01',fill='#333333',font=F(20));dr.text((1120,88),'北 ↑',font=F(22),fill='#444444');im.save(d/'分区地图.png')
  alloc=read(d/'resource_assignment.csv');names=sorted({r['resource'] for r in alloc});height=130+len(names)*29;im=Image.new('RGB',(1600,height),'white');dr=ImageDraw.Draw(im);dr.text((35,20),f'K={K} 各组资源占用（含能源补电和中继周转）',fill='#17334c',font=F(26));maxt=max(float(r['end']) for r in alloc);tx=lambda t:300+float(t)/maxt*1230
  for i,rid in enumerate(names):
   y=80+i*29;dr.text((15,y),rid,fill='#273c4d',font=F(15));dr.line((300,y+21,1540,y+21),fill='#e6e6e6')
   for r in alloc:
    if r['resource']==rid:dr.rectangle((tx(r['start']),y,tx(r['end']),y+19),fill=COL[int(r['group'][1:])-1],outline='white');dr.text((tx(r['start'])+2,y),r['task'],font=F(12),fill='white')
  for t in range(0,int(maxt)+1,1000):dr.text((tx(t)-13,height-35),str(t),font=F(16),fill='#444444')
  im.save(d/'各组资源占用图.png')
 im=Image.new('RGB',(1600,720),'white');dr=ImageDraw.Draw(im);dr.text((35,25),'八类资源：库存与两种基准分区需求',font=F(29),fill='#17334c');series=[s['inventory'],s['results']['K2_baseline']['total_resources'],s['results']['K3_baseline']['total_resources']];colors=['#8898a7',COL[0],COL[1]]
 for i,label in enumerate(LABELS):
  center=140+i*180
  for j,vals in enumerate(series):
   h=vals[i]*65;xx=center-55+j*36;dr.rectangle((xx,565-h,xx+30,565),fill=colors[j]);dr.text((xx+7,537-h),str(vals[i]),font=F(18),fill=colors[j])
  dr.text((center-50,590),label,font=F(20),fill='#273c4d')
 for j,name in enumerate(['现有库存','K=2需求','K=3需求']):dr.rectangle((390+j*250,656,410+j*250,676),fill=colors[j]);dr.text((420+j*250,650),name,font=F(22),fill='#273c4d')
 im.save(a.out/'库存与需求对比.png')
 b2=s['results']['K2_baseline'];b3=s['results']['K3_baseline'];strict2=s['results']['K2_no_copy_renumber'];strict3=s['results']['K3_no_copy_renumber'];bal2=s['results']['K2_workload_first'];bal3=s['results']['K3_workload_first']
 tab='\n'.join('|'+row['scenario']+'|'+str(row['G'])+'|'+f"{row['S']:.6f}"+'|'+f"{row['CV']:.6f}"+'|'+' / '.join(str(row[t]) for t in s['resource_order'])+'|' for row in comp)
 grouptext='\n'.join(f"|{K}|{g['group']}|{'、'.join(g['sites'])}|{' / '.join(map(str,g['resources']))}|{g['work_s']:.6f}|{g['boxes']}|{g['mass_kg']:.3f}|{g['volume_m3']:.5f}|{g['transport_N']}/{g['relay_N']}|" for K in [2,3] for g in s['results'][f'K{K}_baseline']['groups'])
 report=f'''# 第四问：冻结调度下的分区与资源配置

本报告依次按变量假设、优化模型、确定性事件回放三个Skill完成。用于建模分析和复算，不是完整参赛论文；正式竞赛应遵守赛事规则。全部结果来自实际运行。

## 1. 结果及适用范围

基准允许组内同型号资源重新编号；跨组实际使用的中继架次复制完整任务。它们均为**工作假设，需要用户核验**，不是原题明确给出的编号或复制规则。保持第三问baseline所有物理任务及通信保障不变。

资源向量固定按：A运输机/B运输机/C运输机/A电池/B电池/C电池/中继机/中继能源组件。库存为4/2/2/6/4/4/2/6。

|K|组|服务区|配置向量|机体占用工作量s|箱数|质量kg|体积m³|运输/中继任务数|
|---|---|---|---|---:|---:|---:|---:|---|
{grouptext}

两组基准需求为4/2/3/6/4/5/2/2，缺1架C型运输机、1组C型电池；三组基准为4/2/3/6/4/4/4/4，缺1架C型运输机、2架中继机。所有分区均存在至少一类库存缺口（完整枚举统计库存可行分区数量均为0）。这是固定方案和所采用口径下的结果，不意味着改变第三问调度后仍必然短缺。

未分区重新计算的最小配置为 {'/'.join(map(str,s['pooled_minimum']))}，而继承原编号为 {'/'.join(map(str,s['pooled_inherited']))}。中继组件最少只需2组：原R002组件充满后可承接R003；第三问实际使用3个不同组件编号并不是最小需求证明。

两组比未分区最小配置增加1架C型机、1组C电池，没有复制中继任务。三组增加1架C型机、2架中继机、2组中继组件；组件需求4低于库存6，故新增组件配置不是采购缺口。三组把R001、R003各多执行一个完整副本，中继总任务数5，比原3次多2次，能耗增加{b3['extra_relay_E']:.9f}kWh，中继机体占用增加{b3['extra_relay_body_work_s']:.6f}s，组件占用增加{b3['extra_relay_energy_occupied_s']:.6f}s。

80箱及所有医疗/首批时限保持不变，D=0；复制不改变最晚返航时刻7295.419514905454s。总运输能耗保持72.49952244069097kWh；两组总能耗75.86982913821295kWh，三组总能耗{75.86982913821295+b3['extra_relay_E']:.9f}kWh。

## 2. 原文、冻结数据与假设

原文要求15个服务区分为2或3个非空组，每区唯一归属；同运输架次访问的服务区同组；任务与保障关系不变，各组资源不得跨组调配。原文没有明确跨组中继复制机制，也没有明定是否必须沿用原实体编号。没有添加地理连通、等数量或行政边界约束。

冻结文件及原附件哈希见freeze_manifest.json。原题相关段落见source_rule_extract.txt。与第三问核验的9个原始文件一致，执行前后所有冻结文件哈希保持不变。既有表格、轨迹、通信区间均读取，不只依据报告汇总值。

工作假设：组内重新编号只改变承接资源，不改变机型、载货、航线、位置、时刻、能耗、SOC及链路对应。一个原中继架次在同组只复制一次；若涉及多个组则每组独占完整副本。每份副本保留准备、转场、建链、服务、返航与周转，不按实际保障片段裁剪。副本仅为本组提供通信。记录原ID—组ID—副本ID—实体编号。

运输机占用[准备,返航)，电池占用[准备,充满)；中继机占用[准备,返航+300s)，中继组件占用[准备,充满)。返航后能源立即充电，可与中继机体周转并行；无额外充电器或准备工位限制。所有能源初始满电，不同机型电池不兼容。这些沿用第三问需要用户核验的时间解释。

能耗与充电沿用授权公式，独立程序从原始设备表重算。运输每段E=Eu·d/L(q)+(m0+q)gh/(η·3.6×10⁶)，L(q)=L0−(L0−Lf)(q/Q)^(3/2)。中继水平功率×时间、爬升势能、建链及悬停通信分别计入。未加入缺乏功率参数的运输交接悬停能耗。两阶段充电保留90%分界、65%/35%总充电时间比例。能量标定与效率解释仍是工作假设，需要用户核验。

## 3. 数学模型和最小资源证明

运输必须同组关系合并为14块：S011、S012构成一块，其余单独成块。不是按照地理聚类强制分区。

|符号|类型|含义|单位/来源|
|---|---|---|---|
|z_bg|二元决策|不可拆分块b归属g|每块Σ_g z_bg=1，每组至少1块|
|a_j,b_j|固定参数|资源任务区间的起止|s；第三问时刻及原参数复算|
|H_r|固定集合|原中继r实际保障的运输架次|冻结通信表，不按地理可覆盖范围猜测|
|c_rg|二元推导量|组g是否需要中继r的完整副本|组内存在H_r任务则为1|
|n_gt|整数输出/配置|组g对类型t的最少资源|架或组；最大重叠及构造证明|
|u_j|资源分配决策|任务j由哪个组内实体承接|同型号，组间不共享|
|R_t,I_t,Δ_t,U_t|指标/参数|总需求、库存、缺口、剩余|Δ=max(0,R−I)，U=max(0,I−R)|
|W_g|工作量|运输+中继机体区间时长之和|s；包括中继周转，不包括能源充电|
|G,S,CV|目标|归一化缺口、规模、工作量变异系数|无量纲；建模选择|

对固定分组，同类型机体或能源组件都是可互换区间资源。任意时刻同时占用n个任务，至少需要n个实体；按开始时间排序，将已释放的最早实体复用，区间着色恰好用到最大重叠数。因此峰值是下界，具体编号分配达到下界，即该分组的最小资源配置。能源区间延伸至满电，已包含复用充电限制。初始资源都在O01且满电，所有架次回到O01，无额外空间衔接条件。

半开区间使用未舍入文件值，严格同刻释放优先；未发现正值小于1e−7s的潜在边界冲突，没有靠舍入减少峰值。容差用于独立数值复算：时间1e−7s、能量1e−8kWh、SOC1e−10、质量1e−9kg、体积1e−12m³。

基准字典序为G→S→CV，其中G=Σ_t Δ_t/I_t，S=Σ_t R_t/I_t；八类型等权归一化，不能解释成采购成本。库存分母均为2/4/6，以12倍目标转为整数精确比较前两层。CV=√(KΣW_g²/(ΣW_g)²−1)，以双精度计算，CV²并列判断容差1e−12。并列按规范无标签枚举顺序取首个；两基准在该容差下各1个最优分区。

## 4. 枚举、独立证据与最优性范围

固定14块，K=2无标签非空分区为S(14,2)=8191个；K=3为S(14,3)=788970个，全部评估，无候选截断，无随机搜索，无时间提前终止。缓存16383个非空子集的八类资源需求和工作量；运输和中继完整副本按任务去重计算。

优化器通过子集枚举分区、堆式区间着色求资源数；独立检查器不导入优化器，另用受限增长分组递归枚举、时间占用矩阵计算所有子集峰值。10个目标/编号组合的最优目标及枚举数量完全一致。主模型求解{ s['total_seconds']:.3f}s，独立原参复算、16个方案事件回放及二次枚举{v['elapsed_s']:.3f}s。两种枚举算法和区间计算实现独立，但都以同一个冻结第三问基准为条件。

因此可声称**在冻结第三问方案、所选中继复制与编号解释、目标优先级及数值容差下，分区取得完整枚举最优**。不能推广为原始四问联合调度全局最优；第三问自身未证明全局最优，连续通信也未严格认证。

## 5. 替代口径与均衡权衡

|方案|G|S|CV|资源向量|
|---|---:|---:|---:|---|
{tab}

把G→S→CV改成G→CV→S，两种K均得到相同方案。但这不表示均衡没有代价：基准CV分别为{b2['CV']:.6f}、{b3['CV']:.6f}，资源优先导致明显大组/小组。额外采用CV→G→S时，两组CV可降至{bal2['CV']:.9f}，但G升至{bal2['G']:.6f}；三组CV可降至{bal3['CV']:.9f}，G升至{bal3['G']:.6f}。不应把资源最省方案称为全面最好。

禁止复制中继时，严格绑定为：{{S001}}、{{S006}}、其余13个服务区。实际保障链使后者连通，细节见binding_blocks.json。K=2仍有3个无标签合法分区，K=3仅1个；两者不是“无分区解”。两组最优与基准一致；三组需求为{'/'.join(map(str,strict3['total_resources']))}，G={strict3['G']:.6f}，不复制中继却增加运输与电池配置压力。

继承编号时每组独立持有所用原编号的别名副本，跨组同原ID不能共享。既报告同一基准分区下继承原编号的需求，也重新枚举继承编号条件下的最优分区，二者不能混比后归因为重新编号的收益。所有替代方案另存，不替换基准模板。

## 6. 缺口、冗余与关键时段

库存剩余、分区额外配置、中继任务重复是三种不同指标。各场景resource_comparison.csv逐类型列出，不抵消不同类型缺口。基准两组的中继组件剩余4组，三组剩余2组；这不是可以替代C电池或中继机的通用容量。

K=2：G1仅S001，需要C机1架、C电池2组。G1在1907.4897939943457s的P001补电与P011任务区间重叠，需要2组C电池。G2的C机在1560.1589324932272s由P002/P009同时占用，至少2架；其C电池在3533.648726487573s由P002/P009/P014占用，至少3组。两组峰值即使错峰，也因禁止跨组借用而需1+2=3架C机、2+3=5组C电池。

K=3：三个组分别至少1架C机，故总需求3高于库存2。G1保有R003副本1架中继，G3保有R001副本1架，G2在143.18872744071507s原R001/R002同时占用需2架；总独立保有需求4高于库存2。不同组峰值不必同刻发生，不能把全局同时占用数替代分组独立配置。详细任务/时刻证据见peak_evidence.csv。

峰值表也包含所有其他类型；energy_cycles.csv记录逐资源准备预留、返航SOC、补电和恢复满电。events.csv为配置事件，independent_event_replay.csv为独立机体/能源占用状态回放。

## 7. 验证结论与通信限制

16个导出方案均通过独立检查：15区唯一归属、每组非空、运输同架次绑定、80箱不变、16箱医疗和30箱首批硬时限全满足，最小硬时限余量{v['hard_min_slack_s']:.6f}s；原任务对象所有字段完全一致，249条通信保障区间保持原运输架次、时刻和保障源，仅增加组及副本映射。设备和能源无跨组编号，区间无重叠，复用前满电，配置与峰值一致。

库存不足的方案是在“提供所列缺口资源后”的独立执行配置，不能声称现有库存足够。验证资源分配可行不等于库存可行。

通信仅继承第三问“在所述时空分辨率下未发现中断”，未新增连续通信证明。相同中继副本位置、时刻和运输轨迹使原链路几何预算可复用；并未证明真实网络并发容量、共址副本干扰隔离或实体空域运行条件。能源标定、未计运输交接悬停耗电等假设继续适用，均需要用户核验。

## 8. 成果和复算

Q4_分区配置.csv为主模板（共5行），只包含两种基准，不混入替代方案。K2_baseline、K3_baseline目录含完整组别、冻结任务副本、设备分配、组件SOC、通信继承、资源对比、峰值证据及地图/占用图。其他目录名称明确编号和目标口径。全部方案指标对比.csv、各组工作量与任务统计.csv汇总比较。

代码为solve_q4.py、verify_q4.py、report_q4.py。仅依赖numpy、openpyxl、Pillow，随机种子不适用；无商用求解器。详见README_复算.md。原始输入与第三问不写入；快照字段保存于各方案tasks.json，哈希见freeze_manifest.json。
'''
 (a.out/'模型与结果说明.md').write_text(report,encoding='utf-8')
 versions={k:importlib.metadata.version(k) for k in ['numpy','openpyxl','Pillow']};(a.out/'requirements.txt').write_text('\n'.join(k+'=='+val for k,val in versions.items())+'\n',encoding='utf-8')
 readme='''# 复算命令

在原工作区根目录执行，使用已装requirements.txt依赖的Python。输入路径作为外部依赖保留；不要把输出目录指向原始附件或q3。无随机过程，无随机种子，无搜索时间截断；完整枚举所有合法分区。Windows图形字体使用微软雅黑。

```powershell
$src = 'D:\\研一\\比赛\\中文题目\\D题'
$pre = 'outputs/preflight'
$q3 = 'outputs/q3'
$out = 'outputs/q4'
python $out/solve_q4.py --source $src --pre $pre --q3 $q3 --out $out
python $out/verify_q4.py --source $src --pre $pre --q3 $q3 --out $out
python $out/report_q4.py --pre $pre --out $out
```

只验证已导出方案时执行第二条。程序抛出断言则不可报告通过，需定位程序/数据问题，不能改动冻结任务或放宽约束。

主模板Q4_分区配置.csv含K=2、K=3基准5行。原始机体和组件ID保存在frozen任务内；实际分组承接编号见tasks.json顶层unit/energy_component与resource_assignment.csv。两者不同是允许重新编号口径，非任务改变。

编号类型顺序：A/B/C运输机、A/B/C电池、中继机、中继能源组件。CV为包含中继周转的机体占用工作量变异系数。G和S不是货币成本。
'''
 (a.out/'README_复算.md').write_text(readme,encoding='utf-8')
 (a.out/'独立验证报告.md').write_text(f'''# 独立验证报告

全部16个方案通过。程序不导入优化器，重新读取原始货箱、运输与中继参数，重算载荷、交付、能耗、SOC、充电和周转，并检查冻结对象字段完全一致、模板字段与值一致、249条通信关系完整继承。80箱无重复遗漏；医疗16箱、首批30箱硬时限全满足，最小余量{v['hard_min_slack_s']:.9f}s。

按组内实体编号确定性事件回放，释放先于同刻预留，无跨组共享、无重叠、能源复用前满电。独立最大重叠计算等于重新编号方案资源数量；继承编号方案等于不同原编号数量。所有冻结输入的SHA-256执行前后一致。

用另一种受限增长分组枚举和时间占用矩阵独立核验最优性，完整检查8191个两组分区和788970个三组分区，10种目标/编号组合的目标全部一致。详见verification.json。16场景的独立事件回放见各目录independent_event_replay.csv。

运行{v['elapsed_s']:.3f}s；无随机性、不计算蒙特卡洛均值或置信区间。容差：时间1e−7s、能量1e−8kWh、SOC1e−10、质量1e−9kg、体积1e−12m³、目标CV²1e−12。区间用未舍入值和半开规则，不因展示舍入改变可行性。

库存约束未被偷偷放宽：配置方案明确报告需补资源。检查通过指所列配置下可承接冻结任务，不表示现有库存能执行。通信仍仅继承第三问数值检查结论，未证明任意连续时刻可用；复制后的真实干扰、容量与空域运行条件需要用户核验。
''',encoding='utf-8')
 index='''# 第四问成果索引

- [模型与结果说明](模型与结果说明.md)
- [主提交模板：2组与3组](Q4_分区配置.csv)
- [全部口径和目标对比](全部方案指标对比.csv)
- [各组工作量和任务统计](各组工作量与任务统计.csv)
- [独立验证报告](独立验证报告.md)、[机器可读检查及最优性证据](verification.json)
- [运输及中继绑定关系](binding_blocks.json)、[冻结输入哈希](freeze_manifest.json)
- [库存与需求对比图](库存与需求对比.png)
- [K=2分区图](K2_baseline/分区地图.png)、[资源占用](K2_baseline/各组资源占用图.png)
- [K=3分区图](K3_baseline/分区地图.png)、[资源占用](K3_baseline/各组资源占用图.png)
- [依赖与复算命令](README_复算.md)

每个场景目录包含groups.json、tasks.json、resource_assignment.csv、relay_copy_mapping.csv、communication_inheritance.csv、resource_comparison.csv、peak_evidence.csv、energy_cycles.csv、events.csv和independent_event_replay.csv。
'''
 (a.out/'成果索引.md').write_text(index,encoding='utf-8')
 manifest={str(p.relative_to(a.out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in a.out.rglob('*') if p.is_file() and p.suffix not in ['.zip','.pyc'] and p.name!='artifact_manifest.json'};(a.out/'artifact_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 with zipfile.ZipFile(a.out/'Q4_成果与代码.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in a.out.rglob('*'):
   if p.is_file() and p.suffix not in ['.zip','.pyc'] and '__pycache__' not in p.parts:z.write(p,p.relative_to(a.out))
 print('Reports, charts and package generated',len(s['results']))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--pre',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);main(ap.parse_args())
