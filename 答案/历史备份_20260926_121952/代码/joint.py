"""Re-fit complete relay missions to improved transport; retain old solution as bound."""
from pathlib import Path
import sys,json,time,copy
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'outputs/q3'));sys.path.insert(0,str(ROOT/'outputs/q2'))
from solve_joint import fit
from solve_q2 import Problem,score,export
from communication import World,dump,csvout

def main():
 t0=time.perf_counter();src=Path('D:/研一/比赛/中文题目/D题');pre=ROOT/'outputs/preflight';old=ROOT/'outputs/q3';out=Path(__file__).parent/'q3';out.mkdir(parents=True,exist_ok=True)
 pr=Problem(src,pre);w=World(src,pre);c=json.loads((old/'ridge_search/relay_candidates.json').read_text(encoding='utf-8'));triples=json.loads((old/'temporal_expanded.json').read_text(encoding='utf-8'))
 used=sorted({t[k] for t in triples for k in ['master','early','late']});mapping={v:i for i,v in enumerate(used)};c=[dict(c[i],original_candidate=i) for i in used]
 for tr in triples:
  for k in ['master','early','late']:tr[k]=mapping[tr[k]]
 cache={};log=[];opts=[]
 for name in ['baseline','makespan_first']:
  p=json.loads((Path(__file__).parent/'q2'/name/'plan.json').read_text(encoding='utf-8'));v=score(pr,p)
  rr=fit(w,p,c,triples,2,cache);log.append(dict(name=name,dt=2,feasible=rr is not None));print('COARSE',name,rr[:2] if rr else None,flush=True)
  if rr:
   fine=fit(w,p,c,triples,.5,cache);log.append(dict(name=name,dt=.5,feasible=fine is not None));print('FINE',name,fine[:2] if fine else None,flush=True)
   if fine:opts.append(((v[0],fine[0],v[2]+fine[1],len(p)+len(fine[2])),p,fine[2]))
 for name in ['baseline','makespan_first']:
  p=json.loads((old/name/'plan.json').read_text(encoding='utf-8'));r=json.loads((old/name/'relay_plan.json').read_text(encoding='utf-8'));v=score(pr,p);opts.append(((v[0],max(x['finish'] for x in p+r),v[2]+sum(x['energy'] for x in r),len(p)+len(r)),p,r))
 summary={}
 for name,order in [('baseline',(0,1,2,3)),('makespan_first',(1,0,2,3))]:
  val,p,r=min(opts,key=lambda row:tuple(row[0][k] for k in order));export(pr,p,out,name);dump(out/name/'relay_plan.json',r);dump(out/name/'phases.json',w.phases(p));v=score(pr,p)
  summary[name]=dict(D=v[0],Cmax=v[1],E=v[2],N=v[3],C_joint=val[1],relay_E=sum(x['energy'] for x in r),total_E=val[2],relay_N=len(r),total_N=len(p)+len(r),status='PENDING_INDEPENDENT_REPLAY')
  headers=[h for h in list(pr.template['Q3_中继架次'].values)[0] if h]
  csvout(out/name/'Q3_中继架次.csv',[dict(zip(headers,[x['sortie'],x['unit'],x['component'],x['start'],*w.lonlat(*x['position'][:2]),x['position'][2],x['service_start'],x['service_end'],x['finish'],x['energy']])) for x in r])
  csvout(out/name/'relay_resources.csv',[{k:x[k] for k in ['sortie','unit','component','start','takeoff','arrival','service_start','service_end','finish','body_ready','energy','soc','charge_start','component_ready']} for x in r])
 summary['search']=dict(seconds=time.perf_counter()-t0,candidate_locations=len(c),triples=len(triples),transport_candidates=2,relay_structure='one master plus two sequential missions on second body',no_global_proof=True)
 dump(out/'summary.json',summary);dump(out/'search_log.json',log);print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
