from pathlib import Path
from collections import defaultdict,Counter
import json,csv,hashlib,time,argparse,heapq,math
import numpy as np
from openpyxl import load_workbook
from zipfile import ZipFile
from xml.etree import ElementTree as ET

TYPES=['A_drone','B_drone','C_drone','A_battery','B_battery','C_battery','R_drone','R_energy']
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,x):
 if not x:return
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(x[0]));w.writeheader();w.writerows(x)
def components(sites,edges):
 parent={s:s for s in sites}
 def find(x):
  while parent[x]!=x:x=parent[x]
  return x
 for edge in edges:
  for x in edge[1:]:parent[find(x)]=find(edge[0])
 groups=defaultdict(list)
 for s in sites:groups[find(s)].append(s)
 return sorted([sorted(v) for v in groups.values()])
def color(tasks,prefix):
 active=[];free=[];n=0;ans=[]
 for t in sorted(tasks,key=lambda x:(x['start'],x['end'],x['task'])):
  while active and active[0][0]<=t['start']:
   _,i=heapq.heappop(active);heapq.heappush(free,i)
  if free:i=heapq.heappop(free)
  else:n+=1;i=n
  heapq.heappush(active,(t['end'],i));ans.append(dict(t,resource=f'{prefix}-{i:02d}'))
 return n,ans

