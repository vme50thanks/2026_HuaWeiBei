"""Independent raw-input recomputation, event replay and exhaustive certificate check."""
from pathlib import Path
from collections import Counter,defaultdict
import json,csv,hashlib,math,argparse,time
import numpy as np
from openpyxl import load_workbook
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,x):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(x[0]));w.writeheader();w.writerows(x)
def eq(a,b,tol=1e-7):assert abs(float(a)-float(b))<=tol,(a,b)
def charge(full,s):return full*(.65*(.9-s)/.9+.35) if s<.9 else full*.35*(1-s)/.1
def main(a):
 t0=time.perf_counter();s=load(a.out/'summary.json');freeze=load(a.out/'freeze_manifest.json')
 for x in freeze:assert hashlib.sha256(Path(x['path']).read_bytes()).hexdigest()==x['sha256'],x['path']
 p=load(a.q3/'baseline/plan.json');r=load(a.q3/'baseline/relay_plan.json');ps={x['sortie']:x for x in p};rs={x['sortie']:x for x in r};comm=read(a.q3/'baseline/Q3_通信保障.csv');original=ps|rs
 find=lambda n:next(a.source.rglob(n));raw=list(load_workbook(find('运输无人机数据.xlsx'),data_only=True).active.values);models={x[0]:x for x in raw[2:5]};full={x[0]:x[2] for x in raw[19:22]};rr=list(load_workbook(find('中继无人机数据.xlsx'),data_only=True).active.values);rm=rr[2]
 boxes={x[0]:x for x in list(load_workbook(find('物资需求与配送时限.xlsx'),data_only=True)['逐箱货箱清单'].values)[1:] if x[0]};legs={(x['from_id'],x['to_id']):x for x in read(a.pre/'legs.csv')};nodes={x['node_id']:x for x in read(a.pre/'nodes.csv')};seen=Counter();hard=[];delay=0.;transport_energy=0.;releases={};source_rows=[]
 for x in p:
  m=models[x['model']];bs=[boxes[b] for b in x['boxes']];seen.update(x['boxes']);q=sum(b[3] for b in bs);vol=sum(b[4] for b in bs);assert q<=m[3]+1e-9 and vol<=m[4]+1e-12;assert set(x['route'])=={b[1] for b in bs};t=x['start']+m[10]+len(bs)*m[11];eq(t,x['takeoff']);E=0
  for k,l in enumerate(x['legs']):
   data=legs[l['from_id'],l['to_id']];eq(q,l['payload']);eq(t,l['start']);L=m[6]-(m[6]-m[7])*(q/m[3])**1.5;en=m[8]*float(data['horizontal_distance_m'])/L+(m[2]+q)*9.80665*float(data['climb_m'])/(m[16]*3600000);eq(en,l['energy'],1e-8);E+=en
   t+=float(data['climb_m'])/m[14]+float(data['horizontal_distance_m'])/m[5]+float(data['descent_m'])/m[15];eq(t,l['end'])
   if l['to_id']!='O01':
    here=[b for b in bs if b[1]==l['to_id']];t+=m[12]+m[13]*len(here)
    for b in here:
     eq(t,x['deliveries'][b[0]])
     if b[2]=='医疗物资':hard.append(b[7]-t)
     if b[5]=='是':hard.append(b[6]-t)
     if b[7] is not None:delay+=b[8]*max(0,t-b[7])
    q-=sum(b[3] for b in here)
  eq(q,0,1e-9);eq(t,x['finish']);eq(E,x['energy'],1e-8);soc=1-E/m[8];assert soc>=m[9]/100-1e-10;eq(soc,x['soc'],1e-10);ready=t+charge(full[x['model']],soc);eq(ready,x['battery_ready']);releases[x['sortie']]=(x['finish'],x['battery_ready']);transport_energy+=E
 assert set(seen)==set(boxes) and all(v==1 for v in seen.values()) and min(hard)>=-1e-7
 for x in r:
  ground=float(nodes['O01']['operation_alt_m']);H=x['cruise'];z=x['position'][2];dist=math.hypot(x['position'][0]-float(nodes['O01']['x_local_m']),x['position'][1]-float(nodes['O01']['y_local_m']));up=H-ground;down=H-z
  fly=up/rm[12]+dist/rm[5]+down/rm[13];back=down/rm[12]+dist/rm[5]+up/rm[13];eq(x['start']+rm[9],x['takeoff']);eq(x['takeoff']+fly,x['arrival']);eq(x['arrival']+rm[10],x['service_start']);eq(x['service_end']+back,x['finish']);eq(x['finish']+rm[11],x['body_ready'])
  E=2*rm[6]*dist/rm[5]/3600+rm[4]*9.80665*(up+down)/(rm[14]*3600000)+(rm[16]+rm[17])*(rm[10]+x['service_end']-x['service_start'])/3600;eq(E,x['energy'],1e-8);soc=1-E/rm[7];eq(soc,x['soc'],1e-10);assert soc>=rm[8]/100-1e-10;eq(x['finish']+charge(rr[11][2],soc),x['component_ready']);releases[x['sortie']]=(x['body_ready'],x['component_ready'])
 inventory=[sum(x[1]==g for x in raw[8:16]) for g in 'ABC']+[x[1] for x in raw[19:22]]+[len(rr[6:8]),rr[11][1]];assert inventory==s['inventory'];types=s['resource_order'];report={}
 for name,result in s['results'].items():
  d=a.out/name;groups=load(d/'groups.json');tasks=load(d/'tasks.json');alloc=read(d/'resource_assignment.csv');coverage=read(d/'communication_inheritance.csv');all_sites=[v for g in groups for v in g['sites']];assert sorted(all_sites)==sorted(nodes.keys()-{'O01'}) and len(all_sites)==15 and all(g['sites'] for g in groups);groupof={site:g['group'] for g in groups for site in g['sites']}
  for x in p:assert len({groupof[site] for site in x['route']})==1
  expected_relay={(groupof[ps[x['运输架次编号']]['route'][0]],x['中继架次编号']) for x in comm if x['中继架次编号'] and float(x['结束时刻（s）'])>float(x['开始时刻（s）'])}
  assert {(x['group'],x['original_task']) for x in tasks if x['kind']=='relay'}==expected_relay
  assert len([x for x in tasks if x['kind']=='transport'])==len(p) and len(tasks)==len(p)+len(expected_relay)
  assert len({(x['group'],x['original_task']) for x in tasks})==len(tasks)
  for x in tasks:
   assert x['frozen']==original[x['original_task']]
   if x['kind']=='transport':assert x['group']==groupof[x['frozen']['route'][0]]
  expected_alloc=set()
  for x in tasks:
   g=x['frozen']['model'] if x['kind']=='transport' else 'R'
   for typ,rid in [(g+'_drone',x['unit']),('R_energy' if g=='R' else g+'_battery',x['energy_component'])]:expected_alloc.add((x['group'],x['original_task'],typ,rid))
  assert len(alloc)==len(expected_alloc) and {(x['group'],x['task'],x['type'],x['resource']) for x in alloc}==expected_alloc
  template=read(d/'Q4_分区配置.csv');headers=[h for h in list(load_workbook(find('结果提交模板.xlsx'),data_only=True)['Q4_分区配置'].values)[0] if h];assert list(template[0])==headers
  for row,g in zip(template,groups):
   assert int(row[headers[0]])==len(groups) and row[headers[1]]==g['group'] and row[headers[2]].split(';')==g['sites'];assert [int(row[h]) for h in headers[3:]]==g['resources']
  assert len(coverage)==len(comm)
  sortkey=lambda x:(x['运输架次编号'],float(x['开始时刻（s）']))
  for x,y in zip(sorted(coverage,key=sortkey),sorted(comm,key=sortkey)):
   assert all(x[k]==v for k,v in y.items());assert x['group']==groupof[ps[y['运输架次编号']]['route'][0]]
   assert x['relay_copy']==(x['group']+'-'+y['中继架次编号'] if y['中继架次编号'] else '')
  owner={};ev=[];peaks=[]
  for x in alloc:
   src=original[x['task']];idx=0 if x['type'].endswith('drone') else 1;eq(x['start'],src['start']);eq(x['end'],releases[x['task']][idx]);assert x['resource'] not in owner or owner[x['resource']]==x['group'];owner[x['resource']]=x['group'];ev += [(float(x['start']),1,x),(float(x['end']),0,x)]
  state={};trace=[]
  for t,kind,x in sorted(ev,key=lambda e:(e[0],e[1],e[2]['resource'])):
   rid=x['resource']
   if kind:assert rid not in state;(state.update({rid:x['task']}))
   else:assert state.pop(rid)==x['task']
   trace.append(dict(time_s=t,event='RESERVE' if kind else 'READY',resource=rid,group=x['group'],task=x['task'],occupied_resources=len(state)))
  assert not state;write(d/'independent_event_replay.csv',trace)
  W=[];tot=np.zeros(8,dtype=int)
  for g in groups:
   ww=0.
   for i,typ in enumerate(types):
    seq=[x for x in alloc if x['group']==g['group'] and x['type']==typ];peak=max([sum(float(x['start'])<=float(t['start'])<float(x['end']) for x in seq) for t in seq],default=0);assigned=len({x['resource'] for x in seq});assert assigned==g['resources'][i];tot[i]+=assigned
    if result['mode']=='renumber':assert peak==assigned
    else:assert assigned==len({x['original_resource'] for x in seq})
    if typ.endswith('drone'):ww+=math.fsum(float(x['end'])-float(x['start']) for x in seq)
   eq(ww,g['work_s']);W.append(ww)
  assert tot.tolist()==result['total_resources'];G=sum(max(0,int(x)-cap)/cap for x,cap in zip(tot,inventory));S=sum(int(x)/cap for x,cap in zip(tot,inventory));cv=math.sqrt(max(0,len(W)*sum(w*w for w in W)/sum(W)**2-1));eq(G,result['G']);eq(S,result['S']);eq(cv,result['CV'],1e-8)
  if 'no_copy' in name:assert len(expected_relay)==len(r)
  report[name]=dict(status='PASS',groups=len(groups),boxes=80,transport_tasks=len(p),relay_copies=len(expected_relay),resources=tot.tolist(),G=G,S=S,CV=cv,events=len(trace),frozen_task_fields_equal=True,communication_inherited=True)
 # Independent all-subset resource peak certificate using occupancy matrices.
 blocks=load(a.out/'binding_blocks.json')['transport_blocks'];n=len(blocks);fullmask=(1<<n)-1;sitebit={site:1<<i for i,b in enumerate(blocks) for site in b};r_masks={rid:0 for rid in rs}
 for c in comm:
  if c['中继架次编号']:
   for site in ps[c['运输架次编号']]['route']:r_masks[c['中继架次编号']]|=sitebit[site]
 rec=[]
 for x in p+r:
  relay=x['sortie'] in rs;mask=r_masks[x['sortie']] if relay else sitebit[x['route'][0]];g='R' if relay else x['model']
  for typ,end,oid in [(g+'_drone',releases[x['sortie']][0],x['unit']),(('R_energy' if relay else g+'_battery'),releases[x['sortie']][1],x['component'] if relay else x['battery'])]:rec.append(dict(type=typ,start=x['start'],end=end,mask=mask,oid=oid))
 masks=np.arange(fullmask+1);need=np.zeros((fullmask+1,8),dtype=np.int16);ids=need.copy();work=np.zeros(fullmask+1)
 for i,typ in enumerate(types):
  seq=[x for x in rec if x['type']==typ];inc=np.array([(masks & x['mask'])!=0 for x in seq],dtype=np.int16).T;overlap=np.array([[x['start']<=t['start']<x['end'] for t in seq] for x in seq],dtype=np.int16);need[:,i]=(inc@overlap).max(axis=1)
  for oid in {x['oid'] for x in seq}:ids[:,i]+=np.any(inc[:,[k for k,x in enumerate(seq) if x['oid']==oid]],axis=1)
  if typ.endswith('drone'):work+=inc@np.array([x['end']-x['start'] for x in seq])
 assert need[-1].tolist()==s['pooled_minimum'] and ids[-1].tolist()==s['pooled_inherited'];cert=[];weights=np.array([12//x for x in inventory])
 for K in [2,3]:
  parts=[]
  def visit(i,groups):
   if i==n:
    if len(groups)==K:parts.append(tuple(groups))
    return
   for j in range(len(groups)):
    gg=list(groups);gg[j]|=1<<i;visit(i+1,gg)
   if len(groups)<K:visit(i+1,groups+[1<<i])
  visit(0,[]);arr=np.array(parts);W=work[arr];cv2=K*(W*W).sum(axis=1)/(W.sum(axis=1)**2)-1
  for mode,counts in [('renumber',need),('inherited',ids)]:
   R=counts[arr].sum(axis=1);G=(np.maximum(0,R-inventory)*weights).sum(axis=1);S=(R*weights).sum(axis=1)
   for priority,order in [('baseline',(cv2,S,G)),('balance_first',(S,cv2,G))]+([('workload_first',(S,G,cv2))] if mode=='renumber' else []):
    ix=int(np.lexsort(order)[0]);key=f'K{K}_{priority}' if mode=='renumber' else f'K{K}_inherited_{priority}';target=s['results'][key];eq(G[ix]/12,target['G']);eq(S[ix]/12,target['S']);eq(cv2[ix],target['CV_squared'],1e-12);assert len(parts)==target['all_partitions'];cert.append(dict(scenario=key,partitions=len(parts),G_lower_bound=G[ix]/12,S_at_lex_optimum=S[ix]/12,CV_squared_at_lex_optimum=float(cv2[ix]),status='INDEPENDENT_ENUMERATION_MATCH'))
 for x in freeze:assert hashlib.sha256(Path(x['path']).read_bytes()).hexdigest()==x['sha256']
 final=dict(scenarios=report,optimality_certificate=cert,source_unchanged=True,boxes=80,medical_boxes=sum(x[2]=='医疗物资' for x in boxes.values()),first_batch_boxes=sum(x[5]=='是' for x in boxes.values()),hard_min_slack_s=min(hard),D=delay,transport_E=transport_energy,elapsed_s=time.perf_counter()-t0,tolerances=dict(time_s=1e-7,energy_kWh=1e-8,mass_kg=1e-9,volume_m3=1e-12,objective_CV_squared=1e-12),interval_rule='Exact unrounded exported endpoints; half-open intervals; release before reserve at exact ties',communication_claim='继承第三问在所述时空分辨率下未发现中断；未新增连续时间证明')
 (a.out/'verification.json').write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding='utf-8');print('PASS',len(report),'scenarios;',len(cert),'independent exhaustive certificates;',time.perf_counter()-t0,'seconds')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--pre',type=Path,required=True);ap.add_argument('--q3',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);main(ap.parse_args())
