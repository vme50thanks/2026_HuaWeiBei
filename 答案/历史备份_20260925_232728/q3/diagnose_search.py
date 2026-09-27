from communication import World,dump,csvout
from pathlib import Path
import numpy as np,json,time,argparse

def main(source,pre,q2,out,spacing=1500,ridge=False):
 out.mkdir(exist_ok=True,parents=True);world=World(source,pre);plan=json.loads((q2/'baseline/plan.json').read_text(encoding='utf-8'));ph=world.phases(plan);samples=world.sample(ph,5)
 t0=time.perf_counter();blind=[];diagnosis=[]
 for ix,t,pos in samples:
  margin,guaranteed=world.margin(pos,world.gateway,'direct')
  if margin<0:blind.append((ix,t,pos))
  diagnosis.append(dict(sortie=ph[ix]['sortie'],phase=ph[ix]['phase'],time=t,x=pos[0],y=pos[1],z=pos[2],direct_margin_dB=margin,worst_obstruction_guaranteed=guaranteed))
 csvout(out/'q2_direct_diagnosis_5s.csv',diagnosis);dump(out/'q2_phases.json',ph)
 unique={};indices=[]
 for ix,t,pos in blind:
  key=tuple(round(float(x),5) for x in pos)
  if key not in unique:unique[key]=len(unique)
  indices.append(unique[key])
 positions=np.array(list(unique));dump(out/'blind_points.json',[dict(phase=ix,time=t,position=pos.tolist(),point_id=pid) for (ix,t,pos),pid in zip(blind,indices)])
 print('samples',len(samples),'blind',len(blind),'unique',len(unique),'thresholds',world.threshold,flush=True)
 # Regular local grid, plus exact service locations, at two heights.
 locations={(float(world.node(n)[0]),float(world.node(n)[1])) for n in world.nodes}
 for x in np.arange(-6000,6001,spacing):
  for y in np.arange(-3000,6501,spacing):locations.add((float(x),float(y)))
 if ridge:
  for x in np.arange(-6000,6001,750):
   for y in np.arange(-4500,6001,750):
    c0,r0=world.grid((x,y));c1,r1=world.grid((x+750,y+750));ra,rb=sorted([int(r0),int(r1)]);ca,cb=sorted([int(c0),int(c1)])
    block=world.dem[ra:rb+1,ca:cb+1];rr,cc=np.unravel_index(np.argmax(block),block.shape);rr+=ra;cc+=ca
    lon=world.west+(cc+.5)*world.dx;lat=world.north-(rr+.5)*world.dy
    locations.add(((lon-world.proj['lon0'])*world.proj['meters_per_lon_degree'],(lat-world.proj['lat0'])*world.proj['meters_per_lat_degree']))
 candidates=[];margins=[]
 for x,y in sorted(locations):
  for agl in [150,300]:
   trip=world.relay_trip(x,y,agl)
   if trip is None:continue
   pos=np.array(trip['position']);backmargin,_=world.margin(pos,world.gateway,'backhaul')
   if backmargin<0:continue
   mm=np.array([world.margin(p,pos,'access')[0] for p in positions]);covered=mm>=0
   trip.update(id=f'RLOC{len(candidates):04d}',backhaul_margin=backmargin,covered=int(covered.sum()))
   candidates.append(trip);margins.append(mm)
 margins=np.array(margins);np.savez_compressed(out/'candidate_margins.npz',margins=margins,positions=positions,indices=np.array(indices))
 dump(out/'relay_candidates.json',candidates)
 n=len(positions);full=(1<<n)-1;bits=[sum(1<<int(k) for k in np.flatnonzero(mm>=0)) for mm in margins]
 pairs=[]
 for i in range(len(bits)):
  if bits[i]==full:pairs.append((i,i))
  for j in range(i+1,len(bits)):
   if bits[i]|bits[j]==full:pairs.append((i,j))
 dump(out/'covering_pairs.json',pairs)
 summary=dict(samples=len(samples),blind_samples=len(blind),unique_blind_positions=n,candidates=len(candidates),max_covered=max(c['covered'] for c in candidates),complete_pairs=len(pairs),spacing_m=spacing,ridge=ridge,elapsed=time.perf_counter()-t0,thresholds=world.threshold)
 dump(out/'diagnosis_summary.json',summary);print(summary,flush=True)

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--source',type=Path,required=True);a.add_argument('--preflight',type=Path,required=True);a.add_argument('--q2',type=Path,required=True);a.add_argument('--out',type=Path,default=Path(__file__).resolve().parent);a.add_argument('--spacing',type=int,default=1500);a.add_argument('--ridge',action='store_true');r=a.parse_args();main(r.source,r.preflight,r.q2,r.out,r.spacing,r.ridge)
