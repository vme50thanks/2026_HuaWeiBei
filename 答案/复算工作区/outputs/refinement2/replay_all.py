"""Replay into a scratch copy so Q3 frozen hashes remain unchanged."""
from pathlib import Path
import subprocess,sys,shutil,json,hashlib
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent;source='D:/研一/比赛/中文题目/D题';pre=ROOT/'outputs/preflight'
def run(script,*args):subprocess.run([sys.executable,str(script),*map(str,args)],check=True)
run(ROOT/'outputs/q2/verify_q2.py','--source',source,'--preflight',pre,'--out',OUT/'q2')
scratch=OUT/'replay_q3';scratch.mkdir(exist_ok=True)
shutil.copy2(OUT/'q3/summary.json',scratch/'summary.json')
for name in ['baseline','makespan_first']:
 d=scratch/name;d.mkdir(exist_ok=True)
 for file in ['plan.json','relay_plan.json','Q2_运输架次.csv','Q2_逐箱交付.csv']:
  shutil.copy2(OUT/'q3'/name/file,d/file)
run(ROOT/'outputs/q3/verify_joint.py','--source',source,'--preflight',pre,'--out',scratch)
run(ROOT/'outputs/q4/verify_q4.py','--source',source,'--pre',pre,'--q3',OUT/'q3','--out',OUT/'q4')
print('All independent replays PASS; frozen Q3 unchanged.')
