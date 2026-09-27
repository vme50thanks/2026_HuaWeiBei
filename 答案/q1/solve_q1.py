"""Q1 exhaustive pattern enumeration + exact finite-state lexicographic DP.
Dependencies: openpyxl. Energy follows explicitly authorized provisional assumptions.
"""
from pathlib import Path
from collections import defaultdict,Counter
from functools import lru_cache
from itertools import product
from decimal import Decimal
import csv,json,math,hashlib,argparse

def readcsv(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def writecsv(p,rows,fields=None):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')

def run(source,pre,out):
    from openpyxl import load_workbook
    out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((pre/'audit.json').read_text(encoding='utf-8'))
    for s in manifest['sources']:
        p=source/Path(s['path']).relative_to(Path(manifest['sources'][0]['path']).parent)
        assert hashlib.sha256(p.read_bytes()).hexdigest()==s['sha256'],str(p)
    def find(n):return next(source.rglob(n))
    ws=load_workbook(find('运输无人机数据.xlsx'),data_only=True).active
    models={}
    for r in list(ws.values)[2:5]:
        names=['g','name','m0','Q','V','vc','L0','LF','Eu','rho_pct','prep','load','base','box','vu','vd','eta','eta_down']
        models[r[0]]=dict(zip(names,r))
    w=load_workbook(find('物资需求与配送时限.xlsx'),data_only=True)
    boxes=[dict(id=r[0],site=r[1],kind=r[2],mass=float(r[3]),volume=float(r[4])) for r in list(w['逐箱货箱清单'].values)[1:] if r[0]]
    assert len(boxes)==80 and len({b['id'] for b in boxes})==80
    agg=Counter({})
    for r in list(w['数据'].values)[1:]:
        if r[0] and isinstance(r[2],(int,float)):agg[(r[0],r[1])]+=r[2]
    assert agg==Counter((b['site'],b['kind']) for b in boxes)
    nodes={r['node_id']:r for r in readcsv(pre/'nodes.csv')}
    nws=load_workbook(find('调度中心与服务区.xlsx'),data_only=True).active
    for r in nws.values:
        if r[0] in nodes:
            for col,key in [(2,'lon_deg'),(3,'lat_deg'),(4,'ground_table_m')]:assert float(r[col])==float(nodes[r[0]][key])
    legs={(r['from_id'],r['to_id']):r for r in readcsv(pre/'legs.csv')}
    ft={(r['from_id'],r['to_id'],r['model_id']):float(r['flight_time_s']) for r in readcsv(pre/'flight_times.csv')}
    for (i,j,g),t in ft.items():
        a=legs[i,j];m=models[g]
        assert abs(t-(float(a['climb_m'])/m['vu']+float(a['horizontal_distance_m'])/m['vc']+float(a['descent_m'])/m['vd']))<1e-8
    def energy(site,g,q):
        m=models[g];go=legs['O01',site];back=legs[site,'O01']
        L=m['L0']-(m['L0']-m['LF'])*(q/m['Q'])**1.5
        eh=m['Eu']*float(go['horizontal_distance_m'])/L
        eu=(m['m0']+q)*9.80665*float(go['climb_m'])/(m['eta']*3.6e6)
        rh=m['Eu']*float(back['horizontal_distance_m'])/m['L0']
        ru=m['m0']*9.80665*float(back['climb_m'])/(m['eta']*3.6e6)
        return eh+eu+rh+ru
    sites=sorted({b['site'] for b in boxes});patterns={};groups={};states={}
    for s in sites:
        attrs=sorted({(b['mass'],b['volume']) for b in boxes if b['site']==s})
        ids=[[b['id'] for b in boxes if b['site']==s and (b['mass'],b['volume'])==a] for a in attrs]
        counts=tuple(map(len,ids));groups[s]=(attrs,ids);states[s]=counts;pp=[]
        for v in product(*(range(n+1) for n in counts)):
            if not any(v):continue
            q=sum(Decimal(str(a[0]))*n for a,n in zip(attrs,v));vol=sum(Decimal(str(a[1]))*n for a,n in zip(attrs,v))
            for g,m in models.items():
                if q>Decimal(str(m['Q'])) or vol>Decimal(str(m['V'])):continue
                e=energy(s,g,float(q));tflight=ft['O01',s,g]+ft[s,'O01',g]
                t=tflight+m['prep']+sum(v)*m['load']+m['base']+sum(v)*m['box']
                pp.append(dict(vector=v,g=g,q=float(q),vol=float(vol),n=sum(v),E=e,T=t,flight=tflight,soc=1-e/m['Eu']))
        patterns[s]=pp
    def solve_site(s,rho,order):
        pp=[p for p in patterns[s] if p['soc']>=rho]
        @lru_cache(None)
        def dp(rem):
            if not any(rem):return ((0,Decimal(0),Decimal(0)),())
            anchor=next(k for k,n in enumerate(rem) if n)
            best=None
            for ix,p in enumerate(pp):
                v=p['vector']
                if not v[anchor] or any(a>b for a,b in zip(v,rem)):continue
                sub=dp(tuple(b-a for a,b in zip(v,rem)))
                if sub is None:continue
                c=sub[0];cost=(c[0]+1,c[1]+Decimal(str(p['E'])),c[2]+Decimal(str(p['T'])))
                key=tuple(cost[k] for k in order)
                if best is None or key<best[0]:best=(key,cost,(ix,)+sub[1])
            return None if best is None else (best[1],best[2])
        ans=dp(states[s])
        missing=[bid for k,idlist in enumerate(groups[s][1]) for bid in idlist if not any(p['vector'][k]>0 for p in pp)]
        return (None if ans is None else [pp[i] for i in ans[1]]),dp.cache_info().currsize,len(pp),missing
    allplans=[];summaries=[];site_results=[];loads=[];certs=[]
    def execute(name,rho,order):
        selected=[];bad=[];unserved=[];cache_total=0
        for s in sites:
            chosen,nstates,npatterns,missing=solve_site(s,rho,order)
            cache_total+=nstates
            certs.append(dict(scenario=name,site=s,feasible_patterns=npatterns,visited_states=nstates,status='INFEASIBLE' if chosen is None else 'OPTIMAL_ENUMERATED_DP'))
            if chosen is None:bad.append(s);unserved+=missing;continue
            ids=[list(v) for v in groups[s][1]]
            for p in chosen:
                used=[]
                for k,n in enumerate(p['vector']):used+=ids[k][:n];ids[k]=ids[k][n:]
                row=dict(scenario=name,rho=rho,sortie=f'{name}-P{len(selected)+1:03d}',site=s,model=p['g'],box_ids=used,mass_kg=p['q'],volume_m3=p['vol'],flight_s=p['flight'],operation_s=p['T'],energy_kWh=p['E'],return_soc=p['soc'])
                selected.append(row)
            site_results.append(dict(scenario=name,rho=rho,site=s,sorties=len(chosen),energy_kWh=math.fsum(p['E'] for p in chosen),operation_s=math.fsum(p['T'] for p in chosen)))
        allplans.extend(selected)
        summary=dict(scenario=name,rho=rho,priority='>'.join(['架次数','能耗','累计作业时间'][i] for i in order),status='INFEASIBLE' if bad else 'OPTIMAL_ENUMERATED_DP',sorties=None if bad else len(selected),energy_kWh=None if bad else math.fsum(p['energy_kWh'] for p in selected),operation_s=None if bad else math.fsum(p['operation_s'] for p in selected),model_counts=dict(Counter(p['model'] for p in selected)),infeasible_sites=';'.join(bad),infeasible_boxes=';'.join(unserved),min_return_soc=min((p['return_soc'] for p in selected),default=None),visited_states=cache_total)
        summaries.append(summary)
        for s in sites:
            for g,m in models.items():
                budget=(1-rho)*m['Eu'];e0=energy(s,g,0)
                if e0>budget:cap=None;status='空载往返不可行';binding='空载能量'
                elif energy(s,g,m['Q'])<=budget:cap=float(m['Q']);status='可行';binding='额定载质量'
                else:
                    lo,hi=0.,float(m['Q'])
                    for _ in range(80):
                        mid=(lo+hi)/2
                        if energy(s,g,mid)<=budget:lo=mid
                        else:hi=mid
                    cap=lo;status='可行';binding='能量'
                loads.append(dict(scenario=name,rho=rho,site=s,model=g,max_safe_payload_kg=cap,status=status,binding=binding,empty_roundtrip_energy_kWh=e0,energy_at_max_kWh=None if cap is None else energy(s,g,cap),rated_payload_kg=m['Q']))
        print(name,json.dumps(summary,ensure_ascii=False),flush=True)
        return selected,summary
    baseline_rhos={m['rho_pct']/100 for m in models.values()}
    assert len(baseline_rhos)==1,'This sensitivity setup requires a common baseline reserve.'
    baseline_rho=baseline_rhos.pop()
    baseline,base=execute('baseline',baseline_rho,(0,1,2))
    execute('energy_first',baseline_rho,(1,0,2));execute('time_first',baseline_rho,(2,0,1))
    for rho in [.1,.15,.25,.3,.4,.5,.6]:execute(f'rho_{round(rho*100):02d}',rho,(0,1,2))
    # Exact bottleneck DP: largest common reserve compatible with <=K sorties.
    thresholds=[]
    for s in sites:
        k=sum(p['site']==s for p in baseline);pp=patterns[s]
        @lru_cache(None)
        def bottleneck(rem,left):
            if not any(rem):return 1.
            if left<=0:return -math.inf
            anchor=next(k for k,n in enumerate(rem) if n);best=-math.inf
            for p in pp:
                v=p['vector']
                if v[anchor] and all(a<=b for a,b in zip(v,rem)):
                    val=bottleneck(tuple(b-a for a,b in zip(v,rem)),left-1)
                    best=max(best,min(p['soc'],val))
            return best
        star=bottleneck(states[s],k);prev=bottleneck(states[s],k-1)
        thresholds.append(dict(site=s,baseline_sorties=k,max_reserve_with_baseline_sorties=star,max_reserve_with_one_fewer_sortie=None if not math.isfinite(prev) else prev))
    global_star=min(r['max_reserve_with_baseline_sorties'] for r in thresholds)
    execute('threshold_below',global_star-1e-7,(0,1,2));execute('threshold_above',global_star+1e-7,(0,1,2))
    dump(out/'solutions.json',allplans);dump(out/'summary.json',summaries)
    writecsv(out/'priority_and_sensitivity.csv',[{**s,'model_counts':json.dumps(s['model_counts'],ensure_ascii=False)} for s in summaries])
    writecsv(out/'safe_payloads_45.csv',[r for r in loads if r['scenario']=='baseline'])
    writecsv(out/'safe_payloads_all_scenarios.csv',loads)
    writecsv(out/'site_results.csv',site_results);writecsv(out/'reserve_thresholds.csv',thresholds);writecsv(out/'optimality_certificates.csv',certs)
    # Template's round-trip time is pure flight; operation total is separately explicit.
    headers=list(load_workbook(find('结果提交模板.xlsx'),data_only=True)['Q1_单点组批'].values)[0]
    result=[]
    for p in baseline:
        result.append(dict(zip(headers,[p['sortie'],p['site'],p['model'],';'.join(p['box_ids']),p['mass_kg'],p['volume_m3'],p['flight_s'],p['energy_kWh'],100*p['return_soc']])))
    writecsv(out/'Q1_单点组批.csv',result)
    writecsv(out/'baseline_details.csv',[{**p,'box_ids':';'.join(p['box_ids'])} for p in baseline])
    dump(out/'run_manifest.json',dict(source=str(source),preflight=str(pre),source_hashes_verified=len(manifest['sources']),preflight_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in pre.iterdir() if p.is_file()},pattern_counts={s:len(pp) for s,pp in patterns.items()},global_trip_threshold=global_star,models=models,solver='Complete multiset-pattern enumeration and memoized lexicographic DP; Decimal sums of binary64 pattern costs',numerics=dict(feasibility_slack=0,capacity_bisection_iterations=80,verification_energy_kWh=1e-8,verification_mass_kg=1e-9,verification_volume_m3=1e-12,verification_time_s=1e-7)))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--preflight',type=Path,required=True);ap.add_argument('--out',type=Path,default=Path(__file__).resolve().parent)
    a=ap.parse_args();run(a.source,a.preflight,a.out)
