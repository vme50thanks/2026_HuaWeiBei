from pathlib import Path
import subprocess,sys,shutil
r=Path(__file__).resolve().parent;c=r/'复算工作区/outputs';src='D:/研一/比赛/中文题目/D题';pre=r/'preflight'
def run(p,*args):subprocess.run([sys.executable,str(p),*map(str,args)],check=True)
run(c/'q2/verify_q2.py','--source',src,'--preflight',pre,'--out',r/'q2')
temp=r/'独立回放输出/q3';temp.mkdir(parents=True,exist_ok=True)
shutil.copy2(r/'q3/summary.json',temp/'summary.json')
for name in ['baseline','makespan_first']:
 d=temp/name;d.mkdir(exist_ok=True)
 for f in ['plan.json','relay_plan.json','Q2_运输架次.csv','Q2_逐箱交付.csv']:shutil.copy2(r/'q3'/name/f,d/f)
run(c/'q3/verify_joint.py','--source',src,'--preflight',pre,'--out',temp)
run(c/'q4/verify_q4.py','--source',src,'--pre',pre,'--q3',r/'q3','--out',r/'q4')
print('PASS: copied Q2/Q3/Q4 independently verified')
