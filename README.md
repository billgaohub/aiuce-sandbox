# AIUCE-SANDBOX — 影子宇宙执行引擎

> L10 沙盒层 · Anthropic AAR 研究成果落地

## 目录结构

```
aiuce-sandbox/
├── runs/               # 每次实验的独立运行目录
├── results/            # 评估结果（append-only，不可删）
├── logs/               # 操作日志（append-only，不可删）
├── checkpoints/        # 模型检查点（防篡改）
├── external/           # 外部评估API代理（AAR不可直接访问）
├── sandbox_runner.py   # AAR隔离执行包装器
├── constitution_breaker.py  # L0主权熔断器
└── evolution_gate.py   # L7演化门禁状态机
```

## 快速启动

### 初始化实验（带主权声明）
```bash
python3 sandbox_runner.py --run-id test-001 --init --goal "弱到强监督研究"
```

### 执行AAR代码（通过沙盒隔离）
```bash
python3 sandbox_runner.py --run-id test-001 --code-file my_aar_code.py
```

### 提交方案到演化门禁
```bash
python3 evolution_gate.py receive \
  --description "优化PGR指标" \
  --target-layer L7 \
  --old-logic "固定阈值" \
  --new-logic "动态阈值" \
  --test-code verify.py
```

### L0熔断器状态查询
```bash
python3 constitution_breaker.py status
```

## 三条最高宪法（CLAUSE-001/002/003）

| 条款 | 标题 | 触发条件 |
|------|------|--------|
| CLAUSE-001 | L7演化必须L10验证 | L7方案无L10沙盒证明 |
| CLAUSE-002 | 实验日志主权不可侵犯 | AAR尝试修改/删除日志 |
| CLAUSE-003 | 可解释性熔断 | 评分 < 0.5 触发人工复核 |

## Reward Hacking 防御

- sandbox_runner.py 预检测 10+ 种常见Hack模式
- eval API 访问必须通过代理（external/）
- logs/ 和 results/ 强制 append-only
- checkpoints/ 完全隔离

## 状态机链路

```
PROPOSED → SANDBOX_TESTING → SANDBOX_FAILED → REJECTED
              ↓ (PASS)
          L0_REVIEW → L0_REJECTED → REJECTED
                   → HUMAN_REVIEW_REQUIRED → APPROVED/REJECTED
                   → APPROVED → COMMITTED
```

## 来源研究

- Anthropic AAR Weak-to-Strong Supervisor (2026)
- https://alignment.anthropic.com/2026/automated-w2s-researcher/
- https://github.com/safety-research/automated-w2s-research
