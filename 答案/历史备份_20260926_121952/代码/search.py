"""Explicit-type simulated annealing; immutable original inputs and independent replay."""
from pathlib import Path
import sys,json,random,time,math,itertools,argparse
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'outputs/q2'))
from solve_q2 import Problem,score,export,dump

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--seconds',type=float,default=180);ap.add_argument('--stops',type=int,default=3);ap.add_argument('--seed',type=int,default=20260925);a=ap.parse_args()
 out=Path(__file__).parent/'q2';out.mkdir(parents=True,exist_ok=True)
 pr=Problem(Path('D:/研一/比赛/中文题目/D题'),ROOT/'outputs/preflight');rng=random.Random(a.seed);cache={};t0=time.perf_counter();logs=[]
 def profiles(g,ids):
  key=(g,tuple(sorted(ids)))
  if key in cache:return cache[key]
  sites=sorted({pr.boxes[b]['site'] for b in ids});vals=[]
  if len(sites)<=a.stops:
   for route in itertools.permutations(sites):
    p=pr.evaluate(g,ids,route)
    if p:
     hard=min((pr.boxes[b]['hard']-t for b,t in p['deliveries'].items() if pr.boxes[b]['hard'] is not None),default=1e10)
     due=[(t-pr.boxes[b]['due'],pr.boxes[b]['weight']) for b,t in p['deliveries'].items() if pr.boxes[b]['due'] is not None]
     vals.append((p['finish'],p['energy'],pr.charge(g,p['soc']),hard,due,route))
  cache[key]=vals;return vals
 def decode(state,full=False):
  ur={g:[(0,u) for u in pr.units if pr.units[u]==g] for g in 'ABC'};br={g:[(0,b) for b,_ in pr.batts[g]] for g in 'ABC'};D=E=C=0;plan=[]
  for g,ids in state:
   ut,u=min(ur[g]);bt,b=min(br[g]);start=max(ut,bt);opts=[]
   for dur,en,chg,hard,due,route in profiles(g,ids):
    if start>hard+1e-8:continue
    delay=sum(w*max(0,start+off) for off,w in due);opts.append((delay,dur,en,chg,route))
   if not opts:return None
   delay,dur,en,chg,route=min(opts);finish=start+dur;D+=delay;E+=en;C=max(C,finish)
   ur[g].remove((ut,u));ur[g].append((finish,u));br[g].remove((bt,b));br[g].append((finish+chg,b))
   if full:
    p=pr.evaluate(g,ids,route,start);assert p is not None
    p.update(unit=u,battery=b,sortie=f'P{len(plan)+1:03d}',charge_start=p['finish'],battery_ready=p['finish']+chg);plan.append(p)
  return plan if full else (D,C,E,len(state))
 old=json.loads((ROOT/'outputs/q2/baseline/plan.json').read_text(encoding='utf-8'))
 seed=[(p['model'],tuple(p['boxes'])) for p in sorted(old,key=lambda p:(p['start'],p['sortie']))]
 if (out/'baseline/plan.json').exists():
  prev=json.loads((out/'baseline/plan.json').read_text(encoding='utf-8'));seed=[(p['model'],tuple(p['boxes'])) for p in sorted(prev,key=lambda p:(p['start'],p['sortie']))]
 value=decode(seed);best=value;beststate=seed;alt=value;altstate=seed;cur=seed;cv=value;feasible=0;it=0
 def cost(v):return v[1]+min(v[0],1e8)*2+v[2]*.05
 while time.perf_counter()-t0<a.seconds:
  it+=1
  if it%12000==0:cur=list(beststate);cv=best
  x=list(cur);i=rng.randrange(len(x));j=rng.randrange(len(x));kind=rng.randrange(9)
  g,bs=x[i]
  if kind==0:x[i]=(rng.choice('ABC'),bs)
  elif kind==1:
   item=x.pop(i);x.insert(j,item)
  elif kind==2 and i!=j:
   pick=rng.choice(bs);rest=tuple(b for b in bs if b!=pick);x[j]=(x[j][0],x[j][1]+(pick,));x[i]=(g,rest);x=[v for v in x if v[1]]
  elif kind==3 and i!=j:
   b1=rng.choice(bs);b2=rng.choice(x[j][1]);x[i]=(g,tuple(b2 if b==b1 else b for b in bs));x[j]=(x[j][0],tuple(b1 if b==b2 else b for b in x[j][1]))
  elif kind==4 and i!=j:
   x[i]=(rng.choice([g,x[j][0]]),bs+x[j][1]);x.pop(j)
  elif kind==5 and len(bs)>1:
   part=list(bs);rng.shuffle(part);cut=rng.randrange(1,len(part));x[i]=(g,tuple(part[:cut]));x.insert(j,(rng.choice('ABC'),tuple(part[cut:])))
  elif kind==6 and i!=j:x[i],x[j]=(x[j][0],bs),(g,x[j][1])
  elif kind==7 and i!=j:
   pool=list(bs+x[j][1]);rng.shuffle(pool);cut=rng.randrange(1,len(pool));x[i]=(rng.choice('ABC'),tuple(pool[:cut]));x[j]=(rng.choice('ABC'),tuple(pool[cut:]))
  elif kind==8 and i!=j:
   pool=bs+x[j][1];sites=sorted({pr.boxes[b]['site'] for b in pool});rng.shuffle(sites)
   if len(sites)<2:continue
   site=sites[0];first=tuple(b for b in pool if pr.boxes[b]['site']==site);second=tuple(b for b in pool if pr.boxes[b]['site']!=site)
   x[i]=(rng.choice('ABC'),first);x[j]=(rng.choice('ABC'),second)
  else:continue
  v=decode(x)
  if v is None:continue
  feasible+=1
  if v<best:
   best=v;beststate=x;logs.append(dict(iteration=it,seconds=time.perf_counter()-t0,values=v));print('BEST',it,v,flush=True)
   export(pr,decode(x,True),out,'baseline')
  if (v[1],v[0],v[2],v[3])<(alt[1],alt[0],alt[2],alt[3]):alt=v;altstate=x
  temp=2+100*(1-(it%12000)/12000)**3
  diff=cost(v)-cost(cv)
  if diff<=0 or rng.random()<math.exp(-min(700,diff/temp)):cur=x;cv=v
 result={}
 for name,state in [('baseline',beststate),('makespan_first',altstate)]:
  p=decode(state,True);export(pr,p,out,name);v=score(pr,p);result[name]=dict(zip(['D','Cmax','E','N'],v));result[name]['status']='HEURISTIC_NO_GLOBAL_PROOF'
 result['search']=dict(seed=a.seed,seconds=time.perf_counter()-t0,iterations=it,feasible=feasible,profiles=len(cache),maxstops=a.stops,time_limit=a.seconds)
 dump(out/'summary.json',result);dump(out/'search_log.json',logs);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
