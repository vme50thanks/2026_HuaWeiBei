# 第二问复算

依赖：Python 3.10+、openpyxl、Pillow。无需商业优化器。源文件保持只读。

在本目录执行（preflight为相邻目录）：

```powershell
python solve_q2.py --source 'D:\研一\比赛\中文题目\D题' --preflight '..\preflight' --runs 2000 --seconds 180
python improve_q2.py --source 'D:\研一\比赛\中文题目\D题' --preflight '..\preflight' --iterations 5000 --seconds 90
python verify_q2.py --source 'D:\研一\比赛\中文题目\D题' --preflight '..\preflight'
python report_q2.py --source 'D:\研一\比赛\中文题目\D题' --preflight '..\preflight'
```

实际运行Python：C:\Users\ASUS\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe。
PowerShell可把python替换为 & '该绝对路径'。源文件校验路径对应本次环境；迁移数据后应明确更新源审计位置并核验哈希，不要绕过校验。

构造种子0—1999，局部搜索种子20260923。本次完成所有迭代，时间限制未触发；若机器更慢导致提前达到时间上限，候选池可能不同。搜索随机性不是物理仿真随机性。

baseline目录为D优先，makespan_first为完成时间优先。所有CSV保存未人为取整结果，PNG为可读图。两方案独立检查均通过。详细数学模型、限制与下界见模型与调度报告.md。

improve_q2.py会读取并覆盖已有两方案，因此完全复算时应从solve_q2.py开始。报告脚本依赖Pillow和Windows字体（优先微软雅黑）；其他系统应配置对应字体。
