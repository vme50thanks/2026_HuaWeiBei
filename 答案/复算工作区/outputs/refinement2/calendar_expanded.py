"""Joint cargo, type, route, sequence and relay calendar search with geometry caching."""
from pathlib import Path
import sys,json,random,time,math,itertools,argparse
import numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'outputs/q3'));sys.path.insert(0,str(ROOT/'outputs/q2'))
from solve_joint import fit
from solve_q2 import Problem,score
from communication import World,dump
from relay_local import save
load=lambda p:json.loads(p.read_text(encoding='utf-8'))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--seconds',type=float,default=240);ap.add_argument('--seed',type=int,default=2026092603);a=ap.parse_args()
 t0=time.perf_counter();pr=Problem(Path('D:/研一/比赛/中文题目/D题'),ROOT/'outputs/preflight');w=World(pr.source,pr.pre);rng=random.Random(a.seed)
 rr=load(OUT/'q3/baseline/relay_plan.json');c=[w.relay_trip(*x['position'][:2],x['agl']) for x in rr];cache={};geom={};gcache={}
 def geometry(p):
  key=(p['model'],tuple(p['route']),tuple(len(s['boxes']) for s in p['stops']))
  if key in gcache:return gcache[key]
  first=emin=lmin=1e10;emax=-1e10;both=[]
  for ph in w.phases([dict(p,sortie='TEST')]):
   k=(p['model'],ph['phase'],ph['from_id'],ph['to_id'])
   if k not in geom:
    # Actual phase endpoints included; service is stationary.
    ph0=dict(ph,start=0,end=ph['end']-ph['start']);vals=[]
    pts=w.sample([ph0],2) if ph['phase']!='交接' else [(0,0,np.array(ph['a']))]
    for _,t,pos in pts:
     if w.margin(pos,w.gateway,'direct')[0]>=0:continue
     master=w.margin(pos,np.array(c[0]['position']),'access')[0]>=0
     early=w.margin(pos,np.array(c[1]['position']),'access')[0]>=0
     late=w.margin(pos,np.array(c[2]['position']),'access')[0]>=0
     if not(master or early or late):geom[k]=None;break
     vals.append((t,0 if master else 3 if early and late else 1 if early else 2))
    else:geom[k]=vals
   vals=geom[k]
   if vals is None:gcache[key]=None;return None
   if ph['phase']=='交接' and vals:vals=[(0,vals[0][1]),(ph['end']-ph['start'],vals[0][1])]
   for dt,kind in vals:
    t=ph['start']+dt;first=min(first,t)
    if kind==1:emin=min(emin,t);emax=max(emax,t)
    elif kind==2:lmin=min(lmin,t)
    elif kind==3:both.append(t)
  result=(first,emin,emax,lmin,both);gcache[key]=result;return result
 def profiles(g,ids):
  key=g,tuple(sorted(ids))
  if key in cache:return cache[key]
  bs=[pr.boxes[b] for b in ids];m=pr.models[g];sites=sorted({b['site'] for b in bs});ans=[]
  if len(sites)>4 or sum(b['mass'] for b in bs)>m[3]+1e-9 or sum(b['vol'] for b in bs)>m[4]+1e-12:cache[key]=ans;return ans
  for rt in itertools.permutations(sites):
   p=pr.evaluate(g,ids,rt)
   if p is None:continue
   geo=geometry(p)
   if geo is None:continue
   hard=min((min(b['hard'] if b['hard'] is not None else 1e10,b['due'] if b['due'] is not None else 1e10)-p['deliveries'][b['id']] for b in bs),default=1e10)
   ans.append((p,*geo,hard))
  cache[key]=ans;return ans
 def decode(st,end,full=False):
  late=end+c[1]['back']+300+c[2]['earliest_service']+10
  ur={g:[(0,u) for u in pr.units if pr.units[u]==g] for g in 'ABC'};br={g:[(0,b) for b,_ in pr.batts[g]] for g in 'ABC'};C=E=F=0;plan=[]
  for g,ids in st:
   ut,u=min(ur[g]);bt,b=min(br[g]);earliest=max(ut,bt);opts=[]
   for p,first,emin,emax,lmin,both,hard in profiles(g,ids):
    start=max(earliest,c[0]['earliest_service']+6-first,c[1]['earliest_service']+6-emin,late+6-lmin,0);upper=min(hard,end-6-emax)
    for _ in range(6):
     bad=[t for t in both if not(c[1]['earliest_service']+6<=start+t<=end-6 or start+t>=late+6)]
     if not bad:break
     start=max(start,late+6-min(bad))
    else:continue
    if start<=upper+1e-8:opts.append((start+p['finish'],p['energy'],start,p))
   if not opts:return None
   finish,en,start,p=min(opts,key=lambda x:x[:2]);ready=finish+pr.charge(g,p['soc']);ur[g].remove((ut,u));ur[g].append((finish,u));br[g].remove((bt,b));br[g].append((ready,b));C=max(C,finish);E+=en;F+=finish
   if full:
    q=pr.evaluate(g,ids,p['route'],start);q.update(unit=u,battery=b,sortie=f'P{len(plan)+1:03d}',charge_start=q['finish'],battery_ready=q['finish']+pr.charge(g,q['soc']));plan.append(q)
  return plan if full else (C,E,len(st),F)
 seeds=[]
 for pp in [load(OUT/'q3/baseline/plan.json'),load(OUT/'q2_after_run1/baseline/plan.json')]:
  st=[(p['model'],tuple(p['boxes'])) for p in sorted(pp,key=lambda x:x['start'])]
  for end in [2200,2700,3200,3700]:
   for state in [st,sorted(st,key=lambda b:min((p[3] for p in profiles(*b)),default=1e10),reverse=True)]:
    v=decode(state,end)
    if v:seeds.append((v,state,end))
 if not seeds:raise RuntimeError('Calendar seed not found; no infeasibility proof')
 best,state,end=min(seeds);cur=list(state);cv=best;ce=end;beststate=state;bestend=end;it=feasible=0;logs=[]
 print('SEED',best,end,flush=True)
 while time.perf_counter()-t0<a.seconds:
  it+=1
  if it%20000==0:cur=list(beststate);cv=best;ce=bestend
  st=list(cur);i,j=rng.sample(range(len(st)),2);eend=ce;kind=rng.randrange(10);g,bs=st[i];h,cs=st[j]
  if kind==0:row=st.pop(i);st.insert(j,row)
  elif kind==1:st[i]=(rng.choice('ABC'),bs)
  elif kind==2:eend=max(1200,min(4200,ce+rng.choice([-100,-30,30,100])))
  elif kind==3:st[i],st[j]=st[j],st[i]
  elif kind==4:
   b=rng.choice(bs);st[i]=(g,tuple(x for x in bs if x!=b));st[j]=(h,cs+(b,));st=[x for x in st if x[1]]
  elif kind==5:
   b=rng.choice(bs);d=rng.choice(cs);st[i]=(g,tuple(d if x==b else x for x in bs));st[j]=(h,tuple(b if x==d else x for x in cs))
  elif kind==6:st[i]=(rng.choice([g,h]),bs+cs);st.pop(j)
  elif kind==7 and len(bs)>1:
   v=list(bs);rng.shuffle(v);cut=rng.randrange(1,len(v));st[i]=(g,tuple(v[:cut]));st.insert(j,(rng.choice('ABC'),tuple(v[cut:])))
  elif kind==8:
   v=list(bs+cs);rng.shuffle(v);cut=rng.randrange(1,len(v));st[i]=(rng.choice('ABC'),tuple(v[:cut]));st[j]=(rng.choice('ABC'),tuple(v[cut:]))
  elif kind==9:st[i]=(h,bs);st[j]=(g,cs)
  else:continue
  v=decode(st,eend)
  if v is None:continue
  feasible+=1
  if (round(v[0],7),v[1],v[2])<(round(best[0],7),best[1],best[2]):
   best=v;beststate=st;bestend=eend;logs.append((it,v,eend));print('BEST',it,v,eend,flush=True)
  diff=(v[0]+.003*v[3]+.05*v[1])-(cv[0]+.003*cv[3]+.05*cv[1]);temp=3+100*(1-(it%20000)/20000)**3
  if diff<0 or rng.random()<math.exp(-min(700,diff/temp)):cur=st;cv=v;ce=eend
 p=decode(beststate,bestend,True);dump(OUT/'calendar_transport.json',p)
 result=fit(w,p,c,[dict(master=0,early=1,late=2,split=bestend+500)],.5,{})
 print('FINE',result[:2] if result else None,flush=True)
 if result:save(pr,w,p,result[2],load(OUT/'q3/summary.json'),'joint cargo/calendar search')
 dump(OUT/'calendar_search.json',dict(seed=a.seed,seconds=time.perf_counter()-t0,iterations=it,feasible=feasible,best=best,early_end=bestend,logs=logs,geometry_keys=len(geom),batch_profiles=len(cache),fit=result is not None,limitations='Four stop cap; all expected times satisfied as D=0 search restriction; 2s geometry cache, final 0.5s fit; three relay structure; no global proof'))
if __name__=='__main__':main()
