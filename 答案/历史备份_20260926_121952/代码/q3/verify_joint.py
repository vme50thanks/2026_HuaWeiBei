"""Independent original-input replay. No imports from communication or joint optimizer."""
from pathlib import Path
import sys,json,csv,math,argparse,time
import numpy as np
from PIL import Image
from openpyxl import load_workbook
sys.path.insert(0,str(Path(__file__).resolve().parent/'support'))
from verify_q2 import run as transport_check

def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def write(p,x):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(x[0]));w.writeheader();w.writerows(x)
def load(p):return json.loads(p.read_text(encoding='utf-8'))

class Replay:
 def __init__(self,s,pre):
  find=lambda n:next(s.rglob(n));self.proj=load(pre/'audit.json')['local_projection']
  im=Image.open(find('*.tif'));self.dem=np.array(im);dx,dy,_=im.tag_v2[33550];tie=im.tag_v2[33922];assert 2 in im.tag_v2[34735]
  keys=im.tag_v2[34735];raster={keys[i]:keys[i+3] for i in range(4,len(keys),4)};assert raster[1025]==2
  self.west=tie[3]-.5*dx;self.north=tie[4]+.5*dy;self.dx=dx;self.dy=dy
  raw=list(load_workbook(find('调度中心与服务区.xlsx'),data_only=True).active.values)
  self.nodes={}
  for r in raw:
   if isinstance(r[0],str) and (r[0]=='O01' or (r[0].startswith('S') and r[0][1:].isdigit())):
    self.nodes[r[0]]=np.array([(r[2]-self.proj['lon0'])*self.proj['meters_per_lon_degree'],(r[3]-self.proj['lat0'])*self.proj['meters_per_lat_degree'],r[4]+(0 if r[0]=='O01' else 30)])
  rr=list(load_workbook(find('通信链路参数.xlsx'),data_only=True).active.values);p={(r[0],r[1]):r[4] for r in rr[2:] if r[0]}
  self.freq=p['传播参数','载波频率（MHz）'];self.loss=p['传播参数','地形遮挡附加损耗（dB）'];self.limits={}
  for typ,a,b in [('direct','运输无人机','固定网关 G01'),('access','运输无人机','中继接入端'),('backhaul','中继回传端','固定网关 G01')]:
   vals=[p[x,'发射功率（dBm）']+p[a,'天线增益（dBi）']+p[b,'天线增益（dBi）']-p['传播参数','系统损耗（dB）']-p['接收参数','接收灵敏度（dBm）']-p['接收参数','衰落裕量（dB）'] for x in [a,b]];self.limits[typ]=min(vals)
  self.gateway=self.nodes['O01']+np.array([0,0,p['固定网关 G01','天线离地高度（m）']])
  self.rr=list(load_workbook(find('中继无人机数据.xlsx'),data_only=True).active.values);self.r=self.rr[2]
  self.units={r[0] for r in self.rr[6:8]};self.inventory=self.rr[11][1];self.charge=self.rr[11][2]
  self.m={r[0]:r for r in list(load_workbook(find('运输无人机数据.xlsx'),data_only=True).active.values)[2:5]}
  with (pre/'legs.csv').open(encoding='utf-8-sig') as f:self.legs={(r['from_id'],r['to_id']):r for r in csv.DictReader(f)}
 def grid(self,p):
  lon=self.proj['lon0']+p[0]/self.proj['meters_per_lon_degree'];lat=self.proj['lat0']+p[1]/self.proj['meters_per_lat_degree']
  return np.array([(lon-self.west)/self.dx,(self.north-lat)/self.dy])
 def line(self,a,b,spacing):
  g0=self.grid(a);g1=self.grid(b);n=max(1,math.ceil(np.linalg.norm((b-a)[:2])/spacing));t=np.linspace(0,1,n+1)
  grid=g0[:,None]+(g1-g0)[:,None]*t;ij=np.floor(grid).astype(int);z=a[2]+(b[2]-a[2])*t
  return bool(np.any(self.dem[ij[1],ij[0]]>=z-1e-9))
 def exact(self,a,b,onlymax=False):
  a=np.asarray(a);b=np.asarray(b);g0=self.grid(a);g1=self.grid(b);delta=g1-g0;cuts=[0.,1.]
  for dim in [0,1]:
   if abs(delta[dim])>1e-12:
    for k in range(math.ceil(min(g0[dim],g1[dim])),math.floor(max(g0[dim],g1[dim]))+1):
     t=(k-g0[dim])/delta[dim]
     if 0<t<1:cuts.append(t)
  t=np.unique(cuts);mid=(t[1:]+t[:-1])/2;xy=g0[:,None]+delta[:,None]*mid;ij=np.floor(xy).astype(int)
  terrain=self.dem[ij[1],ij[0]];z=a[2]+(b[2]-a[2])*t;maxz=float(terrain.max());blocked=bool(np.any(terrain>=np.minimum(z[:-1],z[1:])-1e-9))
  xy=g0[:,None]+delta[:,None]*t
  for dx,dy in [(1e-8,1e-8),(-1e-8,1e-8),(1e-8,-1e-8),(-1e-8,-1e-8)]:
   ij=np.floor(xy+np.array([dx,dy])[:,None]).astype(int);h=self.dem[ij[1],ij[0]];maxz=max(maxz,float(h.max()));blocked=blocked or bool(np.any(h>=z-1e-9))
  return maxz if onlymax else blocked
 def margin(self,a,b,kind,spacing):
  free=32.45+20*math.log10(self.freq)+20*math.log10(max(np.linalg.norm(a-b)/1000,1e-9));limit=self.limits[kind]
  if free+self.loss<=limit:return limit-free-self.loss
  if free>limit:return limit-free
  obs=self.exact(a,b) if spacing==0 else self.line(a,b,spacing)
  return limit-free-(self.loss if obs else 0)
 def phases(self,plan):
  rows=[]
  for p in plan:
   for k,l in enumerate(p['legs']):
    m=self.m[p['model']];a=self.nodes[l['from_id']];b=self.nodes[l['to_id']];H=float(self.legs[l['from_id'],l['to_id']]['dem_max_m'])+50;t=l['start'];u=np.array([a[0],a[1],H]);v=np.array([b[0],b[1],H])
    for kind,x,y,d in [('爬升',a,u,(H-a[2])/m[14]),('巡航',u,v,np.linalg.norm((b-a)[:2])/m[5]),('下降',v,b,(H-b[2])/m[15])]:
     if d>1e-10:rows.append(dict(sortie=p['sortie'],phase=kind,start=t,end=t+d,a=x.tolist(),b=y.tolist(),site=l['to_id'],from_site=l['from_id'],to_site=l['to_id'],associated_services=';'.join(n for n in [l['from_id'],l['to_id']] if n!='O01')))
     t+=d
    if l['to_id']!='O01':
     stop=p['stops'][k];rows.append(dict(sortie=p['sortie'],phase='交接',start=t,end=stop['complete'],a=b.tolist(),b=b.tolist(),site=l['to_id'],from_site=l['to_id'],to_site=l['to_id'],associated_services=l['to_id']))
  return rows
 def relays(self,plan):
  r=self.r;results=[];phases=[]
  eq=lambda a,b:abs(a-b)<1e-7
  assert len({p['component'] for p in plan})<=self.inventory
  for p in plan:
   assert p['unit'] in self.units;pos=np.array(p['position']);origin=self.nodes['O01'];grid=np.floor(self.grid(pos)).astype(int);ground=float(self.dem[grid[1],grid[0]])
   assert 0<=pos[2]-ground<=r[18]+1e-9
   H=max(self.exact(origin,pos,True)+50,origin[2],pos[2]);assert eq(H,p['cruise'])
   d=np.linalg.norm((pos-origin)[:2]);up=H-origin[2];down=H-pos[2]
   out=up/r[12]+d/r[5]+down/r[13];back=down/r[12]+d/r[5]+up/r[13]
   assert eq(p['takeoff'],p['start']+r[9]) and eq(p['arrival'],p['takeoff']+out) and eq(p['service_start'],p['arrival']+r[10]) and eq(p['finish'],p['service_end']+back)
   assert p['start']>=0 and p['service_end']>=p['service_start'];assert eq(p['body_ready'],p['finish']+r[11])
   horizontal=2*r[6]*d/r[5]/3600;climb=r[4]*9.80665*(up+down)/(r[14]*3600000);link=(r[16]+r[17])*r[10]/3600;service=(r[16]+r[17])*(p['service_end']-p['service_start'])/3600
   E=horizontal+climb+link+service;soc=1-E/r[7];assert abs(E-p['energy'])<1e-8 and abs(soc-p['soc'])<1e-10 and soc>=r[8]/100-1e-10
   chg=self.charge*(.65*(.9-soc)/.9+.35) if soc<.9 else self.charge*.35*(1-soc)/.1
   assert eq(p['charge_start'],p['finish']) and eq(p['component_ready'],p['finish']+chg)
   bm=self.margin(pos,self.gateway,'backhaul',0);assert bm>=0
   results.append(dict(sortie=p['sortie'],horizontal_kWh=horizontal,climb_kWh=climb,link_kWh=link,service_kWh=service,total_kWh=E,soc=soc,backhaul_margin_db=bm,terrain_max_m=H-50))
   for direction,a,b,begin in [('去程',origin,pos,p['takeoff']),('返程',pos,origin,p['service_end'])]:
    topa=np.array([a[0],a[1],H]);topb=np.array([b[0],b[1],H]);t=begin
    for kind,x,y,duration in [('爬升',a,topa,(H-a[2])/r[12]),('巡航',topa,topb,d/r[5]),('下降',topb,b,(H-b[2])/r[13])]:
     phases.append(dict(sortie=p['sortie'],phase=direction+kind,start=t,end=t+duration,a=x.tolist(),b=y.tolist()));t+=duration
   phases.append(dict(sortie=p['sortie'],phase='建链',start=p['arrival'],end=p['service_start'],a=pos.tolist(),b=pos.tolist()));phases.append(dict(sortie=p['sortie'],phase='服务',start=p['service_start'],end=p['service_end'],a=pos.tolist(),b=pos.tolist()))
  for resource,endfield in [('unit','body_ready'),('component','component_ready')]:
   for key in {p[resource] for p in plan}:
    seq=sorted([p for p in plan if p[resource]==key],key=lambda p:p['start']);assert all(x[endfield]<=y['start']+1e-7 for x,y in zip(seq,seq[1:]))
  return results,phases
 def scan(self,phases,relays,dt,spacing,detail=False):
  back={r['sortie']:self.margin(np.array(r['position']),self.gateway,'backhaul',spacing) for r in relays};rows=[];coverage=[];transitions=[];worst=None;bad=[];n=0
  for ph in phases:
   a=np.array(ph['a']);b=np.array(ph['b']);start,end=ph['start'],ph['end']
   def rawstate(t):
    pos=a+(b-a)*(t-start)/(end-start);direct=self.margin(pos,self.gateway,'direct',spacing)
    if direct>=-1e-9:return 'G01',direct,direct,pos
    avail=[(min(self.margin(pos,np.array(r['position']),'access',spacing),back[r['sortie']]),r['sortie']) for r in relays if r['service_start']-1e-8<=t<=r['service_end']+1e-8]
    m,provider=max(avail,default=(-999,'NONE'));return provider if m>=-1e-9 else 'NONE',m,direct,pos
   memo={}
   def state(t):
    if t not in memo:memo[t]=rawstate(t)
    return memo[t]
   times=set(np.linspace(start,end,max(1,math.ceil((end-start)/dt))+1).tolist())
   times.update(t for r in relays for t in [r['service_start'],r['service_end']] if start<t<end)
   if detail:
    base=sorted(times)
    for left,right in zip(base,base[1:]):
     sl=state(left);sr=state(right)
     if min(sl[1],sr[1])<.02 or sl[0]!=sr[0]:
      times.update(np.linspace(left,right,max(1,math.ceil((right-left)/.05))+1).tolist())
   prev=None;segment=start
   for t in sorted(times):
    provider,m,direct,pos=state(t);n+=1
    if provider=='NONE':bad.append(dict(sortie=ph['sortie'],phase=ph['phase'],time=t,margin=m))
    if worst is None or m<worst['margin_db']:worst=dict(sortie=ph['sortie'],phase=ph['phase'],time_s=t,margin_db=m,provider=provider)
    if detail:
     rows.append(dict(sortie=ph['sortie'],phase=ph['phase'],time_s=t,x_m=pos[0],y_m=pos[1],z_m=pos[2],provider=provider,margin_db=m,direct_margin_db=direct))
     if prev and provider!=prev[1]:
      lo=prev[0];hi=t
      for _ in range(30):
       if hi-lo<1e-7:break
       mid=(lo+hi)/2
       if state(mid)[0]==prev[1]:lo=mid
       else:hi=mid
      cut=(lo+hi)/2;transitions.append(dict(sortie=ph['sortie'],phase=ph['phase'],lo=lo,hi=hi,old=prev[1],new=provider))
      coverage.append(dict(sortie=ph['sortie'],phase=ph['phase'],start=segment,end=cut,provider=prev[1],site=ph['site'],from_site=ph['from_site'],to_site=ph['to_site'],associated_services=ph['associated_services']));segment=cut
    prev=(t,provider)
   if detail:coverage.append(dict(sortie=ph['sortie'],phase=ph['phase'],start=segment,end=end,provider=prev[1],site=ph['site'],from_site=ph['from_site'],to_site=ph['to_site'],associated_services=ph['associated_services']))
  return dict(dt_s=dt,spatial_spacing_m=spacing if spacing else 'all crossed cells and touched corners',points=n,failed_points=len(bad),worst=worst,claim='在所述时空分辨率下未发现中断' if not bad else '发现通信中断采样点'),rows,coverage,transitions,bad

