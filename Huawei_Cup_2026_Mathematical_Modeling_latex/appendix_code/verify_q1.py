"""Independent verifier. Does not import solve_q1 or use its energy/time routines.
Reopens original workbooks, reconstructs flight geometry from nodes and DEM maxima,
and uses 45-digit Decimal arithmetic for energies.
"""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal,getcontext
import argparse,csv,json,math
from openpyxl import load_workbook
getcontext().prec=45
D=lambda x:Decimal(str(x))
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def verify(source,pre,out):
    def find(n):return next(source.rglob(n))
    models={r[0]:r for r in list(load_workbook(find('运输无人机数据.xlsx'),data_only=True).active.values)[2:5]}
    boxes={r[0]:r for r in list(load_workbook(find('物资需求与配送时限.xlsx'),data_only=True)['逐箱货箱清单'].values)[1:] if r[0]}
    original_nodes={}
    for r in load_workbook(find('调度中心与服务区.xlsx'),data_only=True).active.values:
        if isinstance(r[0],str) and (r[0]=='O01' or (r[0].startswith('S') and r[0][1:].isdigit())):original_nodes[r[0]]=r
    leg={(r['from_id'],r['to_id']):r for r in read(pre/'legs.csv')}
    geometry=json.loads((pre/'audit.json').read_text(encoding='utf-8'))['local_projection']
    def metrics(site,g,mass,count):
        r=models[g];o=original_nodes['O01'];s=original_nodes[site]
        dx=(s[2]-o[2])*geometry['meters_per_lon_degree'];dy=(s[3]-o[3])*geometry['meters_per_lat_degree']
        distance=math.hypot(dx,dy)
        assert abs(distance-float(leg['O01',site]['horizontal_distance_m']))<1e-7
        cruise=D(leg['O01',site]['dem_max_m'])+50
        up1=cruise-D(o[4]);up2=cruise-D(s[4])-30
        q=D(mass);capacity=D(r[3]);v=q/capacity
        distance_range=D(r[6])-(D(r[6])-D(r[7]))*v*v.sqrt()
        horiz_go=D(r[8])*D(distance)/distance_range
        horiz_back=D(r[8])*D(distance)/D(r[6])
        climb_go=(D(r[2])+q)*D('9.80665')*up1/(D(r[16])*3600000)
        climb_back=D(r[2])*D('9.80665')*up2/(D(r[16])*3600000)
        e=horiz_go+horiz_back+climb_go+climb_back
        flight=(up1+up2)/D(r[14])+(up1+up2)/D(r[15])+2*D(distance)/D(r[5])
        operation=flight+D(r[10])+count*D(r[11])+D(r[12])+count*D(r[13])
        return e,flight,operation,1-e/D(r[8]),[horiz_go,climb_go,horiz_back,climb_back]
    plans=json.loads((out/'solutions.json').read_text(encoding='utf-8'))
    summaries=json.loads((out/'summary.json').read_text(encoding='utf-8'))
    errors=[];checks=[];maxerr=0.;details=[]
    for sm in summaries:
        ps=[p for p in plans if p['scenario']==sm['scenario']];seen=Counter();energies=[];times=[]
        for p in ps:
            bs=[boxes[b] for b in p['box_ids']];seen.update(p['box_ids'])
            assert all(b[1]==p['site'] for b in bs)
            q=sum(D(b[3]) for b in bs);v=sum(D(b[4]) for b in bs);m=models[p['model']]
            assert q<=D(m[3]) and v<=D(m[4])
            e,tf,to,soc,parts=metrics(p['site'],p['model'],q,len(bs))
            assert soc+D('1e-10')>=D(p['rho'])
            assert abs(q-D(p['mass_kg']))<=D('1e-9') and abs(v-D(p['volume_m3']))<=D('1e-12')
            assert abs(e-D(p['energy_kWh']))<=D('1e-8')
            assert abs(tf-D(p['flight_s']))<=D('1e-7') and abs(to-D(p['operation_s']))<=D('1e-7')
            assert abs(soc-D(p['return_soc']))<=D('1e-10')
            maxerr=max(maxerr,float(abs(e-D(p['energy_kWh']))));energies.append(e);times.append(to)
            details.append(dict(scenario=p['scenario'],sortie=p['sortie'],outbound_horizontal_kWh=float(parts[0]),outbound_climb_kWh=float(parts[1]),return_horizontal_kWh=float(parts[2]),return_climb_kWh=float(parts[3]),energy_slack_kWh=float((1-D(p['rho']))*D(m[8])-e),status='PASS'))
        assert all(n==1 for n in seen.values())
        infeasible=[]
        for bid,b in boxes.items():
            available=False
            for g,m in models.items():
                if D(b[3])<=D(m[3]) and D(b[4])<=D(m[4]):
                    e,_,_,soc,_=metrics(b[1],g,b[3],1)
                    if soc>=D(sm['rho']):available=True
            if not available:infeasible.append(bid)
        assert set(infeasible)==set(filter(None,sm['infeasible_boxes'].split(';')))
        if sm['status']!='INFEASIBLE':
            assert set(seen)==set(boxes) and len(ps)==sm['sorties']
            assert abs(sum(energies)-D(sm['energy_kWh']))<D('1e-8')
            assert abs(sum(times)-D(sm['operation_s']))<D('1e-7')
        else:
            assert infeasible
            expected={b for b,r in boxes.items() if r[1] not in sm['infeasible_sites'].split(';')}
            assert set(seen)==expected
        checks.append(dict(scenario=sm['scenario'],checked_sorties=len(ps),checked_boxes=len(seen),full_delivery=sm['status']!='INFEASIBLE',confirmed_untransportable_boxes=len(infeasible),status='PASS'))
    singleton_limits=[]
    for bid,b in boxes.items():
        candidates=[]
        for g,m in models.items():
            if D(b[3])<=D(m[3]) and D(b[4])<=D(m[4]):
                candidates.append((metrics(b[1],g,b[3],1)[3],g))
        best,g=max(candidates)
        singleton_limits.append(dict(box_id=bid,site=b[1],best_singleton_model=g,max_reserve=float(best)))
    with (out/'single_box_reserve_limits.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(singleton_limits[0]));w.writeheader();w.writerows(singleton_limits)
    caps=read(out/'safe_payloads_all_scenarios.csv')
    for r in caps:
        model=models[r['model']];budget=(1-D(r['rho']))*D(model[8])
        if not r['max_safe_payload_kg']:
            assert metrics(r['site'],r['model'],0,0)[0]>budget
        else:
            q=D(r['max_safe_payload_kg']);e=metrics(r['site'],r['model'],q,0)[0]
            assert q<=D(model[3]) and e<=budget+D('1e-8')
            if r['binding']=='能量':
                assert abs(e-budget)<=D('1e-8')
                assert metrics(r['site'],r['model'],q+D('0.00001'),0)[0]>budget
            else:assert q==D(model[3])
    # Independent first-objective lower bound, no DP or solver routines.
    lower=[]
    for s in sorted({b[1] for b in boxes.values()}):
        bs=[b for b in boxes.values() if b[1]==s]
        qm=sum(D(b[3]) for b in bs);vm=sum(D(b[4]) for b in bs)
        n=max(math.ceil(qm/max(D(m[3]) for m in models.values())),math.ceil(vm/max(D(m[4]) for m in models.values())))
        lower.append(dict(site=s,mass_kg=float(qm),volume_m3=float(vm),sortie_lower_bound=n))
    assert sum(r['sortie_lower_bound'] for r in lower)==summaries[0]['sorties']
    with (out/'independent_energy_breakdown.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(details[0]));w.writeheader();w.writerows(details)
    result=dict(status='PASS',independent_of_solver=True,decimal_precision=45,scenarios=checks,payload_rows_checked=len(caps),max_energy_discrepancy_kWh=maxerr,baseline_sortie_lower_bound=sum(r['sortie_lower_bound'] for r in lower),site_lower_bounds=lower,global_full_delivery_reserve_limit=min(r['max_reserve'] for r in singleton_limits),limiting_box=min(singleton_limits,key=lambda r:r['max_reserve']),geometry_note='Original node coordinates and heights plus previously validated DEM path maxima; DEM not rerasterized.',tolerances=dict(energy_kWh=1e-8,mass_kg=1e-9,volume_m3=1e-12,time_s=1e-7,soc=1e-10))
    (out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--source',type=Path,required=True);a.add_argument('--preflight',type=Path,required=True);a.add_argument('--out',type=Path,default=Path(__file__).resolve().parent)
    o=a.parse_args();verify(o.source,o.preflight,o.out)
