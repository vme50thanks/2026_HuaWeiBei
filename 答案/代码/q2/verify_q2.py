"""Independent deterministic event replay; does not import the solver."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal,getcontext
import json,csv,argparse,math
from openpyxl import load_workbook
getcontext().prec=40
D=lambda x:Decimal(str(x))
def read(p):
 with p.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def write(p,rows):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def run(source,pre,out):
 find=lambda n:next(source.rglob(n))
 rr=list(load_workbook(find('运输无人机数据.xlsx'),data_only=True).active.values)
 models={r[0]:r for r in rr[2:5]};units={r[0]:r[1] for r in rr[8:16]}
 batteries={f'{r[0]}-BAT-{i+1:02d}':(r[0],r[2]) for r in rr[19:22] for i in range(r[1])}
 boxes={r[0]:r for r in list(load_workbook(find('物资需求与配送时限.xlsx'),data_only=True)['逐箱货箱清单'].values)[1:] if r[0]}
 legs={(r['from_id'],r['to_id']):r for r in read(pre/'legs.csv')}
 nodes={r[0]:r for r in load_workbook(find('调度中心与服务区.xlsx'),data_only=True).active.values if isinstance(r[0],str) and (r[0]=='O01' or (r[0].startswith('S') and r[0][1:].isdigit()))}
 projection=json.loads((pre/'audit.json').read_text(encoding='utf-8'))['local_projection']
 summary=json.loads((out/'summary.json').read_text(encoding='utf-8'));reports={}
 for name in ['baseline','makespan_first']:
  path=out/name;plan=json.loads((path/'plan.json').read_text(encoding='utf-8'));seen=Counter();events=[];all_delivery={};totalE=D(0);maxT=D(0);maxerr=0;hard_slacks=[];socslacks=[]
  def eq(a,b,tol='1e-7'):assert abs(D(a)-D(b))<=D(tol),(a,b)
  for p in plan:
   g=p['model'];m=models[g];u=p['unit'];bat=p['battery']
   assert units[u]==g and batteries[bat][0]==g
   assert p['start']>=0
   bs=[boxes[b] for b in p['boxes']];seen.update(p['boxes'])
   q=sum(D(b[3]) for b in bs);volume=sum(D(b[4]) for b in bs)
   assert q<=D(m[3])+D('1e-9') and volume<=D(m[4])+D('1e-12')
   assert len(set(p['route']))==len(p['route']) and set(p['route'])=={b[1] for b in bs}
   t=D(p['start'])+D(m[10])+len(bs)*D(m[11]);eq(t,p['takeoff']);energy=D(0);prev='O01'
   assert len(p['legs'])==len(p['route'])+1
   for k,dest in enumerate(p['route']+['O01']):
    r=legs[prev,dest];a=nodes[prev];b=nodes[dest]
    dist=math.hypot((b[2]-a[2])*projection['meters_per_lon_degree'],(b[3]-a[3])*projection['meters_per_lat_degree'])
    eq(dist,r['horizontal_distance_m'])
    h=D(r['dem_max_m'])+50
    up=h-D(a[4])-(0 if prev=='O01' else 30);down=h-D(b[4])-(0 if dest=='O01' else 30)
    x=q/D(m[3]);L=D(m[6])-(D(m[6])-D(m[7]))*x*x.sqrt()
    en=D(m[8])*D(dist)/L+(D(m[2])+q)*D('9.80665')*up/(D(m[16])*3600000)
    leg=p['legs'][k];assert leg['from_id']==prev and leg['to_id']==dest
    eq(t,leg['start']);eq(q,leg['payload']);eq(en,leg['energy'],'1e-8')
    t+=up/D(m[14])+D(dist)/D(m[5])+down/D(m[15]);eq(t,leg['end']);energy+=en
    if dest!='O01':
     here=[b for b in bs if b[1]==dest];stop=p['stops'][k];eq(t,stop['arrival'])
     t+=D(m[12])+len(here)*D(m[13]);eq(t,stop['complete'])
     assert set(stop['boxes'])=={b[0] for b in here}
     for b in here:
      eq(t,p['deliveries'][b[0]]);all_delivery[b[0]]=t
      limits=[]
      if b[2]=='医疗物资':assert b[7] is not None;limits.append(D(b[7]))
      if b[5]=='是':assert b[6] is not None;limits.append(D(b[6]))
      for deadline in limits:
       slack=deadline-t;hard_slacks.append(slack);assert slack>=D('-1e-7'),(b[0],float(slack))
     q-=sum(D(b[3]) for b in here)
    prev=dest
   assert abs(q)<D('1e-9');eq(t,p['finish']);eq(energy,p['energy'],'1e-8')
   soc=1-energy/D(m[8]);eq(soc,p['soc'],'1e-10');assert soc>=D(m[9])/100-D('1e-10')
   full=D(batteries[bat][1]);chg=full*(D('.65')*(D('.9')-soc)/D('.9')+D('.35')) if soc<D('.9') else full*D('.35')*(1-soc)/D('.1')
   eq(p['charge_start'],t);eq(p['battery_ready'],t+chg)
   # Use exported boundaries AFTER independently checking them; this preserves
   # identical shared timestamps rather than introducing Decimal/float ordering noise.
   events.extend([(float(p['start']),2,'PREP_START',u,bat,p['sortie']),(float(p['finish']),0,'LAND_AND_CHARGE',u,bat,p['sortie']),(float(p['battery_ready']),1,'CHARGE_COMPLETE',u,bat,p['sortie'])])
   totalE+=energy;maxT=max(maxT,t);socslacks.append(soc-D(m[9])/100);maxerr=max(maxerr,float(abs(energy-D(p['energy']))))
  assert set(seen)==set(boxes) and all(n==1 for n in seen.values())
  # Events release resources before new reservations at identical times.
  machine={u:None for u in units};battery={b:'FULL' for b in batteries};trace=[]
  for t,_,event,u,bat,flight in sorted(events):
   if event=='PREP_START':
    assert machine[u] is None and battery[bat]=='FULL',(t,u,bat,event)
    machine[u]=flight;battery[bat]=flight
   elif event=='LAND_AND_CHARGE':
    assert machine[u]==flight and battery[bat]==flight
    machine[u]=None;battery[bat]='CHARGING'
   else:
    assert battery[bat]=='CHARGING';battery[bat]='FULL'
   trace.append(dict(time_s=t,event=event,unit=u,battery=bat,sortie=flight,unit_state=machine[u] or 'AVAILABLE',battery_state=battery[bat]))
  delay=sum(D(boxes[b][8])*max(D(0),t-D(boxes[b][7])) for b,t in all_delivery.items() if boxes[b][7] is not None)
  eq(delay,summary[name]['D']);eq(maxT,summary[name]['Cmax']);eq(totalE,summary[name]['E'],'1e-8');assert len(plan)==summary[name]['N']
  # Check exported template CSVs as well as JSON.
  deliveries=read(path/'Q2_逐箱交付.csv');assert len(deliveries)==80
  bybox={b:p for p in plan for b in p['boxes']}
  for r in deliveries:
   bid=r['货箱编号'];eq(r['交付完成时刻（s）'],all_delivery[bid])
   assert r['服务区编号']==boxes[bid][1] and r['架次编号']==bybox[bid]['sortie']
  exported=read(path/'Q2_运输架次.csv');assert len(exported)==len(plan)
  bysortie={p['sortie']:p for p in plan}
  assert len({r['架次编号'] for r in exported})==len(plan)
  for r in exported:
   pp=bysortie[r['架次编号']]
   assert r['无人机编号']==pp['unit'] and r['机型编号']==pp['model'] and r['电池编号']==pp['battery']
   assert r['访问服务区顺序']=='→'.join(pp['route'])
   eq(r['开始时刻（s）'],pp['start']);eq(r['返回O01时刻（s）'],pp['finish']);eq(r['架次能耗（kWh）'],pp['energy'],'1e-8')
  write(path/'event_replay.csv',trace)
  reports[name]=dict(status='PASS',boxes=80,medical_boxes=sum(b[2]=='医疗物资' for b in boxes.values()),first_batch_boxes=sum(b[5]=='是' for b in boxes.values()),hard_deadline_min_slack_s=float(min(hard_slacks)),min_energy_reserve_slack=float(min(socslacks)),D=float(delay),Cmax=float(maxT),E=float(totalE),N=len(plan),events=len(trace),max_energy_recompute_error_kWh=maxerr,used_units=sorted({p['unit'] for p in plan}),used_batteries=sorted({p['battery'] for p in plan}),all_expected_times_met=all(boxes[b][7] is None or t<=D(boxes[b][7])+D('1e-7') for b,t in all_delivery.items()))
 reports['method']='Independent original-workbook reread, 40-digit Decimal energy/time recomputation and deterministic chronological resource state replay. No stochastic physical assumptions.'
 reports['tolerances']=dict(time_s=1e-7,energy_kWh=1e-8,mass_kg=1e-9,volume_m3=1e-12,soc=1e-10)
 (out/'verification.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(reports,ensure_ascii=False,indent=2))

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--source',type=Path,required=True);a.add_argument('--preflight',type=Path,required=True);a.add_argument('--out',type=Path,default=Path(__file__).resolve().parent);args=a.parse_args();run(args.source,args.preflight,args.out)
