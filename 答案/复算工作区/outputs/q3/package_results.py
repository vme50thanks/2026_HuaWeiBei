from pathlib import Path
import json,csv,zipfile,hashlib
from openpyxl import load_workbook

root=Path(__file__).resolve().parent
read=lambda p:list(csv.DictReader(p.open(encoding='utf-8-sig',newline='')))
load=lambda p:json.loads(p.read_text(encoding='utf-8'))
s=load(root/'summary.json');v=load(root/'verification.json');j=load(root/'joint_verification.json')
src=Path(load(root/'source_consistency.json')['sources'][0]['path']).parent
while not list(src.rglob('结果提交模板.xlsx')):src=src.parent
wb=load_workbook(next(src.rglob('结果提交模板.xlsx')),data_only=True)
audit={}
for name in ['baseline','makespan_first']:
 d=root/name;plan=load(d/'plan.json');rp={x['sortie']:x for x in load(d/'relay_plan.json')};coverage=read(d/'Q3_通信保障.csv')
 for sheet in ['Q2_运输架次','Q2_逐箱交付','Q3_中继架次','Q3_通信保障']:
  rows=read(d/(sheet+'.csv'));assert list(rows[0])==[x for x in list(wb[sheet].values)[0] if x],sheet
 assert len(read(d/'Q2_逐箱交付.csv'))==80
 for p in plan:
  rows=sorted([x for x in coverage if x['运输架次编号']==p['sortie']],key=lambda x:float(x['开始时刻（s）']))
  assert abs(float(rows[0]['开始时刻（s）'])-p['takeoff'])<1e-7
  assert abs(float(rows[-1]['结束时刻（s）'])-p['finish'])<1e-7
  assert all(abs(float(x['结束时刻（s）'])-float(y['开始时刻（s）']))<1e-7 for x,y in zip(rows,rows[1:]))
 for x in coverage:
  assert float(x['结束时刻（s）'])>=float(x['开始时刻（s）'])-1e-7
  if x['保障方式']=='中继':
   r=rp[x['中继架次编号']];assert float(x['开始时刻（s）'])>=r['service_start']-1e-7 and float(x['结束时刻（s）'])<=r['service_end']+1e-7
 assert v[name]['status']=='PASS' and all(x['failed_points']==0 for x in j[name]['scans'])
 audit[name]=dict(template_fields_match=True,coverage_has_no_time_gaps_or_overlaps=True,coverage_within_relay_service=True,template_coverage_intervals=len(coverage))
