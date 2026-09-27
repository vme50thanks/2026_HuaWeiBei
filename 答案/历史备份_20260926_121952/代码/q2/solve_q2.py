from pathlib import Path
from collections import defaultdict,Counter
from itertools import permutations
import csv,json,math,random,time,hashlib,argparse
from openpyxl import load_workbook

def read(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def csvout(p,rows,fields=None):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)

class Problem:
 def __init__(self,source,pre):
  self.source=source;self.pre=pre
  for row in json.loads((pre/'audit.json').read_text(encoding='utf-8'))['sources']:
   assert hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()==row['sha256']
  find=lambda n:next(source.rglob(n))
  w=load_workbook(find('运输无人机数据.xlsx'),data_only=True).active
  rr=list(w.values);self.models={r[0]:r for r in rr[2:5]}
  self.units={r[0]:r[1] for r in rr[8:16]}
  self.batts={r[0]:[(f'{r[0]}-BAT-{i+1:02d}',float(r[2])) for i in range(r[1])] for r in rr[19:22]}
  assert Counter(self.units.values())=={'A':4,'B':2,'C':2}
  assert [len(self.batts[g]) for g in 'ABC']==[6,4,4]
  w=load_workbook(find('物资需求与配送时限.xlsx'),data_only=True)
  self.boxes={}
  for r in list(w['逐箱货箱清单'].values)[1:]:
   if not r[0]:continue
   hard=[float(r[7])] if r[2]=='医疗物资' and r[7] is not None else []
   if r[5]=='是':assert r[6] is not None;hard.append(float(r[6]))
   self.boxes[r[0]]=dict(id=r[0],site=r[1],kind=r[2],mass=float(r[3]),vol=float(r[4]),hard=min(hard) if hard else None,due=float(r[7]) if r[7] is not None else None,weight=float(r[8]))
  assert len(self.boxes)==80
  self.legs={(r['from_id'],r['to_id']):{k:float(r[k]) for k in ['horizontal_distance_m','climb_m','descent_m']} for r in read(pre/'legs.csv')}
  self.ft={(r['from_id'],r['to_id'],r['model_id']):float(r['flight_time_s']) for r in read(pre/'flight_times.csv')}
  self.nodes=read(pre/'nodes.csv')
  self.template=load_workbook(find('结果提交模板.xlsx'),data_only=True)
 def charge(self,g,soc):
  full=self.batts[g][0][1]
  return full*(.65*(.9-soc)/.9+.35) if soc<.9 else full*.35*(1-soc)/.1
 def evaluate(self,g,ids,route,start=0):
  m=self.models[g];bs=[self.boxes[i] for i in ids];q=sum(b['mass'] for b in bs);vol=sum(b['vol'] for b in bs)
  if q>m[3]+1e-10 or vol>m[4]+1e-12:return None
  take=start+m[10]+len(ids)*m[11];t=take;e=0;last='O01';delivs={};legs=[];stops=[]
  for dest in list(route)+['O01']:
   a=self.legs[last,dest];L=m[6]-(m[6]-m[7])*(q/m[3])**1.5
   en=m[8]*a['horizontal_distance_m']/L+(m[2]+q)*9.80665*a['climb_m']/(m[16]*3.6e6)
   begin=t;t+=self.ft[last,dest,g];e+=en
   legs.append(dict(from_id=last,to_id=dest,start=begin,end=t,payload=q,energy=en))
   if dest!='O01':
    here=[b for b in bs if b['site']==dest];arrival=t;t+=m[12]+len(here)*m[13]
    for b in here:
     delivs[b['id']]=t
     if b['hard'] is not None and t>b['hard']+1e-8:return None
    q-=sum(b['mass'] for b in here)
    stops.append(dict(site=dest,arrival=arrival,complete=t,boxes=[b['id'] for b in here]))
   last=dest
  if e>(1-m[9]/100)*m[8]+1e-10:return None
  assert abs(q)<1e-8
  return dict(model=g,boxes=list(ids),route=list(route),start=start,takeoff=take,finish=t,energy=e,soc=1-e/m[8],deliveries=delivs,legs=legs,stops=stops)
 def best_route(self,g,ids,start,maxstops):
  sites=sorted({self.boxes[i]['site'] for i in ids})
  if len(sites)>maxstops:return None
  best=None
  for rt in permutations(sites):
   a=self.evaluate(g,ids,rt,start)
   if a:
    delay=sum(self.boxes[b]['weight']*max(0,t-self.boxes[b]['due']) for b,t in a['deliveries'].items() if self.boxes[b]['due'] is not None)
    key=(delay,a['finish'],a['energy'])
    if best is None or key<best[0]:best=(key,a)
  return best[1] if best else None

 def construct(self,seed,maxstops):
  rng=random.Random(seed);pending=set(self.boxes);ready={u:0. for u in self.units};br={b:0. for vals in self.batts.values() for b,_ in vals};plan=[]
  # Fixed per-run perturbations; actual system itself is deterministic.
  noise={b:rng.uniform(.65,1.45) for b in self.boxes}
  power=rng.uniform(.8,2.2);hardmult=rng.uniform(1.5,5);penalty=rng.uniform(.0001,.0015)
  while pending:
   resources=[]
   for u,g in self.units.items():
    bat=min(self.batts[g],key=lambda bt:(br[bt[0]],bt[0]))[0]
    resources.append((max(ready[u],br[bat]),{'C':0,'B':1,'A':2}[g],u,g,bat))
   resources.sort();choice=None
   for start,_,u,g,bat in resources:
    # Try first currently available vehicle; if no admissible cargo, try others.
    def weight(bid):
     b=self.boxes[bid];deadline=min(b['due'] or 1e9,b['hard'] or 1e9)
     urgency=(3600/max(300,deadline-start))**power
     return noise[bid]*b['weight']*urgency*(hardmult if b['hard'] is not None else 1)
    ranked=sorted(pending,key=lambda b:(-weight(b),b))
    seeds=[]
    for bid in ranked:
     if self.boxes[bid]['site'] not in [self.boxes[x]['site'] for x in seeds]:seeds.append(bid)
     if len(seeds)>=5:break
    candidates=[]
    for anchor in seeds:
     selected=[anchor];a=self.best_route(g,selected,start,maxstops)
     if not a:continue
     # Greedy insertion with full route permutation for up to maxstops visits.
     for bid in ranked:
      if bid in selected:continue
      m=self.models[g]
      if sum(self.boxes[x]['mass'] for x in selected)+self.boxes[bid]['mass']>m[3]+1e-9:continue
      if sum(self.boxes[x]['vol'] for x in selected)+self.boxes[bid]['vol']>m[4]+1e-12:continue
      candidate=self.best_route(g,selected+[bid],start,maxstops)
      if candidate:selected.append(bid);a=candidate
     benefit=sum(weight(b) for b in selected)
     score=benefit/(1+penalty*(a['finish']-start))
     candidates.append((score,a))
    if candidates:
     a=max(candidates,key=lambda v:v[0])[1];choice=(u,bat,a);break
   if choice is None:return None
   u,bat,a=choice;g=a['model'];a.update(unit=u,battery=bat,sortie=f'P{len(plan)+1:03d}')
   a['charge_start']=a['finish'];a['battery_ready']=a['finish']+self.charge(g,a['soc'])
   plan.append(a);pending.difference_update(a['boxes']);ready[u]=a['finish'];br[bat]=a['battery_ready']
  return plan

