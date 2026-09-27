"""Piecewise-linear flight trajectories and conservative exact-cell DEM ray tests."""
from pathlib import Path
import csv,json,math
import numpy as np
from PIL import Image
from openpyxl import load_workbook

def read(p):
 with p.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def csvout(p,rows,fields=None):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)

class World:
 def __init__(self,source,pre):
  self.source=source;self.pre=pre;self.nodes={r['node_id']:r for r in read(pre/'nodes.csv')}
  self.proj=json.loads((pre/'audit.json').read_text(encoding='utf-8'))['local_projection']
  im=Image.open(next(source.rglob('*.tif')));self.dem=np.array(im,dtype=float)
  dx,dy=im.tag_v2[33550][:2];tie=im.tag_v2[33922];self.dx=dx;self.dy=dy;self.west=tie[3]-dx/2;self.north=tie[4]+dy/2
  self.legs={(r['from_id'],r['to_id']):r for r in read(pre/'legs.csv')}
  rr=list(load_workbook(next(source.rglob('运输无人机数据.xlsx')),data_only=True).active.values);self.models={r[0]:r for r in rr[2:5]}
  self.relay=list(load_workbook(next(source.rglob('中继无人机数据.xlsx')),data_only=True).active.values)[2]
  rr=list(load_workbook(next(source.rglob('通信链路参数.xlsx')),data_only=True).active.values)
  params={(r[0],r[1]):r[4] for r in rr[2:] if r[0]}
  self.f=params['传播参数','载波频率（MHz）'];self.loss=params['传播参数','系统损耗（dB）'];self.obs=params['传播参数','地形遮挡附加损耗（dB）']
  sensitivity=params['接收参数','接收灵敏度（dBm）']+params['接收参数','衰落裕量（dB）']
  def endpoint(cat):return (params[cat,'发射功率（dBm）'],params[cat,'天线增益（dBi）'])
  ep={name:endpoint(cat) for name,cat in [('T','运输无人机'),('RA','中继接入端'),('RB','中继回传端'),('G','固定网关 G01')]}
  self.threshold={}
  for typ,a,b in [('direct','T','G'),('access','T','RA'),('backhaul','RB','G')]:
   pt,ga=ep[a];pb,gb=ep[b];self.threshold[typ]=min(pt+ga+gb-self.loss-sensitivity,pb+gb+ga-self.loss-sensitivity)
  self.o=self.node('O01');self.gateway=self.o+np.array([0,0,params['固定网关 G01','天线离地高度（m）']])
 def node(self,n):
  r=self.nodes[n];return np.array([float(r['x_local_m']),float(r['y_local_m']),float(r['operation_alt_m'])])
 def lonlat(self,x,y):return (self.proj['lon0']+x/self.proj['meters_per_lon_degree'],self.proj['lat0']+y/self.proj['meters_per_lat_degree'])
 def grid(self,p):
  lon,lat=self.lonlat(p[0],p[1]);return ((lon-self.west)/self.dx,(self.north-lat)/self.dy)
 def terrain(self,x,y):
  c,r=self.grid((x,y));ri,ci=math.floor(r),math.floor(c)
  if not (0<=ri<self.dem.shape[0] and 0<=ci<self.dem.shape[1]):return None
  return float(self.dem[ri,ci])
 def ray_cells(self,a,b):
  x0,y0=self.grid(a);x1,y1=self.grid(b);ts=[np.array([0.,1.])]
  for s,e in [(x0,x1),(y0,y1)]:
   if abs(e-s)>1e-12:
    t=(np.arange(math.ceil(min(s,e)),math.floor(max(s,e))+1)-s)/(e-s);ts.append(t[(t>0)&(t<1)])
  t=np.unique(np.concatenate(ts));mid=(t[:-1]+t[1:])/2
  cs=np.floor(x0+(x1-x0)*mid).astype(int);rs=np.floor(y0+(y1-y0)*mid).astype(int)
  if len(mid)==0:cs=np.array([math.floor(x0)]);rs=np.array([math.floor(y0)]);t=np.array([0.,1.])
  assert np.all((rs>=0)&(rs<self.dem.shape[0])&(cs>=0)&(cs<self.dem.shape[1]))
  return t,rs,cs
 def margin(self,a,b,typ,method='cells',spacing=5):
  distance=float(np.linalg.norm(a-b));free=32.45+20*math.log10(self.f)+20*math.log10(max(distance/1000,1e-9));limit=self.threshold[typ]
  if free+self.obs<=limit:return limit-free-self.obs,True # conservative regardless of obstruction
  if free>limit:return limit-free,False
  if method=='sample':
   n=max(1,math.ceil(float(np.linalg.norm((a-b)[:2]))/spacing));ts=np.linspace(0,1,n+1)
   x0,y0=self.grid(a);x1,y1=self.grid(b);cs=np.floor(x0+(x1-x0)*ts).astype(int);rs=np.floor(y0+(y1-y0)*ts).astype(int)
   blocked=bool(np.any(self.dem[rs,cs]>=a[2]+(b[2]-a[2])*ts-1e-9))
  else:
   t,rs,cs=self.ray_cells(a,b);z=a[2]+(b[2]-a[2])*t
   blocked=bool(np.any(self.dem[rs,cs]>=np.minimum(z[:-1],z[1:])-1e-9))
   # Boundary/corner touches conservatively include all adjacent cell samples.
   x0,y0=self.grid(a);x1,y1=self.grid(b);xx=x0+(x1-x0)*t;yy=y0+(y1-y0)*t
   for dc,dr in [(1e-8,1e-8),(-1e-8,1e-8),(1e-8,-1e-8),(-1e-8,-1e-8)]:
    cc=np.floor(xx+dc).astype(int);rr=np.floor(yy+dr).astype(int)
    blocked=blocked or bool(np.any(self.dem[rr,cc]>=z-1e-9))
  return limit-free-(self.obs if blocked else 0),False
 def phases(self,plan):
  rows=[]
  for p in plan:
   m=self.models[p['model']]
   for k,leg in enumerate(p['legs']):
    a=self.node(leg['from_id']);b=self.node(leg['to_id']);h=float(self.legs[leg['from_id'],leg['to_id']]['cruise_alt_m']);t=leg['start']
    topa=np.array([a[0],a[1],h]);topb=np.array([b[0],b[1],h])
    for kind,u,v,duration in [('爬升',a,topa,(h-a[2])/m[14]),('巡航',topa,topb,float(self.legs[leg['from_id'],leg['to_id']]['horizontal_distance_m'])/m[5]),('下降',topb,b,(h-b[2])/m[15])]:
     if duration>1e-10:rows.append(dict(sortie=p['sortie'],phase=kind,start=t,end=t+duration,a=u.tolist(),b=v.tolist(),from_id=leg['from_id'],to_id=leg['to_id']))
     t+=duration
    if leg['to_id']!='O01':
     stop=p['stops'][k];rows.append(dict(sortie=p['sortie'],phase='交接',start=stop['arrival'],end=stop['complete'],a=b.tolist(),b=b.tolist(),from_id=leg['to_id'],to_id=leg['to_id']))
  return rows
 def sample(self,phases,dt):
  rows=[]
  for ix,ph in enumerate(phases):
   n=max(1,math.ceil((ph['end']-ph['start'])/dt));a=np.array(ph['a']);b=np.array(ph['b'])
   for t in np.linspace(ph['start'],ph['end'],n+1):
    pos=a+(b-a)*(t-ph['start'])/(ph['end']-ph['start']);rows.append((ix,float(t),pos))
  return rows
 def relay_trip(self,x,y,agl):
  z=self.terrain(x,y)
  if z is None:return None
  pos=np.array([x,y,z+agl]);t,rs,cs=self.ray_cells(self.o,pos)
  maxz=float(self.dem[rs,cs].max());x0,y0=self.grid(self.o);x1,y1=self.grid(pos)
  for dc,dr in [(1e-8,1e-8),(-1e-8,1e-8),(1e-8,-1e-8),(-1e-8,-1e-8)]:
   cc=np.floor(x0+(x1-x0)*t+dc).astype(int);rr=np.floor(y0+(y1-y0)*t+dr).astype(int);maxz=max(maxz,float(self.dem[rr,cc].max()))
  H=max(maxz+50,self.o[2],pos[2]);m=self.relay
  dist=math.hypot(x-self.o[0],y-self.o[1]);fly=(H-self.o[2])/m[12]+dist/m[5]+(H-pos[2])/m[13]
  back=(H-pos[2])/m[12]+dist/m[5]+(H-self.o[2])/m[13]
  travelE=2*m[6]*dist/m[5]/3600+m[4]*9.80665*((H-self.o[2])+(H-pos[2]))/(m[14]*3.6e6)
  return dict(position=pos.tolist(),agl=agl,ground=z,cruise=H,distance=dist,fly=fly,back=back,travel_energy=travelE,earliest_service=m[9]+fly+m[10])
