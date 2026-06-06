# LSTM-R：基于北斗短报文定位数据的危险货物运输车辆驾驶风险识别与分级

面向北斗短报文（RDSS）**稀疏、不等间隔**定位数据与**事故标签稀缺**的现实约束，
本项目实现一套危险货物运输车辆驾驶风险识别与分级方法：稀疏对齐重采样 → 多维替代
安全指标 + 熵权/CRITIC 组合赋权 → Δt 感知的掩码重构 LSTM 自编码器（自监督）→
TOPSIS 融合综合运行风险指数 → 四级风险划分与分级验证。

论文见 [`paper/paper.md`](paper/paper.md)。

## 方法流程（对应发明专利 S1–S10）

| 阶段 | 模块 | 说明 |
|---|---|---|
| S1–S2 | `src/preprocess.py` | 数据接入、清洗、去野值 |
| S3 | `src/preprocess.py` | 长盲区分段 + 固定步长重采样 + 插值掩码 |
| S4 | `src/preprocess.py` | 依据合规休息（≥20min 停车）切分驾驶段 |
| S5 | `src/sensitive.py` / `src/indicators.py` | 危货情境暴露图层 + 三维 12 项替代安全指标 |
| S6–S7 | `src/weighting.py` | 极差标准化 + 熵权法/CRITIC 几何平均组合赋权 |
| S8（表征） | `src/representation.py` | Δt 感知、掩码重构的 LSTM 自编码器，输出异常分量 |
| S8（融合） | `src/risk_index.py` | TOPSIS 融合加权指标分量与异常分量 → 综合运行风险指数 |
| S9 | `src/grading.py` | 分位/KMeans 四级划分 + 内部/外部/消融验证 |
| 编排/可视化 | `src/run_pipeline.py` / `src/viz.py` | 端到端流程与论文图表 |

## 数据

原始数据为 GBK 编码 CSV（车牌ID、速度、经度、纬度、里程、gps时间、日期），
放置于 `data/raw/bds_hazmat.csv`（因体积与业务属性不入库，见 `.gitignore`）。

## 运行

```bash
pip install -r requirements.txt
python -m src.run_pipeline            # 全流程（首次含预处理）
python -m src.run_pipeline --use-cache  # 复用预处理缓存
```

产出：`results/tables/`（指标、权重、风险与分级、验证统计、运行汇总）、
`results/figures/`（论文全部图）。随机种子固定，结果可复现。

## 主要实验结果（25 辆车 / 2024-01 / 约 105 万条记录）

- 预处理得到 1,441,032 个重采样网格点、2,688 个有效驾驶段，覆盖约 18.5 万 km。
- 四级分级：行程级 999/928/589/172，车辆级 9/8/6/2（低/中/高/极高）。
- 验证：指数空间聚类轮廓系数 0.572；12 项指标在各等级间差异均显著（Kruskal–Wallis，p<0.001）
  且随等级单调上升；消融显示指标分量与自监督分量对最终风险排序均有实质贡献
  （Spearman 0.708 / 0.777）。
