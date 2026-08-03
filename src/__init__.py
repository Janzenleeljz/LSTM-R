"""基于北斗短报文定位数据的危险货物运输车辆驾驶风险识别与分级方法。

模块：
    config          全局配置与阈值
    preprocess      数据接入、清洗、稀疏对齐与重采样、行程切分
    sensitive       危货敏感目标图层与情境暴露代理
    indicators      多维替代安全指标体系
    weighting       标准化与组合赋权（熵权法 + CRITIC）
    representation  自监督 LSTM 自编码器（Δt 感知、掩码重构）
    risk_index      综合运行风险指数（TOPSIS 融合）
    grading         风险等级划分与分级验证
    run_pipeline    端到端流程编排
"""
