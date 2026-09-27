import numpy as np
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
    c=candidates[idx];start=max(c['earliest_service'],float(tt.min())-5);end=float(tt.max())+5
    if start>float(tt.min()):break
    prep=start-c['earliest_service'];en=c['travel_energy']+1.1*(end-start+30)/3600
    if prep<0 or en>2.56:break
    soc=1-en/3.2;chg=1800*(.65*(.9-soc)/.9+.35) if soc<.9 else 1800*.35*(1-soc)/.1
    relay.append(dict(**c,candidate=idx,sortie=f'R{j+1:03d}',unit='R01' if j==0 else 'R02',component=f'R-ENE-{j+1:02d}',start=prep,takeoff=prep+180,arrival=start-30,service_start=start,service_end=end,finish=end+c['back'],body_ready=end+c['back']+300,energy=en,soc=soc,charge_start=end+c['back'],component_ready=end+c['back']+chg))
   if len(relay)!=3 or relay[1]['body_ready']>relay[2]['start']:continue
   finish=max(max(p['finish'] for p in plan),max(r['finish'] for r in relay));en=sum(r['energy'] for r in relay)
   options.append((finish,en,relay))
 return min(options,key=lambda r:r[:2]) if options else None
