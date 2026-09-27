"""A verified Q3 transport schedule is also feasible for relaxed Q2."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent;sys.path.insert(0,str(ROOT/'outputs/q2'))
from solve_q2 import Problem,export,score,dump
pr=Problem(Path('D:/研一/比赛/中文题目/D题'),ROOT/'outputs/preflight');q2=OUT/'q2';s=json.loads((q2/'summary.json').read_text(encoding='utf-8'))
dump(q2/'search_round3_summary.json',s)
dump(OUT/'calendar_seed_transport.json',json.loads((q2/'baseline/plan.json').read_text(encoding='utf-8')))
p=json.loads((OUT/'q3/baseline/plan.json').read_text(encoding='utf-8'));v=score(pr,p)
for name in ['baseline','makespan_first']:
 old=s[name]
 if v[0]<=old['D']+1e-7 and v[1]<=old['Cmax']+1e-7 and v[2]<old['E']:
  export(pr,p,q2,name);s[name].update(zip(['D','Cmax','E','N'],v));s[name]['source']='independently verified improved Q3 transport; Q2 is its relaxation'
dump(q2/'summary.json',s)
