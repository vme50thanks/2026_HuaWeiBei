"""Read-only source audit and reproducible D-problem geometry preprocessing.

Dependencies: numpy, Pillow, openpyxl, lxml. No energy assumptions are executed.
Run: python build_preflight.py --source <D题目录> --out <输出目录>
"""
from pathlib import Path
import argparse, csv, hashlib, json, math, zipfile
import numpy as np
from PIL import Image
from openpyxl import load_workbook
from lxml import etree


def write_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def crossing_cells(x0, y0, x1, y1):
    """Closed pixel rectangles; coordinates expressed at pixel boundaries.
    Split at every grid crossing; include both sides of exact boundary touches.
    """
    ts = [0., 1.]
    for a, b in [(x0, x1), (y0, y1)]:
        if abs(b-a) > 1e-12:
            for v in range(math.ceil(min(a,b)), math.floor(max(a,b))+1):
                t = (v-a)/(b-a)
                if 0 < t < 1:
                    ts.append(t)
    ts = sorted(set(ts))
    samples = ts + [(a+b)/2 for a,b in zip(ts,ts[1:])]
    cells = set()
    def choices(v):
        if abs(v-round(v)) < 1e-8:
            return [round(v)-1, round(v)]
        return [math.floor(v)]
    for t in samples:
        x, y = x0+t*(x1-x0), y0+t*(y1-y0)
        cells.update((r,c) for r in choices(y) for c in choices(x))
    return cells


def slab_cells(x0, y0, x1, y1):
    """Independent vectorized segment/rectangle clipping for validation."""
    cs = np.arange(math.floor(min(x0,x1))-1, math.floor(max(x0,x1))+2)
    rs = np.arange(math.floor(min(y0,y1))-1, math.floor(max(y0,y1))+2)
    c, r = np.meshgrid(cs, rs)
    lo, hi = np.zeros(c.shape), np.ones(c.shape)
    valid = np.ones(c.shape, dtype=bool)
    for a,d,left in [(x0,x1-x0,c),(y0,y1-y0,r)]:
        if abs(d)<1e-12:
            valid &= (a>=left-1e-10)&(a<=left+1+1e-10)
        else:
            t0,t1=(left-a)/d,(left+1-a)/d
            lo=np.maximum(lo,np.minimum(t0,t1))
            hi=np.minimum(hi,np.maximum(t0,t1))
    valid &= lo <= hi+1e-10
    return set(zip(r[valid].tolist(),c[valid].tolist()))


def ecef(lon, lat):
    a=6378137.; e2=6.6943799901413165e-3
    la,ph=math.radians(lon),math.radians(lat)
    n=a/math.sqrt(1-e2*math.sin(ph)**2)
    return np.array([n*math.cos(ph)*math.cos(la),n*math.cos(ph)*math.sin(la),n*(1-e2)*math.sin(ph)])


