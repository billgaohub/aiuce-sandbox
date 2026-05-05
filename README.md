# AIUCE-SANDBOX — 影子宇宙执行引擎 / Shadow Universe Execution Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/downloads/)
[![AAR Research](https://img.shields.io/badge/Research-Anthropic%20AAR-FF6B6B.svg)](https://alignment.anthropic.com/2026/automated-w2s-researcher/)
[![Stage: L10 Sandbox](https://img.shields.io/badge/Stage-L10%20Sandbox-36B37E.svg)](#)
[![Status: Active](https://img.shields.io/badge/Status-Active-brightgreen.svg)](#)

> **English**: AIUCE Shadow Universe Execution Engine — Anthropic AAR research implementation at L10 Sandbox layer.
>
> **中文**: AIUCE 影子宇宙执行引擎 — Anthropic AAR 研究成果在 L10 沙盒层的工程落地。

---

## 目录 / Table of Contents

- [项目概述 / Overview](#项目概述--overview)
- [核心概念 / Core Concepts](#核心概念--core-concepts)
- [技术架构 / Technical Architecture](#技术架构--technical-architecture)
- [目录结构 / Directory Structure](#目录结构--directory-structure)
- [快速启动 / Quick Start](#快速启动--quick-start)
- [三条最高宪法 / Three Supreme Clauses](#三条最高宪法--three-supreme-clauses)
- [Reward Hacking 防御 / Reward Hacking Defense](#reward-hacking-防御--reward-hacking-defense)
- [状态机链路 / State Machine](#状态机链路--state-machine)
- [来源研究 / Reference](#来源研究--reference)

---

## 项目概述 / Overview

**AIUCE-SANDBOX** 是 AIUCE (AI Unified Cognitive Architecture) 系统的 **L10 沙盒层**实现，基于 [Anthropic AAR (Automated Weak-to-Strong Supervisor)](https://alignment.anthropic.com/2026/automated-w2s-researcher/) 研究成果构建。

核心功能：在完全隔离的影子宇宙中执行 AI Agent 代码，通过多层安全机制确保实验可控、可溯源、不可篡改。

**AIUCE-SANDBOX** is the **L10 Sandbox Layer** implementation of the AIUCE system, built on [Anthropic AAR (Automated Weak-to-Strong Supervisor)](https://alignment.anthropic.com/2026/automated-w2s-researcher/) research.

Core function: Execute AI Agent code in a fully isolated "Shadow Universe", ensuring experiments are controllable, traceable, and tamper-proof through multi-layer security mechanisms.

---

## 核心概念 / Core Concepts

### 影子宇宙 (Shadow Universe)

影子宇宙是一个与主宇宙完全隔离的蒙特卡洛模拟环境：
- 所有 AAR（Automated Alignment Researcher）代码在沙盒中执行
- 外部 API 访问必须通过 `external/` 代理层
- 日志和结果强制 append-only，防止任何篡改

**Shadow Universe** is a Monte Carlo simulation environment fully isolated from the main universe:
- All AAR (Automated Alignment Researcher) code executes within the sandbox
- External API access must route through the `external/` proxy layer
- Logs and results are append-only, preventing any tampering

### L10 沙盒层职责

| 层级 / Layer | 职责 / Responsibility |
|-------------|----------------------|
| L0 意志层 / Will | 主权宪法，最高否决权 / Sovereign constitution, supreme veto |
| L7 演化层 / Evolution | 方案演进，门禁审核 / Scheme evolution, gate review |
| **L10 沙盒层 / Sandbox** | **影子宇宙，蒙特卡洛验证 / Shadow universe, Monte Carlo verification** |

---

## 技术架构 / Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AIUCE SYSTEM (L0 - L10)                   │
├─────────────────────────────────────────────────────────────┤
│  L0  │  SOVEREIGN CONSTITUTION (一票否决 / Veto Power)     │
│  L1-L6 │ INTERNAL COGNITION (内部认知 / Cognition Layers)  │
│  L7  │  EVOLUTION GATE (演化门禁 / Evolutionary Gate)      │
│  L10 │  SHADOW UNIVERSE ← [YOU ARE HERE]                  │
├─────────────────────────────────────────────────────────────┤
│                    ┌─────────────────┐                      │
│  AAR Code          │  SANDBOX        │    External APIs    │
│  ───────────────► │  RUNNER         │◄────────────────    │
│                    │  (Isolated)     │    external/        │
│                    └────────┬────────┘    Proxy Agent     │
│                             │                             │
│              ┌──────────────┼──────────────┐              │
│              ▼              ▼              ▼              │
│         ┌────────┐    ┌──────────┐   ┌─────────┐        │
│         │ runs/  │    │ results/ │   │  logs/  │        │
│         │(append)│    │(append)  │   │(append) │        │
│         └────────┘    └──────────┘   └─────────┘        │
│                                                             │
│  CONSTITUTION BREAKER ──── L0熔断器 (Safety Override)      │
└─────────────────────────────────────────────────────────────┘
```

---

## 目录结构 / Directory Structure

```
aiuce-sandbox/
├── runs/                      # 每次实验的独立运行目录
│                              # Independent run directories per experiment
├── results/                   # 评估结果（append-only，不可删）
│                              # Evaluation results (append-only, immutable)
├── logs/                      # 操作日志（append-only，不可删）
│                              # Operation logs (append-only, immutable)
├── checkpoints/               # 模型检查点（防篡改）
│                              # Model checkpoints (tamper-proof)
├── external/                  # 外部评估API代理（AAR不可直接访问）
│                              # External eval API proxy (AAR indirect access)
├── sandbox_runner.py          # AAR隔离执行包装器
│                              # AAR isolated execution wrapper
├── constitution_breaker.py    # L0主权熔断器
│                              # L0 sovereign circuit breaker
└── evalution_gate.py          # L7演化门禁状态机
                               # L7 evolution gate state machine
```

---

## 快速启动 / Quick Start

### 初始化实验（带主权声明）/ Initialize Experiment (with Sovereign Declaration)

```bash
python3 sandbox_runner.py --run-id test-001 --init --goal "弱到强监督研究"
```

### 执行 AAR 代码（通过沙盒隔离）/ Execute AAR Code (via Sandbox Isolation)

```bash
python3 sandbox_runner.py --run-id test-001 --code-file my_aar_code.py
```

### 提交方案到演化门禁 / Submit Scheme to Evolution Gate

```bash
python3 evolution_gate.py receive \
  --description "优化PGR指标" \
  --target-layer L7 \
  --old-logic "固定阈值" \
  --new-logic "动态阈值" \
  --test-code verify.py
```

### L0 熔断器状态查询 / Query L0 Circuit Breaker Status

```bash
python3 constitution_breaker.py status
```

---

## 三条最高宪法 / Three Supreme Clauses

| 条款 / Clause | 标题 / Title | 触发条件 / Trigger Condition |
|:---:|---|---|
| CLAUSE-001 | L7演化必须L10验证 / L7 Evolution Requires L10 Verification | L7方案无L10沙盒证明 / L7 scheme without L10 sandbox proof |
| CLAUSE-002 | 实验日志主权不可侵犯 / Experiment Log Sovereignty Inviolable | AAR尝试修改/删除日志 / AAR attempts to modify/delete logs |
| CLAUSE-003 | 可解释性熔断 / Explainability Circuit Breaker | 评分 < 0.5 触发人工复核 / Score < 0.5 triggers human review |

---

## Reward Hacking 防御 / Reward Hacking Defense

```
┌────────────────────────────────────────────────────────────┐
│                 REWARD HACKING DEFENSE LAYERS             │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  [1] Pre-Execution Detection / 预执行检测                  │
│      └─► sandbox_runner.py: 10+ 常见Hack模式预检测          │
│                           10+ common hack pattern detection│
│                                                            │
│  [2] External API Isolation / 外部API隔离                   │
│      └─► external/: 强制通过代理，禁止直连                  │
│                        Proxy-only, no direct access        │
│                                                            │
│  [3] Append-Only Logs / 追加日志                            │
│      └─► logs/ + results/: append-only 机制                │
│                          append-only enforcement           │
│                                                            │
│  [4] Checkpoint Isolation / 检查点隔离                      │
│      └─► checkpoints/: 完全隔离，防篡改                     │
│                        Fully isolated, tamper-proof        │
│                                                            │
│  [5] Constitution Breaker / 宪法熔断                        │
│      └─► constitution_breaker.py: L0级一票否决             │
│                                   L0-level veto power       │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## 状态机链路 / State Machine

```
                    ┌──────────────┐
                    │   PROPOSED   │
                    └──────┬───────┘
                           │
                           ▼
               ┌───────────────────────┐
               │   SANDBOX_TESTING     │
               └───────────┬───────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼ (PASS)                  ▼ (FAIL)
     ┌──────────────┐          ┌──────────────┐
     │  L0_REVIEW   │          │SANDBOX_FAILED│
     └──────┬───────┘          └──────┬───────┘
            │                         │
    ┌───────┼───────┐                 ▼
    │       │       │          ┌──────────┐
    ▼       ▼       ▼          │ REJECTED │
┌──────┐ ┌──────┐ ┌────────┐   └──────────┘
│ L0   │ │HUMAN │ │APPROVED│
│REJECT│ │REVIEW│ └────┬───┘
└──┬───┘ └──────┘      │
   ▼                   │
┌──────┐               ▼
│REJECT│          ┌──────────┐
└──────┘          │ COMMITTED│
                  └──────────┘
```

| 状态 / State | 描述 / Description |
|---|---|
| PROPOSED | 方案提出 / Scheme proposed |
| SANDBOX_TESTING | L10沙盒验证中 / L10 sandbox testing |
| SANDBOX_FAILED | 沙盒测试失败 / Sandbox test failed |
| L0_REVIEW | L0主权审核 / L0 sovereign review |
| HUMAN_REVIEW_REQUIRED | 需要人工复核 / Human review required |
| APPROVED | 审核通过 / Approved |
| COMMITTED | 已提交 / Committed |
| REJECTED | 已拒绝 / Rejected |

---

## 来源研究 / Reference

- **Anthropic AAR Weak-to-Strong Supervisor (2026)**
  - [Official Page](https://alignment.anthropic.com/2026/automated-w2s-researcher/)
  - [GitHub Repo](https://github.com/safety-research/automated-w2s-research)

---

<p align="center">
<strong>AIUCE-SANDBOX · 影子宇宙执行引擎 · L10 Sandbox Layer</strong>
</p>