def main(a):
 t0=time.perf_counter();transport_check(a.source,a.preflight,a.out);v=Replay(a.source,a.preflight);summary=load(a.out/'summary.json');reports={}
 for name in ['baseline','makespan_first']:
  path=a.out/name;p=load(path/'plan.json');r=load(path/'relay_plan.json');energy,rph=v.relays(r);ph=v.phases(p);scans=[]
  for dt,spacing in [(1,5),(.5,2.5),(.5,0)]:
   result,rows,cov,trans,bad=v.scan(ph,r,dt,spacing,spacing==0);scans.append(result);print(name,result,flush=True)
   if bad:dump(path/'failed_communication.json',bad);raise AssertionError('communication failure; repair required')
   if spacing==0:
    write(path/'communication_samples.csv',rows);write(path/'switch_brackets.csv',trans)
    headers=['运输架次编号','通信阶段','开始时刻（s）','结束时刻（s）','保障方式','中继架次编号']
    write(path/'Q3_通信保障.csv',[dict(zip(headers,[x['sortie'],x['phase'],x['start'],x['end'],'直连' if x['provider']=='G01' else '中继','' if x['provider']=='G01' else x['provider']])) for x in cov])
    write(path/'q4_associations.csv',cov)
  write(path/'relay_energy_check.csv',energy);dump(path/'relay_phases.json',rph);dump(path/'independent_transport_phases.json',ph)
  events=[]
  for x in r:
   for field,event in [('start','RESERVE_BODY_AND_FULL_COMPONENT'),('service_start','LINK_READY'),('service_end','SERVICE_END'),('finish','LAND_AND_BEGIN_CHARGE'),('body_ready','BODY_READY'),('component_ready','COMPONENT_FULL')]:
    events.append(dict(time_s=x[field],event=event,sortie=x['sortie'],unit=x['unit'],component=x['component']))
  write(path/'relay_event_replay.csv',sorted(events,key=lambda x:(x['time_s'],x['event'])))
  write(path/'uncertified_continuous_intervals.csv',[{k:x[k] for k in ['sortie','phase','start','end']} for x in ph])
  joint=max([x['finish'] for x in p+r]);er=sum(x['total_kWh'] for x in energy);assert abs(joint-summary[name]['C_joint'])<1e-7 and abs(er-summary[name]['relay_E'])<1e-8
  reports[name]=dict(status='PASS_AT_REPORTED_RESOLUTIONS',scans=scans,relay_energy_kWh=er,C_joint=joint,relay_sorties=len(r),relay_units=sorted({x['unit'] for x in r}),relay_components=sorted({x['component'] for x in r}),continuous_mathematical_certificate=False,uncertified_phase_intervals=len(ph),relay_checks='original inputs, independent terrain traversal, energy decomposition, device/component intervals and recharge')
 reports['seconds']=time.perf_counter()-t0;reports['tolerances']=dict(time_s=1e-7,energy_kWh=1e-8,soc=1e-10,link_db=1e-9);dump(a.out/'joint_verification.json',reports)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--preflight',type=Path,required=True);p.add_argument('--out',type=Path,required=True);main(p.parse_args())