def main(a):
 t0=time.perf_counter();a.out.mkdir(parents=True,exist_ok=True);base=a.q3/'baseline'
 files=[p for p in base.iterdir() if p.is_file()]+[a.q3/n for n in ['模型与结果说明.md','独立检查报告.md','summary.json','source_consistency.json','verification.json','joint_verification.json','export_check.json']]+[a.pre/n for n in ['audit.json','nodes.csv','legs.csv','time_rules.json','flight_times.csv']]
 for x in load(a.q3/'source_consistency.json')['sources']:
  p=Path(x['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==x['original_sha256'];files.append(p)
 freeze=[dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files];dump(a.out/'freeze_manifest.json',freeze)
 source=next(p for p in a.source.glob('*.docx') if not p.name.startswith('~'))
 with ZipFile(source) as z:
  root=ET.fromstring(z.read('word/document.xml'));ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'};paras=[''.join(x.text or '' for x in p.findall('.//w:t',ns)) for p in root.findall('.//w:p',ns)]
 (a.out/'source_rule_extract.txt').write_text('\n'.join(p for p in paras if any(k in p for k in ['问题四','任务分区','跨组','充电','周转'])),encoding='utf-8')
 p=load(base/'plan.json');r=load(base/'relay_plan.json');comm=read(base/'Q3_通信保障.csv');assoc=read(base/'q4_associations.csv');assert len(comm)==len(assoc)
 for x,y in zip(comm,assoc):
  assert x['运输架次编号']==y['sortie'];assert abs(float(x['开始时刻（s）'])-float(y['start']))<1e-7;assert (x['中继架次编号'] or 'G01')==y['provider']
 byid={x['sortie']:x for x in p};sites=sorted({s for x in p for s in x['route']});assert len(sites)==15
 blocks=components(sites,[x['route'] for x in p]);n=len(blocks);sitebit={s:1<<i for i,b in enumerate(blocks) for s in b};relay_sites={x['sortie']:set() for x in r}
 for x in comm:
  if x['保障方式']=='中继' and float(x['结束时刻（s）'])>float(x['开始时刻（s）']):relay_sites[x['中继架次编号']].update(byid[x['运输架次编号']]['route'])
 rb={rid:sum(sitebit[s] for s in set()) for rid in relay_sites}
 for rid,ss in relay_sites.items():
  rb[rid]=0
  for s in ss:rb[rid]|=sitebit[s]
 strict=components(sites,[x['route'] for x in p]+[sorted(x) for x in relay_sites.values() if x]);dump(a.out/'binding_blocks.json',dict(transport_blocks=blocks,relay_bindings={k:sorted(v) for k,v in relay_sites.items()},no_relay_copy_blocks=strict))
 find=lambda name:next(a.source.rglob(name));rr=list(load_workbook(find('运输无人机数据.xlsx'),data_only=True).active.values);units=Counter(x[1] for x in rr[8:16]);stock=[units[g] for g in 'ABC']+[x[1] for x in rr[19:22]]
 relayrows=list(load_workbook(find('中继无人机数据.xlsx'),data_only=True).active.values);stock += [len([x for x in relayrows[6:8] if x[0]]),relayrows[11][1]];assert stock==[4,2,2,6,4,4,2,6]
 boxes={x[0]:x for x in list(load_workbook(find('物资需求与配送时限.xlsx'),data_only=True)['逐箱货箱清单'].values)[1:] if x[0]};template=[h for h in list(load_workbook(find('结果提交模板.xlsx'),data_only=True)['Q4_分区配置'].values)[0] if h]
 records=[]
 for x in p:
  bit=sitebit[x['route'][0]];assert all(sitebit[s]==bit for s in x['route'])
  for typ,end,orig in [(x['model']+'_drone',x['finish'],x['unit']),(x['model']+'_battery',x['battery_ready'],x['battery'])]:records.append(dict(type=typ,task=x['sortie'],start=x['start'],end=end,original_resource=orig,mask=bit))
 for x in r:
  for typ,end,orig in [('R_drone',x['body_ready'],x['unit']),('R_energy',x['component_ready'],x['component'])]:records.append(dict(type=typ,task=x['sortie'],start=x['start'],end=end,original_resource=orig,mask=rb[x['sortie']]))
 full=(1<<n)-1;need=np.zeros((full+1,8),dtype=np.int16);inherit=need.copy();work=np.zeros(full+1)
 for mask in range(1,full+1):
  rec=[x for x in records if x['mask']&mask]
  for k,typ in enumerate(TYPES):
   seq=[x for x in rec if x['type']==typ];need[mask,k]=color(seq,'X')[0];inherit[mask,k]=len({x['original_resource'] for x in seq})
  work[mask]=math.fsum(x['end']-x['start'] for x in rec if x['type'].endswith('drone'))
 np.savez_compressed(a.out/'subset_cache.npz',need=need,inherited=inherit,work=work);write(a.out/'input_intervals.csv',records)
 pooled=need[full].tolist();pooled_ids=inherit[full].tolist();weights=np.array([12//x for x in stock]);results={};alltemplate=[];logs=[]
 def export(key,masks,counts,metrics,mode):
  dest=a.out/key;dest.mkdir(exist_ok=True);alloc=[];groups=[];relaymap=[];coverage=[];tasks=[];peaks=[]
  for gi,mask in enumerate(masks):
   group=f'G{gi+1}';ss=[s for i,b in enumerate(blocks) if mask&(1<<i) for s in b];ps=[x for x in p if x['route'][0] in ss];rs=[x for x in r if rb[x['sortie']]&mask];seq=[x for x in records if x['mask']&mask]
   for typ in TYPES:
    selected=[x for x in seq if x['type']==typ];_,colored=color(selected,f'{group}-{typ}')
    if mode=='inherited':colored=[dict(x,resource=f'{group}-{typ}-{x["original_resource"]}') for x in selected]
    alloc += [dict(group=group,**x) for x in colored]
    # Exact half-open peak evidence, without rounded timestamps.
    best=[];bt=None
    for t in sorted({x['start'] for x in selected}):
     active=[x['task'] for x in selected if x['start']<=t<x['end']]
     if len(active)>len(best):best=active;bt=t
    peaks.append(dict(group=group,type=typ,peak=len(best),time_s=bt,tasks=';'.join(best)))
   amap={(x['task'],x['type']):x['resource'] for x in alloc if x['group']==group}
   for x in ps:tasks.append(dict(group=group,kind='transport',original_task=x['sortie'],copy_id=f'{group}-{x["sortie"]}',unit=amap[x['sortie'],x['model']+'_drone'],energy_component=amap[x['sortie'],x['model']+'_battery'],frozen=x))
   for x in rs:
    rel=dict(group=group,original_relay=x['sortie'],copy_id=f'{group}-{x["sortie"]}',unit=amap[x['sortie'],'R_drone'],component=amap[x['sortie'],'R_energy'],start=x['start'],service_start=x['service_start'],service_end=x['service_end'],finish=x['finish'],energy=x['energy']);relaymap.append(rel)
    tasks.append(dict(group=group,kind='relay',original_task=x['sortie'],copy_id=rel['copy_id'],unit=rel['unit'],energy_component=rel['component'],frozen=x))
   for x in comm:
    if byid[x['运输架次编号']]['route'][0] in ss:coverage.append(dict(group=group,relay_copy=f'{group}-{x["中继架次编号"]}' if x['中继架次编号'] else '',**x))
   bs=[b for x in ps for b in x['boxes']];gc=counts[mask].tolist();groups.append(dict(group=group,sites=ss,mask=int(mask),resources=gc,work_s=float(work[mask]),boxes=len(bs),mass_kg=sum(boxes[b][3] for b in bs),volume_m3=sum(boxes[b][4] for b in bs),transport_N=len(ps),relay_N=len(rs),transport_E=sum(x['energy'] for x in ps),relay_E=sum(x['energy'] for x in rs),relay_body_work_s=sum(x['body_ready']-x['start'] for x in rs),relay_energy_occupied_s=sum(x['component_ready']-x['start'] for x in rs)))
  rows=[dict(zip(template,[len(masks),g['group'],';'.join(g['sites']),*g['resources']])) for g in groups];write(dest/'Q4_分区配置.csv',rows)
  if key.endswith('baseline'):alltemplate.extend(rows)
  dump(dest/'groups.json',groups);dump(dest/'tasks.json',tasks);write(dest/'resource_assignment.csv',alloc);write(dest/'relay_copy_mapping.csv',relaymap);write(dest/'communication_inheritance.csv',coverage);write(dest/'peak_evidence.csv',peaks)
  total=np.sum([g['resources'] for g in groups],axis=0);pool=pooled if mode=='renumber' else pooled_ids
  resource=[dict(type=typ,demand=int(total[i]),stock=stock[i],gap=max(0,int(total[i])-stock[i]),unused=max(0,stock[i]-int(total[i])),pooled=pool[i],partition_extra=int(total[i])-pool[i]) for i,typ in enumerate(TYPES)];write(dest/'resource_comparison.csv',resource)
  events=[]
  for x in alloc:
   for t,kind in [(x['start'],'RESERVE'),(x['end'],'READY')]:events.append(dict(time_s=t,event=kind,group=x['group'],type=x['type'],resource=x['resource'],task=x['task']))
   if x['type'].endswith('battery') or x['type']=='R_energy':
    obj=byid.get(x['task']) or next(y for y in r if y['sortie']==x['task']);events.append(dict(time_s=obj['finish'],event='LAND_BEGIN_CHARGE',group=x['group'],type=x['type'],resource=x['resource'],task=x['task']))
  write(dest/'events.csv',sorted(events,key=lambda x:(x['time_s'],0 if x['event']=='READY' else 1,x['resource'])))
  results[key]=dict(K=len(masks),mode=mode,groups=groups,total_resources=total.tolist(),gap=[x['gap'] for x in resource],unused=[x['unused'] for x in resource],partition_extra=[x['partition_extra'] for x in resource],**metrics,extra_relay_N=sum(g['relay_N'] for g in groups)-len(r),extra_relay_E=sum(g['relay_E'] for g in groups)-sum(x['energy'] for x in r),extra_relay_body_work_s=sum(g['relay_body_work_s'] for g in groups)-sum(x['body_ready']-x['start'] for x in r),extra_relay_energy_occupied_s=sum(g['relay_energy_occupied_s'] for g in groups)-sum(x['component_ready']-x['start'] for x in r))
 for K in [2,3]:
  t=time.perf_counter();parts=[]
  for m1 in range(1,full,2):
   rem=full^m1
   if K==2:parts.append((m1,rem));continue
   low=rem&-rem;m2=(rem-1)&rem
   while m2:
    if m2&low:parts.append((m1,m2,rem^m2))
    m2=(m2-1)&rem
  arr=np.array(parts,dtype=np.int32);assert len(arr)==((2**(n-1)-1) if K==2 else (3**n-3*2**n+3)//6)
  W=work[arr];cv2=K*np.sum(W*W,axis=1)/np.sum(W,axis=1)**2-1
  for mode,counts in [('renumber',need),('inherited',inherit)]:
   R=counts[arr].sum(axis=1);G=(np.maximum(0,R-stock)*weights).sum(axis=1);S=(R*weights).sum(axis=1)
   for name,ordering in [('baseline',(cv2,S,G)),('balance_first',(S,cv2,G))]+([('workload_first',(S,G,cv2))] if mode=='renumber' else []):
    ix=int(np.lexsort(ordering)[0]);gv,sv,cv=int(G[ix]),int(S[ix]),float(cv2[ix]);ties=np.flatnonzero((G==gv)&(S==sv)&(abs(cv2-cv)<=1e-12));ix=int(ties[0]);masks=[int(x) for x in arr[ix]]
    key=f'K{K}_{name}' if mode=='renumber' else f'K{K}_inherited_{name}'
    export(key,masks,counts,dict(G=gv/12,S=sv/12,CV=math.sqrt(max(0,cv)),CV_squared=cv,tied_optima=len(ties),all_partitions=len(arr),min_gap_partitions=int((G==gv).sum()),inventory_feasible_partitions=int((G==0).sum()),status='EXHAUSTIVE_OPTIMUM_CONDITIONAL_ON_FROZEN_MODEL'),mode)
    print(key,results[key]['total_resources'],gv/12,sv/12,math.sqrt(max(0,cv)),flush=True)
  logs.append(dict(K=K,partitions=len(arr),seconds=time.perf_counter()-t))
  # Hold each main partition fixed when comparing original-ID inheritance.
  masks=[g['mask'] for g in results[f'K{K}_baseline']['groups']];tot=inherit[masks].sum(axis=0);ww=work[masks];cv=float(K*np.sum(ww*ww)/sum(ww)**2-1)
  export(f'K{K}_fixed_partition_inherited',masks,inherit,dict(G=float(sum(np.maximum(0,tot-stock)*weights)/12),S=float(sum(tot*weights)/12),CV=math.sqrt(max(0,cv)),status='FIXED_PARTITION_COMPARISON'), 'inherited')
  strictm=[]
  for block in strict:
   mask=0
   for site in block:mask|=sitebit[site]
   strictm.append(mask)
  sp=[]
  def strict_part(i,groups):
   if i==len(strictm):
    if len(groups)==K:sp.append(groups)
    return
   for g in range(len(groups)):
    gg=list(groups);gg[g]|=strictm[i];strict_part(i+1,gg)
   if len(groups)<K:strict_part(i+1,groups+[strictm[i]])
  strict_part(0,[])
  if sp:
   for mode,counts in [('renumber',need),('inherited',inherit)]:
    candidates=[]
    for masks in sp:
     total=counts[masks].sum(axis=0);ww=work[masks];cv=float(K*np.sum(ww*ww)/sum(ww)**2-1);gv=int(sum(np.maximum(0,total-stock)*weights));sv=int(sum(total*weights));candidates.append(((gv,sv,cv),masks))
    (gv,sv,cv),masks=min(candidates)
    export(f'K{K}_no_copy_{mode}',masks,counts,dict(G=gv/12,S=sv/12,CV=math.sqrt(max(0,cv)),all_partitions=len(sp),status='EXHAUSTIVE_OPTIMUM_NO_RELAY_COPY'),mode)
 write(a.out/'Q4_分区配置.csv',alltemplate[:2]+[x for x in alltemplate if x['K（2或3）']==3][:3])
 # Main template only contains renumber baseline, not the inherited-ID alternatives.
 write(a.out/'Q4_分区配置.csv',read(a.out/'K2_baseline/Q4_分区配置.csv')+read(a.out/'K3_baseline/Q4_分区配置.csv'))
 strict_count=len(strict);dump(a.out/'summary.json',dict(resource_order=TYPES,inventory=stock,pooled_minimum=pooled,pooled_inherited=pooled_ids,block_count=n,results=results,no_copy=dict(blocks=strict,K2_possible=strict_count>=2,K3_possible=strict_count>=3),search=logs,total_seconds=time.perf_counter()-t0,random_seed=None,complete_enumeration=True,objective_tolerance_cv_squared=1e-12))
 print('blocks',blocks,'no-copy',strict,'seconds',time.perf_counter()-t0,flush=True)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--pre',type=Path,required=True);ap.add_argument('--q3',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);main(ap.parse_args())
