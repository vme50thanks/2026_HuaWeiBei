# 复算说明

Python 3.12.14。依赖：{'numpy': '2.3.5', 'Pillow': '12.3.0', 'openpyxl': '3.1.5'}。无需商用优化器、SciPy或OR-Tools。推荐在现有工作区执行；原始输入和已核验预处理数据为外部依赖，不改写它们。`support/`为本次使用的第二问求解辅助与独立检查代码副本。

PowerShell（用已安装依赖的 python，或本机运行时绝对路径代替 python）：

```powershell
$src = 'D:\研一\比赛\中文题目\D题'
$pre = 'outputs/preflight'
$q2 = 'outputs/q2'
$q3 = 'outputs/q3'
python $q3/diagnose_search.py --source $src --pre $pre --q2 $q2 --out $q3 --spacing 1500
python $q3/diagnose_search.py --source $src --pre $pre --q2 $q2 --out $q3/fine_search --spacing 750
python $q3/diagnose_search.py --source $src --pre $pre --q2 $q2 --out $q3/ridge_search --spacing 750 --ridge
python $q3/temporal_search.py --folder $q3/ridge_search --out $q3/temporal_candidates.json --keep 100
python $q3/solve_joint.py --source $src --preflight $pre --q2 $q2 --out $q3 --mutations 24 --seconds 180
Copy-Item $q3/summary.json $q3/search_small_summary.json
python $q3/temporal_search.py --folder $q3/ridge_search --out $q3/temporal_expanded.json --keep 2000
python $q3/solve_joint.py --source $src --preflight $pre --q2 $q2 --out $q3 --mutations 160 --seconds 240 --triples temporal_expanded.json
python $q3/verify_joint.py --source $src --preflight $pre --out $q3
python $q3/report_joint.py --source $src --preflight $pre --out $q3
```

计时限制使较慢机器可能评估不同数量的运输候选；同一候选池排序与数值计算确定，随机种子为20260923。为复核交付方案，不必重新优化，直接执行最后两条命令。检查失败会抛出异常，必须修复或重新搜索，不能放宽约束。

基准细时间步长0.5 s，独立再用1/0.5 s比较；射线5/2.5 m与穿越像元检查。`summary.json`中Cmax/E/N仍为运输专用字段，联合字段为C_joint/total_E/total_N，避免把运输指标误认为联合指标。CSV时间、质量、能耗保留浮点原精度，报告仅展示时舍入。
