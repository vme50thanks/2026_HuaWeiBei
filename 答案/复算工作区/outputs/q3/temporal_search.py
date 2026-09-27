"""Search one persistent relay + two sequential sorties of the second relay."""
from pathlib import Path
import json,numpy as np,time,argparse
from communication import dump

def search(folder,out,keep=100):
 m=np.load(folder/'candidate_margins.npz')['margins'];c=json.loads((folder/'relay_candidates.json').read_text(encoding='utf-8'));rows=json.loads((folder/'blind_points.json').read_text(encoding='utf-8'))
 order=np.argsort([r['time'] for r in rows]);times=np.array([rows[i]['time'] for i in order]);pids=np.array([rows[i]['point_id'] for i in order]);cov=m[:,pids]>=0
 ready=np.array([x['earliest_service'] for x in c]);back=np.array([x['back'] for x in c]);t0=time.perf_counter();best=[]
 for master in range(len(c)):
  need=np.flatnonzero(~cov[master]);t=times[need]
  if not len(need):continue
  cc=cov[:,need];fails=~cc
  first=np.where(fails.any(axis=1),fails.argmax(axis=1),len(need))
  last=np.where(fails.any(axis=1),len(need)-1-fails[:,::-1].argmax(axis=1),-1)
  # Only boundaries with a positive time gap; assignments before/after are unambiguous.
  for k in np.flatnonzero(np.diff(t)>1):
   e=np.flatnonzero((first>k)&(ready<=t[0]))
   l=np.flatnonzero((last<=k)&(ready<=t[k+1]))
   if not len(e) or not len(l):continue
   for i in e:
    avail=t[k]+back[i]+300+ready[l]
    feasible=l[avail<=t[k+1]]
    for j in feasible:
     if master in (i,j):continue
     # Persistent relay only needs points not served by secondary over the two windows.
     needed_master=~np.where(times<=t[k],cov[i],cov[j])
     tm=times[needed_master]
     if not len(tm) or ready[master]>tm.min():continue
     intervals=[(master,float(tm.min()),float(tm.max())),(int(i),float(t[0]),float(t[k])),(int(j),float(t[k+1]),float(t[-1]))]
     energy=[c[a]['travel_energy']+1.1*(end-start+30)/3600 for a,start,end in intervals]
     if max(energy)>2.56:continue
     finish=max(end+c[a]['back'] for a,start,end in intervals)
     best.append(dict(master=master,early=int(i),late=int(j),intervals=intervals,energy=sum(energy),relay_finish=finish,split=float((t[k]+t[k+1])/2)))
 best.sort(key=lambda r:(r['relay_finish'],r['energy']));dump(out,best[:keep]);print('temporal candidates',len(best),'seconds',time.perf_counter()-t0,flush=True)
 if best:print(best[0],flush=True)

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--folder',type=Path,required=True);a.add_argument('--out',type=Path,required=True);a.add_argument('--keep',type=int,default=100);r=a.parse_args();search(r.folder,r.out,r.keep)