(root/'export_check.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
text='''# 第三问成果索引

建议先读 [模型与结果说明](模型与结果说明.md) 和 [独立检查说明](独立检查报告.md)。这是数值验证方案，未证明连续通信或全局最优。

|成果|文件|
|---|---|
|运输架次模板|[基准运输架次](baseline/Q2_运输架次.csv)|
|80箱交付模板|[基准逐箱交付](baseline/Q2_逐箱交付.csv)|
|中继架次模板|[基准中继架次](baseline/Q3_中继架次.csv)|
|通信保障模板|[基准通信保障](baseline/Q3_通信保障.csv)|
|第四问关联|[关联表](baseline/q4_associations.csv)|
|逐段三维轨迹|[轨迹段](baseline/trajectory_segments.csv)|
|逐航段运输能耗|[运输能量分解](baseline/transport_energy_detail.csv)|
|中继能耗|[中继能量分解](baseline/relay_energy_check.csv)|
|运输设备/电池状态|[资源占用](baseline/resource_usage.csv)、[独立事件回放](baseline/event_replay.csv)|
|中继设备/能源状态|[资源占用](baseline/relay_resources.csv)、[独立事件回放](baseline/relay_event_replay.csv)|
|通信明细|[链路采样](baseline/communication_samples.csv)、[切换括区](baseline/switch_brackets.csv)|
|尚未严格认证区间|[全部运输阶段](baseline/uncertified_continuous_intervals.csv)|
|目标对比|[优先级比较](目标优先级对比.csv)|
|空间搜索对比|[空间候选比较](空间候选范围对比.csv)|
|扩大联合搜索|[完整日志](joint_search_log.json)、[范围比较](联合搜索范围对比.json)|
|直连盲点/候选点|[5秒诊断](q2_direct_diagnosis_5s.csv)、[候选及回传裕量](ridge_search/relay_candidates.json)|
|图示|[部署图](baseline/部署图.png)、[联合甘特图](baseline/联合甘特图.png)、[通信时间图](baseline/通信状态时间图.png)|
|代码与复算|[README](README_复算.md)、[依赖](requirements.txt)|

替代优先级完整成果位于 `makespan_first/`，与基准同名文件结构一致。
'''
(root/'成果索引.md').write_text(text,encoding='utf-8')
vr='''# 独立检查报告

`verify_joint.py`不导入联合优化器或其通信判定函数。其运输部分调用随包保存的独立 `support/verify_q2.py`，重新读取原始货箱、设备、截止时间，以40位Decimal重新计算时刻和能量，再按时间回放资源状态。中继部分另写地形射线、功率积分、爬升能耗、SOC、组件充电和机体周转检查。

以下统计来自实际运行，不代表物理网络或连续时间的严格认证。

'''
for name in ['baseline','makespan_first']:
 r=v[name];z=j[name];vr+=f"## {name}\n\n80箱检查通过，无遗漏/重复/错投。医疗{r['medical_boxes']}箱与首批{r['first_batch_boxes']}箱全部满足硬时限，最小余量{r['hard_deadline_min_slack_s']:.6f}秒。容量、SOC、机体、电池、组件与复用充电检查通过。运输能耗最大重算误差{r['max_energy_recompute_error_kWh']:.3g}kWh。中继2架、3组件、3架次，逐架回放见CSV。\n\n|时间步长|空间检查|检查点数|失败点数|最小所选链路裕量dB|\n|---|---|---:|---:|---:|\n"
 for x in z['scans']:vr+=f"|{x['dt_s']}s|{x['spatial_spacing_m']}|{x['points']}|{x['failed_points']}|{x['worst']['margin_db']:.9f}|\n"
 vr+='\n最后一行对低于0.02 dB的裕量区间或保障源切换区间追加不超过0.05秒的检查，并对切换点作1e−7秒二分括区。全穿越像元检查包含边和角，不仅看射线少量点。\n\n'
vr+='''准确结论：**在所述时空分辨率下未发现中断**。所有193个运输阶段均保守列入连续时间尚未严格认证区间。失败点数0不等于已证明中断时长0；离散采样间隙可能存在未定位的短暂遮挡变化。低于毫米尺度的地图定位误差、额外运输悬停功耗和真实网络并发容量均未由本程序认证。

容差：时间1e−7 s、质量1e−9 kg、体积1e−12 m³、能耗1e−8 kWh、SOC1e−10、链路1e−9 dB。以未四舍五入数据判断。原始表与DEM不同高程保持，不自动消除遮挡。中继水平转场满足最高DEM+50米条件，端点采用题给/工作假设的垂直起降剖面。

`export_check.json`另检查4张模板有效字段完全一致、保障表时间区间无间隙/重叠且中继保障不超出有效服务期。`source_consistency.json`保存原始文件未变化的SHA-256证据。
'''
(root/'独立检查报告.md').write_text(vr,encoding='utf-8')
files=[p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.zip','.pyc'] and p.name!='covering_triples.json']
manifest={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.name!='artifact_manifest.json'}
(root/'artifact_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
with zipfile.ZipFile(root/'Q3_成果与代码.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in files:z.write(p,p.relative_to(root))
 if root/'artifact_manifest.json' not in files:z.write(root/'artifact_manifest.json','artifact_manifest.json')
print(json.dumps(dict(export_check=audit,files=len(files),zip_bytes=(root/'Q3_成果与代码.zip').stat().st_size),ensure_ascii=False))