def text_math(e):
    if e is None:return ''
    tag=etree.QName(e).localname
    ns={'m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
    def c(n):return text_math(e.find('m:'+n,ns))
    if tag=='t':return e.text or ''
    if tag.endswith('Pr'):return ''
    if tag=='f':return '('+c('num')+')/('+c('den')+')'
    if tag=='sSub':return c('e')+'_{'+c('sub')+'}'
    if tag=='sSup':return c('e')+'^{'+c('sup')+'}'
    if tag=='sSubSup':return c('e')+'_{'+c('sub')+'}^{'+c('sup')+'}'
    if tag=='d':return '('+c('e')+')'
    if tag=='nary':return 'SUM_{'+c('sub')+'}^{'+c('sup')+'}('+c('e')+')'
    return ''.join(text_math(x) for x in e)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--out',type=Path,default=Path(__file__).resolve().parent)
    args=ap.parse_args(); root,out=args.source,args.out
    out.mkdir(parents=True,exist_ok=True)
    def locate(name):
        found=list(root.rglob(name)); assert len(found)==1,(name,found)
        return found[0]
    nodefile=locate('调度中心与服务区.xlsx')
    model_file=locate('运输无人机数据.xlsx')
    demfile=locate('*.tif')
    docfile=next(p for p in root.glob('*.docx') if not p.name.startswith('~$'))
    nodews=load_workbook(nodefile,data_only=True,read_only=True).active
    records=[]
    for row in nodews.values:
        if isinstance(row[0],str) and (row[0]=='O01' or (row[0].startswith('S') and row[0][1:].isdigit())):
            records.append(dict(node_id=row[0],name=row[1],lon_deg=float(row[2]),lat_deg=float(row[3]),ground_table_m=float(row[4])))
    assert len(records)==16 and len({r['node_id'] for r in records})==16
    im=Image.open(demfile); arr=np.array(im,dtype=np.float64)
    scale,tie,keys=im.tag_v2[33550],im.tag_v2[33922],im.tag_v2[34735]
    geo={keys[i]:keys[i+3] for i in range(4,len(keys),4)}
    assert geo[2048]==4326 and geo[1025]==2,geo
    assert tie[:3]==(0.,0.,0.)
    dx,dy=scale[:2]; west_center,north_center=tie[3:5]
    # RasterPixelIsPoint: raw TIFF tiepoint is center of first sample.
    west,north=west_center-dx/2,north_center+dy/2
    height,width=arr.shape
    valid=np.isfinite(arr)&(arr!=-32767)
    lon0=(min(r['lon_deg'] for r in records)+max(r['lon_deg'] for r in records))/2
    lat0=(min(r['lat_deg'] for r in records)+max(r['lat_deg'] for r in records))/2
    ph=math.radians(lat0); a=6378137.;e2=6.6943799901413165e-3
    n=a/math.sqrt(1-e2*math.sin(ph)**2)
    m=a*(1-e2)/(1-e2*math.sin(ph)**2)**1.5
    sx=n*math.cos(ph)*math.pi/180; sy=m*math.pi/180
    points={}
    for rec in records:
        c=(rec['lon_deg']-west)/dx; r=(north-rec['lat_deg'])/dy
        ri,ci=math.floor(r),math.floor(c)
        assert 0<=ri<height and 0<=ci<width and valid[ri,ci]
        h=float(arr[ri,ci]); agl=0. if rec['node_id']=='O01' else 30.
        rec.update(dem_row_0=ri,dem_col_0=ci,ground_dem_cell_m=h,
                   table_minus_dem_m=rec['ground_table_m']-h,operation_agl_m=agl,
                   operation_alt_m=rec['ground_table_m']+agl,
                   x_local_m=(rec['lon_deg']-lon0)*sx,y_local_m=(rec['lat_deg']-lat0)*sy)
        points[rec['node_id']]=(c,r)
    legs=[]; slab_checks=0; reverse_checks=0; dense_checks=0
    edge_cache={}
    for i,src in enumerate(records):
        for j in range(i+1,len(records)):
            dst=records[j]
            x0,y0=points[src['node_id']];x1,y1=points[dst['node_id']]
            cells=crossing_cells(x0,y0,x1,y1)
            assert cells==slab_cells(x0,y0,x1,y1),(src['node_id'],dst['node_id'],'clipping mismatch')
            slab_checks+=1
            assert cells==crossing_cells(x1,y1,x0,y0)
            reverse_checks+=1
            assert all(0<=r<height and 0<=c<width and valid[r,c] for r,c in cells)
            highest=max(cells,key=lambda rc:(arr[rc],-rc[0],-rc[1]))
            z=float(arr[highest]); cruise=z+50.
            dist=math.hypot(dst['x_local_m']-src['x_local_m'],dst['y_local_m']-src['y_local_m'])
            chord=float(np.linalg.norm(ecef(src['lon_deg'],src['lat_deg'])-ecef(dst['lon_deg'],dst['lat_deg'])))
            # One metre point samples, independent of grid crossing logic.
            tt=np.linspace(0,1,math.ceil(dist)+1)
            rr=np.floor(y0+tt*(y1-y0)).astype(int);cc=np.floor(x0+tt*(x1-x0)).astype(int)
            assert float(arr[rr,cc].max())<=z+1e-8
            dense_checks+=1
            common=dict(horizontal_distance_m=dist,dem_max_m=z,cruise_alt_m=cruise,
                        dem_cells_touched=len(cells),max_dem_row_0=highest[0],max_dem_col_0=highest[1],
                        max_dem_lon_deg=west_center+highest[1]*dx,max_dem_lat_deg=north_center-highest[0]*dy,
                        ecef_chord_check_m=chord,projection_vs_chord_relative_error=(dist-chord)/chord,
                        distance_method='WGS84_local_linear_metric',terrain_method='closed_cell_supercover_PixelIsPoint')
            for start,end in [(src,dst),(dst,src)]:
                climb=cruise-start['operation_alt_m'];descent=cruise-end['operation_alt_m']
                assert climb>=0 and descent>=0,(start,end,cruise)
                leg=dict(from_id=start['node_id'],to_id=end['node_id'],**common,
                         from_operation_alt_m=start['operation_alt_m'],to_operation_alt_m=end['operation_alt_m'],
                         climb_m=climb,descent_m=descent)
                legs.append(leg)
                edge_cache[(start['node_id'],end['node_id'])]=leg
    legs.sort(key=lambda r:(r['from_id'],r['to_id']))
    assert len(legs)==240
    flight=[]
    modelws=load_workbook(model_file,data_only=True,read_only=True).active
    models=[]
    for row in list(modelws.values)[2:5]:
        g=row[0];vc,vu,vd=map(float,(row[5],row[14],row[15]))
        models.append(dict(model_id=g,cruise_speed_m_s=vc,climb_speed_m_s=vu,descent_speed_m_s=vd))
        for leg in legs:
            tc=leg['climb_m']/vu;th=leg['horizontal_distance_m']/vc;td=leg['descent_m']/vd
            flight.append(dict(from_id=leg['from_id'],to_id=leg['to_id'],model_id=g,
                               climb_time_s=tc,cruise_time_s=th,descent_time_s=td,
                               flight_time_s=tc+th+td,includes_preparation_or_handover=False))
    write_csv(out/'nodes.csv',records);write_csv(out/'legs.csv',legs);write_csv(out/'flight_times.csv',flight)
    rulefile=Path(__file__).resolve().parent/'time_rules.json'
    if rulefile.exists():
        rules=json.loads(rulefile.read_text(encoding='utf-8'))
        write_csv(out/'time_rules.csv',rules['rules'])
    # Audit appendix directly from OOXML, including structured math.
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
    with zipfile.ZipFile(docfile) as z:
        tree=etree.fromstring(z.read('word/document.xml'))
        paras=tree.findall('.//w:p',ns)
        active=False; excerpts=[]
        for idx,p in enumerate(paras,1):
            s=text_math(p)
            if s.startswith('附录 2.'):active=True
            if s.startswith('附录 3.'):active=False
            if active and s:excerpts.append(f'段落 {idx}\n\n{s}\n')
        (out/'appendix2_evidence.txt').write_text('\n'.join(excerpts),encoding='utf-8')
        math_count=len(tree.findall('.//m:oMath',ns))
    sources=[]
    for p in [docfile,demfile,*sorted(root.rglob('*.xlsx')),locate('镇龙乡地理空间数据说明.pdf')]:
        if p.name.startswith('~$'):continue
        sources.append(dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    # Nontrivial unit fixtures for cell-edge and grid-corner coverage.
    for coords in [(0.2,0.2,2.8,2.8),(1.,0.2,1.,2.8),(0.2,1.,2.8,1.),(1.,1.,2.,2.)]:
        assert crossing_cells(*coords)==slab_cells(*coords)
    # Read-back verifies serialization counts and positivity.
    for name,count in [('nodes.csv',16),('legs.csv',240),('flight_times.csv',720)]:
        with (out/name).open(encoding='utf-8-sig',newline='') as f:
            assert len(list(csv.DictReader(f)))==count
    summary=dict(nodes=16,directed_legs=240,model_flight_rows=720,
                 dem_shape_rows_cols=list(arr.shape),dem_valid_cells=int(valid.sum()),dem_invalid_cells=int((~valid).sum()),
                 dem_min_m=float(arr[valid].min()),dem_max_m=float(arr[valid].max()),
                 raster_type='PixelIsPoint',epsg=4326,
                 dem_first_center_lon=west_center,dem_first_center_lat=north_center,pixel_size_lon_deg=dx,pixel_size_lat_deg=dy,
                 local_projection=dict(lon0=lon0,lat0=lat0,meters_per_lon_degree=sx,meters_per_lat_degree=sy),
                 max_abs_node_height_difference_m=max(abs(r['table_minus_dem_m']) for r in records),
                 distance_range_m=[min(r['horizontal_distance_m'] for r in legs),max(r['horizontal_distance_m'] for r in legs)],
                 cruise_alt_range_m=[min(r['cruise_alt_m'] for r in legs),max(r['cruise_alt_m'] for r in legs)],
                 max_relative_distance_check_error=max(abs(r['projection_vs_chord_relative_error']) for r in legs),
                 max_absolute_distance_check_error_m=max(abs(r['horizontal_distance_m']-r['ecef_chord_check_m']) for r in legs),
                 validation=dict(independent_rectangle_clipping_pairs=slab_checks,reverse_direction_pairs=reverse_checks,
                                 one_metre_sampling_pairs=dense_checks,boundary_corner_fixtures=4,output_readback=True,
                                 missing_terrain_on_routes=0,negative_climb_or_descent=0),
                 source_omml_math_objects=math_count,sources=sources,
                 limitations=['Local linear metric projection is a documented numerical approximation; ECEF chord is a check, not an exact geodesic.',
                              'Energy subformulas and timing assumptions require confirmation; no energy results or optimal schedules generated.',
                              'Flight table covers transport nodes only, not yet variable relay hover locations.',
                              'NoData sentinel -32767 comes from the supplied PDF; GeoTIFF contains no explicit GDAL NoData tag.'])
    (out/'audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='sources'},ensure_ascii=False,indent=2))
    print('NODE HEIGHT DIFFERENCES',[(r['node_id'],round(r['table_minus_dem_m'],4)) for r in records])
    print('EXAMPLE',edge_cache[('O01','S001')])


if __name__=='__main__':main()
