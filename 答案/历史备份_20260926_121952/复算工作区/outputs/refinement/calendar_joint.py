"""Communication calendar jointly constrains transport sequencing and type choice."""
from pathlib import Path
import sys,json,random,time,math,itertools
import numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'outputs/q3'));sys.path.insert(0,str(ROOT/'outputs/q2'))
from solve_joint import fit
from solve_q2 import Problem,score,export
from communication import World,dump,csvout

def main():
 t0=time.perf_counter();src=Path('D:/研一/比赛/中文题目/D题');pre=ROOT/'outputs/preflight';pr=Problem(src,pre);w=World(src,pre);rng=random.Random(20260928)
 allc=json.loads((ROOT/'outputs/q3/ridge_search/relay_candidates.json').read_text(encoding='utf-8'));c=[allc[i] for i in [130,511,489]];cache={}
 old=json.loads((ROOT/'outputs/q3/baseline/plan.json').read_text(encoding='utf-8'));new=json.loads((OUT/'q2/baseline/plan.json').read_text(encoding='utf-8'))
 def profile(g,ids):
  key=(g,tuple(sorted(ids)))
  if key in cache:return cache[key]
  ans=[]
  for rt in itertools.permutations(sorted({pr.boxes[b]['site'] for b in ids})):
   p=pr.evaluate(g,ids,rt)
   if not p:continue
   blind=[];e=[];l=[];both=[];failed=False
   for _,t,pos in w.sample(w.phases([dict(p,sortie='TEST')]),2):
    if w.margin(pos,w.gateway,'direct')[0]>=0:continue
    blind.append(t)
    if w.margin(pos,np.array(c[0]['position']),'access')[0]>=0:continue
    yes=[w.margin(pos,np.array(z['position']),'access')[0]>=0 for z in c[1:]]
    if yes==[False,False]:failed=True;break
    (both if all(yes) else e if yes[0] else l).append(t)
   if failed:continue
   hard=min((min(b['hard'] or 1e10,b['due'] or 1e10)-p['deliveries'][bid] for bid in ids for b in [pr.boxes[bid]]),default=1e10)
   ans.append((p,min(blind,default=1e10),min(e,default=1e10),max(e,default=-1e10),min(l,default=1e10),both,hard))
  cache[key]=ans;return ans
 def decode(state,end,full=False):
  late=end+c[1]['back']+300+c[2]['earliest_service']+10
  ur={g:[(0,u) for u in pr.units if pr.units[u]==g] for g in 'ABC'};br={g:[(0,b) for b,_ in pr.batts[g]] for g in 'ABC'};finishmax=energy=totalfinish=0;plan=[]
  for g,ids in state:
   ut,u=min(ur[g]);bt,b=min(br[g]);earliest=max(ut,bt);opts=[]
   for p,first,emin,emax,lmin,both,hard in profile(g,ids):
    start=max(earliest,c[0]['earliest_service']+6-first,c[1]['earliest_service']+6-emin,late+6-lmin,0)
    upper=min(hard,end-6-emax)
    for _ in range(5):
     bad=[t for t in both if not(c[1]['earliest_service']+6<=start+t<=end-6 or start+t>=late+6)]
     if not bad:break
     start=max(start,late+6-min(bad))
    else:continue
    if start>upper+1e-8:continue
    opts.append((start+p['finish'],p['energy'],start,p))
   if not opts:return None
   finish,en,start,p=min(opts,key=lambda x:x[:2]);ready=finish+pr.charge(g,p['soc']);ur[g].remove((ut,u));ur[g].append((finish,u));br[g].remove((bt,b));br[g].append((ready,b));finishmax=max(finishmax,finish);energy+=en;totalfinish+=finish
   if full:
    q=pr.evaluate(g,ids,p['route'],start);q.update(unit=u,battery=b,sortie=f'P{len(plan)+1:03d}',charge_start=q['finish'],battery_ready=q['finish']+pr.charge(g,q['soc']));plan.append(q)
  return plan if full else (finishmax,energy,totalfinish)
 seeds=[]
 for pp in [new,old]:
  state=[(p['model'],tuple(p['boxes'])) for p in sorted(pp,key=lambda p:p['start'])]
  for end in [1700,2200,2700,3200,3700]:
   # Urgent early-only visits must be dispatched before late-only visits.
   def urgency(batch):
    pp=profile(*batch);return min((x[3] for x in pp),default=1e10)
   for st in [state,sorted(state,key=urgency,reverse=True)]:
    v=decode(st,end)
    if v:seeds.append((v,st,end));print('SEED',len(pp),end,v,flush=True)
 if not seeds:raise RuntimeError('No calendar seed; search failure, not infeasibility')
 best,state,end=min(seeds);cur=state;cv=best;ce=end;beststate=state;bestend=end;logs=[];it=0
 while time.perf_counter()-t0<180:
  it+=1
  if it%5000==0:cur=list(beststate);cv=best;ce=bestend
  st=list(cur);i,j=rng.sample(range(len(st)),2);eend=ce;kind=rng.randrange(4)
  if kind==0:row=st.pop(i);st.insert(j,row)
  elif kind==1:st[i]=(rng.choice('ABC'),st[i][1])
  elif kind==2:eend=max(1000,min(4000,ce+rng.choice([-100,-30,30,100])))
  else:st[i],st[j]=st[j],st[i]
  v=decode(st,eend)
  if not v:continue
  if v[:2]<best[:2]:best=v;beststate=st;bestend=eend;logs.append((it,v,eend));print('CALENDAR',it,v,eend,flush=True)
  diff=(v[0]+.005*v[2])-(cv[0]+.005*cv[2]);temp=5+40*(1-(it%5000)/5000)
  if diff<0 or rng.random()<math.exp(-min(700,diff/temp)):cur=st;cv=v;ce=eend
 p=decode(beststate,bestend,True);tr=[dict(master=0,early=1,late=2,split=bestend+600)];rr=fit(w,p,c,tr,.5,{})
 dump(OUT/'calendar_search.json',dict(best=best,early_end=bestend,iterations=it,seconds=time.perf_counter()-t0,logs=logs,fit=rr is not None));dump(OUT/'calendar_transport.json',p)
 if rr:
  out=OUT/'q3';s=json.loads((out/'summary.json').read_text(encoding='utf-8'));v=score(pr,p);val=(v[0],rr[0],v[2]+rr[1],len(p)+len(rr[2]));print('FINAL',val,flush=True)
  for name,order in [('baseline',(0,1,2,3)),('makespan_first',(1,0,2,3))]:
   oldv=tuple(s[name][k] for k in ['D','C_joint','total_E','total_N'])
   if tuple(val[k] for k in order)>=tuple(oldv[k] for k in order):continue
   r=rr[2];export(pr,p,out,name);dump(out/name/'relay_plan.json',r);dump(out/name/'phases.json',w.phases(p));s[name]=dict(D=v[0],Cmax=v[1],E=v[2],N=v[3],C_joint=val[1],relay_E=rr[1],total_E=val[2],relay_N=len(r),total_N=val[3],status='PENDING_INDEPENDENT_REPLAY')
   headers=[h for h in list(pr.template['Q3_中继架次'].values)[0] if h]
   csvout(out/name/'Q3_中继架次.csv',[dict(zip(headers,[x['sortie'],x['unit'],x['component'],x['start'],*w.lonlat(*x['position'][:2]),x['position'][2],x['service_start'],x['service_end'],x['finish'],x['energy']])) for x in r])
   csvout(out/name/'relay_resources.csv',[{k:x[k] for k in ['sortie','unit','component','start','takeoff','arrival','service_start','service_end','finish','body_ready','energy','soc','charge_start','component_ready']} for x in r])
  s['calendar_search']=dict(seconds=time.perf_counter()-t0,iterations=it,seed=20260928,positions=[130,511,489],box_groupings='old and improved Q2, type and ordering mutable',all_due_met_as_search_restriction=True);dump(out/'summary.json',s)
 else:print('FINE_FIT_FAILED: retain verified incumbent',flush=True)
if __name__=='__main__':main()