def score(problem,plan):
 d=sum(problem.boxes[b]['weight']*max(0,t-problem.boxes[b]['due']) for a in plan for b,t in a['deliveries'].items() if problem.boxes[b]['due'] is not None)
 return (d,max(a['finish'] for a in plan),sum(a['energy'] for a in plan),len(plan))

def export(pr,plan,out,name):
 dest=out/name;dest.mkdir(parents=True,exist_ok=True);dump(dest/'plan.json',plan)
 rows=[];delivs=[];legs=[];usage=[]
 for a in plan:
  rows.append(dict(zip(list(pr.template['Q2_运输架次'].values)[0],[a['sortie'],a['unit'],a['model'],a['battery'],a['start'],'→'.join(a['route']),a['finish'],a['energy']])))
  for b,t in a['deliveries'].items():delivs.append(dict(zip(list(pr.template['Q2_逐箱交付'].values)[0],[b,a['sortie'],pr.boxes[b]['site'],t])))
  legs.extend(dict(sortie=a['sortie'],**l) for l in a['legs'])
  usage.append(dict(sortie=a['sortie'],unit=a['unit'],model=a['model'],battery=a['battery'],start=a['start'],takeoff=a['takeoff'],return_time=a['finish'],soc_start=1,soc_return=a['soc'],charge_start=a['charge_start'],charge_end=a['battery_ready']))
 csvout(dest/'Q2_运输架次.csv',rows);csvout(dest/'Q2_逐箱交付.csv',delivs);csvout(dest/'legs.csv',legs);csvout(dest/'resource_usage.csv',usage)
 csvout(dest/'stops.csv',[dict(sortie=a['sortie'],site=s['site'],arrival=s['arrival'],complete=s['complete'],boxes=';'.join(s['boxes'])) for a in plan for s in a['stops']])

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--preflight',type=Path,required=True);ap.add_argument('--out',type=Path,default=Path(__file__).resolve().parent);ap.add_argument('--runs',type=int,default=120);ap.add_argument('--seconds',type=float,default=180)
 args=ap.parse_args();pr=Problem(args.source,args.preflight);args.out.mkdir(exist_ok=True,parents=True)
 start=time.perf_counter();best={};log=[]
 for maxstops in [1,2,3]:
  for seed in range(args.runs):
   if time.perf_counter()-start>args.seconds:break
   plan=pr.construct(seed,maxstops)
   if plan is None:
    log.append(dict(maxstops=maxstops,seed=seed,status='NO_FEASIBLE_PLAN_FOUND'));continue
   value=score(pr,plan);log.append(dict(maxstops=maxstops,seed=seed,status='FEASIBLE',D=value[0],Cmax=value[1],E=value[2],N=value[3]))
   for name,order in [('baseline',(0,1,2,3)),('makespan_first',(1,0,2,3))]:
    key=tuple(value[k] for k in order)
    if name not in best or key<best[name][0]:
     best[name]=(key,plan,value,seed,maxstops);print(name,maxstops,seed,value,flush=True)
  if time.perf_counter()-start>args.seconds:break
 dump(args.out/'search_log.json',log)
 if not best:raise RuntimeError('Search did not find a feasible plan; no infeasibility proof.')
 for name,(_,plan,value,seed,k) in best.items():export(pr,plan,args.out,name)
 summary={name:dict(D=v[2][0],Cmax=v[2][1],E=v[2][2],N=v[2][3],seed=v[3],maxstops=v[4],status='VERIFIABLE_HEURISTIC_INCUMBENT',drone_counts=dict(Counter(a['model'] for a in v[1]))) for name,v in best.items()}
 summary['search']=dict(elapsed_seconds=time.perf_counter()-start,time_limit=args.seconds,runs_per_maxstops=args.runs,attempts=len(log),feasible=sum(r['status']=='FEASIBLE' for r in log),method='seeded multi-start greedy insertion and exhaustive within-batch visit permutations; both priorities rank same candidate pool',no_global_optimality_proof=True)
 dump(args.out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
