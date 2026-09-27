from relay_local import *
from fit_v2 import fit
w=World(Path('D:/研一/比赛/中文题目/D题'),ROOT/'outputs/preflight');pr=Problem(w.source,w.pre);p=load(OUT/'calendar_transport.json');r=load(OUT/'q3/baseline/relay_plan.json');c=[w.relay_trip(*x['position'][:2],x['agl']) for x in r];end=load(OUT/'calendar_search.json')['early_end']
res=fit(w,p,c,[dict(master=0,early=1,late=2,split=end+500)],.5,{})
print('Repaired fit',res[:2] if res else None,flush=True)
if res:save(pr,w,p,res[2],load(OUT/'q3/summary.json'),'joint cargo/calendar search with earliest-service padding boundary corrected')
dump(OUT/'calendar_fit_repair.json',dict(feasible=res is not None,result=res[:2] if res else None,change='Clamp optional 5s pre-service buffer to physically earliest service; still require service before first needed sample. No actual constraint relaxed.'))
