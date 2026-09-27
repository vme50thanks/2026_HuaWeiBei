from relay_local import *
w=World(Path('D:/研一/比赛/中文题目/D题'),ROOT/'outputs/preflight');p=load(OUT/'calendar_transport.json');r=load(OUT/'q3/baseline/relay_plan.json');c=[w.relay_trip(*x['position'][:2],x['agl']) for x in r];rows=[];bad=[]
for ix,t,pos in w.sample(w.phases(p),.5):
 if w.margin(pos,w.gateway,'direct')[0]>=0:continue
 ms=[w.margin(pos,np.array(x['position']),'access')[0] for x in c];cov=[m>=0 for m in ms];rows.append((t,cov))
 if not any(cov):bad.append(dict(t=t,position=pos.tolist(),margins=ms))
end=load(OUT/'calendar_search.json')['early_end'];split=end+500
times=np.array([x[0] for x in rows]);cov=np.array([x[1] for x in rows]);secondary=np.where(times<=split,1,2);ok=cov[np.arange(len(times)),secondary]
print('uncovered_geometry',len(bad),'wrong_time',sum(~(ok|cov[:,0])))
assignment=np.zeros(len(times),dtype=int)
for j in [1,2]:
 required=(secondary==j)&~cov[:,0]
 if required.any():
  lo,hi=times[required].min(),times[required].max();assignment[(times>=lo)&(times<=hi)&cov[:,j]]=j
out=[]
for j,x in enumerate(c):
 tt=times[assignment==j];start=float(tt.min())-5;finish=float(tt.max())+5;out.append(dict(j=j,start=start,end=finish,prepare=start-x['earliest_service'],body_end=finish+x['back']+300,energy=x['travel_energy']+1.1*(finish-start+30)/3600))
print(out);dump(OUT/'calendar_failure_diagnosis.json',dict(uncovered=bad,wrong_calendar_samples=int(sum(~(ok|cov[:,0]))),relay_intervals=out))
