"""Bounded joint candidate search; every changed batch is rescheduled from scratch."""
from pathlib import Path
import sys,json,random,time,argparse,math
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent/'support'))
from solve_q2 import Problem,score,export
from improve_q2 import decode
from communication import World,dump,csvout

def fit(w,plan,candidates,triples,dt,cache):
 phases=w.phases(plan);samples=w.sample(phases,dt);blind=[]
 for ix,t,pos in samples:
  key=tuple(np.round(pos,7))
  if key not in cache:
   direct=w.margin(pos,w.gateway,'direct')[0]
   cache[key]=(direct,None)
  direct,ms=cache[key]
  if direct>=0:continue
  if ms is None:
   ms=np.array([w.margin(pos,np.array(c['position']),'access')[0] for c in candidates]);cache[key]=(direct,ms)
  blind.append((t,ms))
 blind.sort(key=lambda x:x[0]);times=np.array([r[0] for r in blind]);m=np.array([r[1] for r in blind]);options=[]
 for tr in triples:
  ids=[tr['master'],tr['early'],tr['late']];cov=m[:,ids]>=0
  # Retain split as one candidate, and derive split from geometric residual gaps.
  residual=times[~cov[:,0]]
  splits=[tr['split']]
  if len(residual)>1:
   gaps=np.diff(residual);splits += [float((residual[k]+residual[k+1])/2) for k in np.argsort(gaps)[-3:]]
  for split in splits:
   secondary=np.where(times<=split,1,2);ok=cov[np.arange(len(times)),secondary]
   if not np.all(ok|cov[:,0]):continue
   assignment=np.zeros(len(times),dtype=int)
   for j in [1,2]:
    required=(secondary==j)&~cov[:,0]
    if not required.any():continue
    lo,hi=times[required].min(),times[required].max()
    assignment[(times>=lo)&(times<=hi)&cov[:,j]]=j
   relay=[]
   for j,idx in enumerate(ids):
    tt=times[assignment==j]
    if not len(tt):break
    c=candidates[idx];start=float(tt.min())-5;end=float(tt.max())+5
    prep=start-c['earliest_service'];en=c['travel_energy']+1.1*(end-start+30)/3600
    if prep<0 or en>2.56:break
    soc=1-en/3.2;chg=1800*(.65*(.9-soc)/.9+.35) if soc<.9 else 1800*.35*(1-soc)/.1
    relay.append(dict(**c,candidate=idx,sortie=f'R{j+1:03d}',unit='R01' if j==0 else 'R02',component=f'R-ENE-{j+1:02d}',start=prep,takeoff=prep+180,arrival=start-30,service_start=start,service_end=end,finish=end+c['back'],body_ready=end+c['back']+300,energy=en,soc=soc,charge_start=end+c['back'],component_ready=end+c['back']+chg))
   if len(relay)!=3 or relay[1]['body_ready']>relay[2]['start']:continue
   finish=max(max(p['finish'] for p in plan),max(r['finish'] for r in relay));en=sum(r['energy'] for r in relay)
   options.append((finish,en,relay))
 return min(options,key=lambda r:r[:2]) if options else None

