"""Bounded local search, reassigns every batch to machine/battery after mutations."""
from solve_q2 import Problem,score,export,dump
from pathlib import Path
import argparse,json,random,time

def decode(pr,batches,k):
 ready={u:0. for u in pr.units};br={b:0. for v in pr.batts.values() for b,_ in v};plan=[]
 for ids in batches:
  options=[]
  for g in 'ABC':
   u=min((u for u in ready if pr.units[u]==g),key=lambda u:(ready[u],u))
   bat=min(pr.batts[g],key=lambda x:(br[x[0]],x[0]))[0];start=max(ready[u],br[bat])
   a=pr.best_route(g,ids,start,k)
   if a:
    delay=sum(pr.boxes[b]['weight']*max(0,t-pr.boxes[b]['due']) for b,t in a['deliveries'].items() if pr.boxes[b]['due'] is not None)
    options.append(((delay,a['finish'],a['energy']),u,bat,a))
  if not options:return None
  _,u,bat,a=min(options,key=lambda x:x[0]);a.update(unit=u,battery=bat,sortie=f'P{len(plan)+1:03d}')
  a['charge_start']=a['finish'];a['battery_ready']=a['finish']+pr.charge(a['model'],a['soc'])
  ready[u]=a['finish'];br[bat]=a['battery_ready'];plan.append(a)
 return plan

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--preflight',type=Path,required=True);ap.add_argument('--out',type=Path,default=Path(__file__).resolve().parent);ap.add_argument('--seconds',type=float,default=90);ap.add_argument('--iterations',type=int,default=5000)
 args=ap.parse_args();pr=Problem(args.source,args.preflight);s=json.loads((args.out/'summary.json').read_text(encoding='utf-8'));best={}
 for name,order in [('baseline',(0,1,2,3)),('makespan_first',(1,0,2,3))]:
  p=json.loads((args.out/name/'plan.json').read_text(encoding='utf-8'));v=score(pr,p);best[name]=(tuple(v[k] for k in order),p,v)
 rng=random.Random(20260923);start=time.perf_counter();logs=[]
 seedbatches=[a['boxes'] for a in sorted(best['baseline'][1],key=lambda a:(a['start'],a['sortie']))]
 current=seedbatches
 for it in range(args.iterations):
  if time.perf_counter()-start>args.seconds:break
  if it%100==0:current=[a['boxes'] for a in sorted(best['baseline'][1],key=lambda a:(a['start'],a['sortie']))]
  candidate=[list(v) for v in current];i,j=rng.sample(range(len(candidate)),2);action=rng.randrange(4)
  if action==0:candidate[i],candidate[j]=candidate[j],candidate[i]
  elif action==1:
   box=candidate[i].pop(rng.randrange(len(candidate[i])));candidate[j].append(box);candidate=[v for v in candidate if v]
  elif action==2:
   a=rng.randrange(len(candidate[i]));b=rng.randrange(len(candidate[j]));candidate[i][a],candidate[j][b]=candidate[j][b],candidate[i][a]
  else:
   candidate[min(i,j)]+=candidate[max(i,j)];candidate.pop(max(i,j))
  if any(len({pr.boxes[b]['site'] for b in batch})>3 for batch in candidate):continue
  plan=decode(pr,candidate,3)
  if plan is None:continue
  value=score(pr,plan);logs.append(dict(iteration=it,D=value[0],Cmax=value[1],E=value[2],N=value[3]))
  improved=False
  for name,order in [('baseline',(0,1,2,3)),('makespan_first',(1,0,2,3))]:
   key=tuple(value[k] for k in order)
   if key<best[name][0]:
    best[name]=(key,plan,value);improved=True
    print(name,it,value,flush=True)
  if improved or rng.random()<.015:current=candidate
 for name,(_,plan,value) in best.items():
  export(pr,plan,args.out,name)
  s[name]=dict(D=value[0],Cmax=value[1],E=value[2],N=value[3],status='VERIFIABLE_HEURISTIC_INCUMBENT',maxstops=max(len(a['route']) for a in plan),multi_stop_sorties=sum(len(a['route'])>1 for a in plan),search='constructive pool plus local mutations with reassignment')
 s['local_search']=dict(seed=20260923,iterations_attempted=it+1,feasible_candidates=len(logs),seconds=time.perf_counter()-start,time_limit=args.seconds,iteration_limit=args.iterations,maxstops=3)
 dump(args.out/'summary.json',s);dump(args.out/'local_search_log.json',logs)

if __name__=='__main__':main()
