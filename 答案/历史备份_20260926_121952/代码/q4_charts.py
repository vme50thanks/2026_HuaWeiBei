from pathlib import Path
import json,csv,argparse,math,importlib.metadata,sys,zipfile,hashlib
from PIL import Image,ImageDraw,ImageFont
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,x):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(x[0]));w.writeheader();w.writerows(x)
F=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
COL=['#217eab','#d67b28','#7c4da9'];LABELS=['A运输机','B运输机','C运输机','A电池','B电池','C电池','中继机','中继组件']
def main(a):
 s=load(a.out/'summary.json');v=load(a.out/'verification.json');bind=load(a.out/'binding_blocks.json');nodes={x['node_id']:x for x in read(a.pre/'nodes.csv')};comp=[];group_rows=[]
 for key,x in s['results'].items():
  comp.append(dict(scenario=key,K=x['K'],mode=x['mode'],G=x['G'],S=x['S'],CV=x['CV'],**dict(zip(s['resource_order'],x['total_resources'])),gap_vector=';'.join(map(str,x['gap'])),extra_relay_N=x['extra_relay_N'],extra_relay_E=x['extra_relay_E'],extra_relay_body_work_s=x['extra_relay_body_work_s'],extra_relay_energy_occupied_s=x['extra_relay_energy_occupied_s']))
  for g in x['groups']:group_rows.append(dict(scenario=key,**{k:(';'.join(val) if k=='sites' else val) for k,val in g.items() if k not in ['resources','mask']}))
  d=a.out/key;tasks=load(d/'tasks.json');cycles=[]
  for t in tasks:
   p=t['frozen'];relay=t['kind']=='relay';cycles.append(dict(group=t['group'],task=t['copy_id'],original_task=t['original_task'],component=t['energy_component'],reserve_start=p['start'],soc_start=1.0,return_s=p['finish'],soc_return=p['soc'],energy_kWh=p['energy'],charge_start=p['finish'],full_ready=p['component_ready'] if relay else p['battery_ready'],soc_ready=1.0))
  write(d/'energy_cycles.csv',cycles)
 write(a.out/'全部方案指标对比.csv',comp);write(a.out/'各组工作量与任务统计.csv',group_rows)
 for K in [2,3]:
  name=f'K{K}_baseline';x=s['results'][name];d=a.out/name;groups=x['groups'];im=Image.new('RGB',(1400,1050),'white');dr=ImageDraw.Draw(im);dr.text((40,25),f'K={K} 服务区分组（不要求地理连通）',fill='#17334c',font=F(29))
  xs=[float(n['x_local_m']) for n in nodes.values()];ys=[float(n['y_local_m']) for n in nodes.values()];scale=min(1170/(max(xs)-min(xs)),690/(max(ys)-min(ys)));xy=lambda n:(110+(float(n['x_local_m'])-min(xs))*scale,840-(float(n['y_local_m'])-min(ys))*scale)
  for gi,g in enumerate(groups):
   for site in g['sites']:
    xx,yy=xy(nodes[site]);dr.ellipse((xx-7,yy-7,xx+7,yy+7),fill=COL[gi]);dr.text((xx+10,yy-15),site,fill=COL[gi],font=F(20))
   dr.text((45,890+gi*36),f"{g['group']}："+'、'.join(g['sites']),fill=COL[gi],font=F(18))
  xx,yy=xy(nodes['O01']);dr.rectangle((xx-7,yy-7,xx+7,yy+7),fill='#333333');dr.text((xx+12,yy-14),'O01',fill='#333333',font=F(20));dr.text((1120,88),'北 ↑',font=F(22),fill='#444444');im.save(d/'分区地图.png')
  alloc=read(d/'resource_assignment.csv');names=sorted({r['resource'] for r in alloc});height=130+len(names)*29;im=Image.new('RGB',(1600,height),'white');dr=ImageDraw.Draw(im);dr.text((35,20),f'K={K} 各组资源占用（含能源补电和中继周转）',fill='#17334c',font=F(26));maxt=max(float(r['end']) for r in alloc);tx=lambda t:300+float(t)/maxt*1230
  for i,rid in enumerate(names):
   y=80+i*29;dr.text((15,y),rid,fill='#273c4d',font=F(15));dr.line((300,y+21,1540,y+21),fill='#e6e6e6')
   for r in alloc:
    if r['resource']==rid:dr.rectangle((tx(r['start']),y,tx(r['end']),y+19),fill=COL[int(r['group'][1:])-1],outline='white');dr.text((tx(r['start'])+2,y),r['task'],font=F(12),fill='white')
  for t in range(0,int(maxt)+1,1000):dr.text((tx(t)-13,height-35),str(t),font=F(16),fill='#444444')
  im.save(d/'各组资源占用图.png')
 im=Image.new('RGB',(1600,720),'white');dr=ImageDraw.Draw(im);dr.text((35,25),'八类资源：库存与两种基准分区需求',font=F(29),fill='#17334c');series=[s['inventory'],s['results']['K2_baseline']['total_resources'],s['results']['K3_baseline']['total_resources']];colors=['#8898a7',COL[0],COL[1]]
 for i,label in enumerate(LABELS):
  center=140+i*180
  for j,vals in enumerate(series):
   h=vals[i]*65;xx=center-55+j*36;dr.rectangle((xx,565-h,xx+30,565),fill=colors[j]);dr.text((xx+7,537-h),str(vals[i]),font=F(18),fill=colors[j])
  dr.text((center-50,590),label,font=F(20),fill='#273c4d')
 for j,name in enumerate(['现有库存','K=2需求','K=3需求']):dr.rectangle((390+j*250,656,410+j*250,676),fill=colors[j]);dr.text((420+j*250,650),name,font=F(22),fill='#273c4d')
 im.save(a.out/'库存与需求对比.png')

if __name__=='__main__':
 import argparse
 a=argparse.Namespace(out=Path(__file__).resolve().parent/'q4',pre=Path(__file__).resolve().parents[2]/'outputs/preflight');main(a)