def main(a):
 t0=time.perf_counter();w=World(a.source,a.preflight);pr=Problem(a.source,a.preflight);c=json.loads((a.out/'ridge_search/relay_candidates.json').read_text(encoding='utf-8'));triples=json.loads((a.out/a.triples).read_text(encoding='utf-8'));cache={};rng=random.Random(20260923)
 used=sorted({t[k] for t in triples for k in ['master','early','late']});mapping={v:i for i,v in enumerate(used)};c=[dict(c[i],original_candidate=i) for i in used]
 for tr in triples:
  for k in ['master','early','late']:tr[k]=mapping[tr[k]]
 pool=[]
 for name in ['baseline','makespan_first']:
  pool.append((f'q2_{name}',json.loads((a.q2/name/'plan.json').read_text(encoding='utf-8'))))
 batches=[p['boxes'] for p in sorted(pool[0][1],key=lambda x:(x['start'],x['sortie']))]
 for it in range(a.mutations):
  b=[list(x) for x in batches];i,j=rng.sample(range(len(b)),2);kind=it%4
  if kind==0:b[i],b[j]=b[j],b[i]
  elif kind==1:b[j].append(b[i].pop(rng.randrange(len(b[i]))));b=[x for x in b if x]
  elif kind==2:
   ii=rng.randrange(len(b[i]));jj=rng.randrange(len(b[j]));b[i][ii],b[j][jj]=b[j][jj],b[i][ii]
  else:b[i]+=b[j];b.pop(j)
  p=decode(pr,b,3)
  if p:pool.append((f'mutation_{it}',p))
 log=[];feasible=[]
 for name,p in pool:
  v=score(pr,p);res=fit(w,p,c,triples,5,cache)
  log.append(dict(candidate=name,transport_D=v[0],transport_Cmax=v[1],transport_E=v[2],transport_N=v[3],communication_fit=res is not None))
  if res:
   value=(v[0],res[0],v[2]+res[1],v[3]+3);feasible.append((value,name,p,res[2]));log[-1].update(C_joint=res[0],total_E=value[2]);print(name,value,flush=True)
  if time.perf_counter()-t0>a.seconds:break
 if not feasible:raise RuntimeError('No candidate found; not an infeasibility proof')
 best={};finecache={}
 for name,order in [('baseline',(0,1,2,3)),('makespan_first',(1,0,2,3))]:
  # Fine check at least the top three candidates; failure returns to candidate pool.
  ranked=sorted(feasible,key=lambda x:tuple(x[0][i] for i in order));opts=[]
  for _,label,p,_ in ranked[:min(8,len(ranked))]:
   r=fit(w,p,c,triples,.5,finecache)
   if r:
    v=score(pr,p);value=(v[0],r[0],v[2]+r[1],v[3]+3);opts.append((tuple(value[i] for i in order),value,label,p,r[2]))
  if not opts:raise RuntimeError('Fine check failed; expand search')
  _,v,label,p,r=min(opts,key=lambda x:x[0]);export(pr,p,a.out,name);dump(a.out/name/'relay_plan.json',r);dump(a.out/name/'phases.json',w.phases(p));tv=score(pr,p)
  best[name]=dict(D=v[0],Cmax=tv[1],E=tv[2],N=tv[3],C_joint=v[1],relay_E=sum(x['energy'] for x in r),total_E=v[2],relay_N=3,total_N=v[3],source_candidate=label,status='NUMERICAL_CANDIDATE_PENDING_INDEPENDENT_REPLAY')
  headers=[h for h in list(pr.template['Q3_中继架次'].values)[0] if h]
  csvout(a.out/name/'Q3_中继架次.csv',[dict(zip(headers,[x['sortie'],x['unit'],x['component'],x['start'],*w.lonlat(*x['position'][:2]),x['position'][2],x['service_start'],x['service_end'],x['finish'],x['energy']])) for x in r])
  csvout(a.out/name/'relay_resources.csv',[{k:x[k] for k in ['sortie','unit','component','start','takeoff','arrival','service_start','service_end','finish','body_ready','energy','soc','charge_start','component_ready']} for x in r])
 best['search']=dict(seconds=time.perf_counter()-t0,seed=20260923,mutation_limit=a.mutations,pool_size=len(pool),evaluated=len(log),coarse_feasible=len(feasible),candidate_locations=len(c),triples=len(triples),time_limit=a.seconds,fine_dt=.5,no_global_proof=True,maxstops=3,triples_file=a.triples)
 dump(a.out/'summary.json',best);dump(a.out/'joint_search_log.json',log);print(json.dumps(best,ensure_ascii=False),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--preflight',type=Path,required=True);p.add_argument('--q2',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--mutations',type=int,default=24);p.add_argument('--seconds',type=float,default=240);p.add_argument('--triples',default='temporal_candidates.json');main(p.parse_args())
