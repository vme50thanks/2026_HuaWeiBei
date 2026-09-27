"""Coordinate search of relay locations; full task energy and resource fit retained."""
from pathlib import Path
import sys,json,time,itertools
import numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'outputs/q3'));sys.path.insert(0,str(ROOT/'outputs/q2'))
from communication import World,dump,csvout
from solve_joint import fit
from solve_q2 import Problem,score,export
load=lambda p:json.loads(p.read_text(encoding='utf-8'))
def save(pr,w,p,r,s,label):
 v=score(pr,p);value=(v[0],max(x['finish'] for x in p+r),v[2]+sum(x['energy'] for x in r),len(p)+len(r))
 for name,order in [('baseline',(0,1,2,3)),('makespan_first',(1,0,2,3))]:
  prev=tuple(s[name][k] for k in ['D','C_joint','total_E','total_N'])
  key=lambda v:tuple(round(v[k],7) if k<2 else v[k] for k in order)
  if key(value)>=key(prev):continue
  export(pr,p,OUT/'q3',name);d=OUT/'q3'/name;dump(d/'relay_plan.json',r);dump(d/'phases.json',w.phases(p))
  headers=[h for h in list(pr.template['Q3_中继架次'].values)[0] if h]
  csvout(d/'Q3_中继架次.csv',[dict(zip(headers,[x['sortie'],x['unit'],x['component'],x['start'],*w.lonlat(*x['position'][:2]),x['position'][2],x['service_start'],x['service_end'],x['finish'],x['energy']])) for x in r])
  csvout(d/'relay_resources.csv',[{k:x[k] for k in ['sortie','unit','component','start','takeoff','arrival','service_start','service_end','finish','body_ready','energy','soc','charge_start','component_ready']} for x in r])
  s[name]=dict(D=v[0],Cmax=v[1],E=v[2],N=v[3],C_joint=value[1],relay_E=sum(x['energy'] for x in r),total_E=value[2],relay_N=len(r),total_N=value[3],status='PENDING_INDEPENDENT_REPLAY',source=label)
 dump(OUT/'q3/summary.json',s)
def main():
 t0=time.perf_counter();w=World(Path('D:/研一/比赛/中文题目/D题'),ROOT/'outputs/preflight');pr=Problem(w.source,w.pre);logs=[];s=load(OUT/'q3/summary.json')
 oldp=load(ROOT/'outputs/refinement/q3/baseline/plan.json');oldr=load(ROOT/'outputs/refinement/q3/baseline/relay_plan.json')
 oldc=[w.relay_trip(*x['position'][:2],x['agl']) for x in oldr]
 for label,p in [('previous_transport',oldp),('new_transport',load(OUT/'q2/baseline/plan.json'))]:
  current=oldc;winner=None
  for step in [250,125,50]:
   cand=list(current);triples=[dict(master=0,early=1,late=2,split=4000)]
   for role,c in enumerate(current):
    x,y,_=c['position']
    offsets=[(dx,dy,c['agl']) for dx,dy in itertools.product([-step,0,step],repeat=2) if dx or dy]+[(0,0,h) for h in [150,200,250] if h!=c['agl']]
    for dx,dy,h in offsets:
     z=w.relay_trip(x+dx,y+dy,h)
     if z is None or w.margin(np.array(z['position']),w.gateway,'backhaul')[0]<0:continue
     idx=len(cand);cand.append(z);ids=[0,1,2];ids[role]=idx;triples.append(dict(zip(['master','early','late','split'],ids+[4000])))
   rr=fit(w,p,cand,triples,5,{})
   logs.append(dict(label=label,step_m=step,candidates=len(cand),triples=len(triples),result=rr[:2] if rr else None));print(logs[-1],flush=True)
   if rr:
    current=[cand[x['candidate']] for x in rr[2]];winner=rr
  if winner:
   fine=fit(w,p,current,[dict(master=0,early=1,late=2,split=4000)],.5,{})
   print('FINE',label,fine[:2] if fine else None,flush=True)
   if fine:save(pr,w,p,fine[2],s,label)
 dump(OUT/'relay_location_search.json',dict(seconds=time.perf_counter()-t0,logs=logs,limits='Coordinate search at 250/125/50m and 150/200/250/300m AGL; three missions, two bodies; numerical search only'))
if __name__=='__main__':main()
