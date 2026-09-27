# 复算命令

在原工作区根目录执行，使用已装requirements.txt依赖的Python。输入路径作为外部依赖保留；不要把输出目录指向原始附件或q3。无随机过程，无随机种子，无搜索时间截断；完整枚举所有合法分区。Windows图形字体使用微软雅黑。

```powershell
$src = 'D:\研一\比赛\中文题目\D题'
$pre = 'outputs/preflight'
$q3 = 'outputs/q3'
$out = 'outputs/q4'
python $out/solve_q4.py --source $src --pre $pre --q3 $q3 --out $out
python $out/verify_q4.py --source $src --pre $pre --q3 $q3 --out $out
python $out/report_q4.py --pre $pre --out $out
```

只验证已导出方案时执行第二条。程序抛出断言则不可报告通过，需定位程序/数据问题，不能改动冻结任务或放宽约束。

主模板Q4_分区配置.csv含K=2、K=3基准5行。原始机体和组件ID保存在frozen任务内；实际分组承接编号见tasks.json顶层unit/energy_component与resource_assignment.csv。两者不同是允许重新编号口径，非任务改变。

编号类型顺序：A/B/C运输机、A/B/C电池、中继机、中继能源组件。CV为包含中继周转的机体占用工作量变异系数。G和S不是货币成本。
