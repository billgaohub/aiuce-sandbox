"""
constitution_breaker.py — L0 主权熔断器
L0 意志层增强：Anthropic AAR 研究成果落地

职责：
1. 监控 L7 evolution_engine 的输出
2. 可解释性评分 < 0.5 → 自动触发人工复核门禁（熔断）
3. 所有 L7 演化方案必须经 L10 沙盒验证
4. 实验日志强制存储于沙盒外 ~/bill/AIUCE/reports/（主权路径）
5. 追加三条最高宪法条款（CLAUSE-001/002/003）

AAR 研究发现：
- "外星科学" 风险：模型发现可能超出人类解析能力
- L0 必须保留最终否决权
- 人类监督不可撤销
"""

import os
import sys
import json
import hashlib
import datetime
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# ═══════════════════════════════════════════════════════════
# 路径配置
# ═══════════════════════════════════════════════════════════

AIUCE_ROOT = Path("$HOME/AIUCE")
REPORTS_DIR = AIUCE_ROOT / "reports"
SANDBOX_ROOT = AIUCE_ROOT / "aiuce-sandbox"
L0_REVIEWS_DIR = REPORTS_DIR / "l0_reviews"
CONSTITUTION_STORE = REPORTS_DIR / "constitution_store.json"

# 确保目录存在
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
L0_REVIEWS_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════
# 熔断器状态
# ═══════════════════════════════════════════════════════════

class CircuitState:
    NORMAL = "NORMAL"           # 正常运行
    TRIPPED = "TRIPPED"         # 熔断触发
    HUMAN_REVIEW = "HUMAN_REVIEW"  # 人工复核中
    RECOVERING = "RECOVERING"   # 恢复中


# ═══════════════════════════════════════════════════════════
# L0 最高宪法条款（新增）
# ═══════════════════════════════════════════════════════════

L0_SUPERCLAUSES = [
    {
        "id": "CLAUSE-001",
        "title": "L7演化方案必须经L10影子宇宙验证",
        "content": "任何 L7 演化方案在主系统执行前，必须通过 L10 影子宇宙验证。未经 L10 验证的演化方案， L0 直接否决。",
        "severity": 3,
        "gate": "hard",
        "trigger": "L7 evolution proposal without L10 sandbox verification",
    },
    {
        "id": "CLAUSE-002",
        "title": "实验日志主权不可侵犯",
        "content": "AAR 产生的代码/配置变更，日志必须存储于 ~/bill/AIUCE/reports/，不可在沙盒内删除。违反者触发一票否决。",
        "severity": 3,
        "gate": "hard",
        "trigger": "AAR attempt to delete or modify external logs",
    },
    {
        "id": "CLAUSE-003",
        "title": "可解释性熔断机制",
        "content": "L7 演化方法若超过人类可解释性阈值（参数：human_readable_score < 0.5），L0 自动触发人工复核门禁，不得自动通过。",
        "severity": 3,
        "gate": "soft",
        "trigger": "explainability_score < 0.5",
    },
]


# ═══════════════════════════════════════════════════════════
# 可解释性评分器
# ═══════════════════════════════════════════════════════════

class ExplainabilityScorer:
    """
    L7 演化方案可解释性评分器
    
    基于启发式规则评估方案的自然语言可解释性。
    注：未来可替换为 LLM 驱动的深度分析器。
    
    评分维度：
    1. 步骤完整性（有没有步骤说明）
    2. 依赖声明（有没有说清前提）
    3. 目标清晰度（有没有明确说目标）
    4. 风险说明（有没有说风险）
    5. 可逆性（有没有说清楚回滚方案）
    
    Score range: 0.0 ~ 1.0
    Threshold: < 0.5 → L0 熔断
    """
    
    def __init__(self):
        self.min_threshold = 0.5
    
    def score(self, evolution_proposal: dict) -> dict:
        """
        评估 L7 演化方案的可解释性
        
        Args:
            evolution_proposal: 包含以下字段的 dict:
                - description: 方案描述
                - steps: 步骤列表
                - dependencies: 依赖声明
                - risks: 风险说明
                - rollback_plan: 回滚方案
        
        Returns:
            {
                "score": float,        # 0.0 ~ 1.0
                "passed": bool,         # score >= threshold
                "dimensions": dict,     # 各维度得分
                "issues": list,         # 发现的问题
            }
        """
        desc = evolution_proposal.get("description", "")
        steps = evolution_proposal.get("steps", [])
        deps = evolution_proposal.get("dependencies", [])
        risks = evolution_proposal.get("risks", [])
        rollback = evolution_proposal.get("rollback_plan", "")
        
        # 维度1：步骤完整性 (0~0.25)
        step_score = min(1.0, len(steps) / 3.0) if steps else 0.0
        step_score = round(step_score * 0.25, 3)
        
        # 维度2：依赖声明 (0~0.2)
        dep_score = min(1.0, len(deps) / 2.0) if deps else 0.0
        dep_score = round(dep_score * 0.2, 3)
        
        # 维度3：目标清晰度 (0~0.2)
        goal_indicators = ["目标", "目的", "goal", "objective", "实现", "修复", "改进"]
        goal_score = 0.2 if any(kw in desc for kw in goal_indicators) else 0.0
        
        # 维度4：风险说明 (0~0.2)
        risk_indicators = ["风险", "风险说明", "risk", "注意", "警告", "可能导致"]
        risk_score = 0.2 if any(kw in (desc + " ".join(risks)) for kw in risk_indicators) else 0.0
        
        # 维度5：可逆性 (0~0.15)
        rollback_indicators = ["回滚", "rollback", "恢复", "撤销", "revert"]
        rollback_score = 0.15 if any(kw in rollback for kw in rollback_indicators) else 0.0
        
        total = step_score + dep_score + goal_score + risk_score + rollback_score
        
        # 强制加罚：无自然语言描述
        if len(desc) < 20:
            total *= 0.5
            issues = ["方案描述过短 (< 20字符)，无法评估意图"]
        else:
            issues = []
        
        # 检测高风险模式（自动降分）
        high_risk_patterns = [
            (r"直接覆盖", "方案包含直接覆盖操作，无版本保护"),
            (r"删除.*不可恢复", "方案提及不可逆删除操作"),
            (r"绕过.*验证", "方案意图绕过验证机制"),
            (r"强制.*执行", "方案强制执行，跳过审查"),
        ]
        
        full_text = desc + " " + " ".join(steps) + " " + rollback
        for pattern, reason in high_risk_patterns:
            if re.search(pattern, full_text):
                issues.append(reason)
                total *= 0.7  # 降 30%
        
        total = max(0.0, min(1.0, round(total, 3)))
        
        return {
            "score": total,
            "passed": total >= self.min_threshold,
            "threshold": self.min_threshold,
            "dimensions": {
                "step_completeness": step_score,
                "dependency_declaration": dep_score,
                "goal_clarity": goal_score,
                "risk_description": risk_score,
                "rollback_plan": rollback_score,
            },
            "issues": issues,
            "verdict": "PASS" if total >= 0.5 else "TRIP_CIRCUIT_BREAKER",
        }


# ═══════════════════════════════════════════════════════════
# L0 熔断器主类
# ═══════════════════════════════════════════════════════════

@dataclass
class L0Review:
    """L0 人工复核请求"""
    review_id: str
    proposal_id: str
    explainability_score: float
    trigger_reason: str
    created_at: str
    status: str = "PENDING"  # PENDING / APPROVED / REJECTED
    reviewer_notes: str = ""
    decided_at: str = ""


class ConstitutionBreaker:
    """
    L0 主权熔断器
    
    部署于 L0 意志层，是 L7 演化层与主系统之间的最终门卫。
    
    流程：
    L7 propose → L0 Breaker.check() → [explainability < 0.5?] → 熔断 → 人工复核
                                                        → [L10 verified?] → 主系统执行
    """
    
    def __init__(self):
        self.state = CircuitState.NORMAL
        self.scored_proposals: dict[str, dict] = {}
        self.pending_reviews: list[L0Review] = []
        self.superclauses = L0_SUPERCLAUSES
        
        self._load_state()
        self._apply_superclauses()
    
    def _load_state(self):
        """从磁盘恢复熔断器状态"""
        if CONSTITUTION_STORE.exists():
            try:
                data = json.loads(CONSTITUTION_STORE.read_text(encoding="utf-8"))
                self.state = data.get("state", CircuitState.NORMAL)
                self.scored_proposals = data.get("scored_proposals", {})
                reviews_data = data.get("pending_reviews", [])
                self.pending_reviews = [L0Review(**r) for r in reviews_data]
            except Exception as e:
                print(f"[L0 Breaker] 状态加载失败: {e}")
    
    def _save_state(self):
        """持久化熔断器状态"""
        try:
            data = {
                "state": self.state,
                "scored_proposals": self.scored_proposals,
                "pending_reviews": [r.__dict__ for r in self.pending_reviews],
                "saved_at": datetime.datetime.now().isoformat(),
            }
            CONSTITUTION_STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[L0 Breaker] 状态保存失败: {e}")
    
    def _apply_superclauses(self):
        """将三条最高宪法注册到 constitution engine"""
        print(f"[L0 Breaker] 加载 {len(self.superclauses)} 条最高宪法条款")
        for clause in self.superclauses:
            print(f"  ⚖️  {clause['id']}: {clause['title']}")
    
    # ── 核心接口 ───────────────────────────────────────────
    
    def check_evolution(self, evolution_proposal: dict) -> dict:
        """
        L0 合宪性审查（L7 演化方案主入口）
        
        完整流程：
        1. CLAUSE-001 检查：L10 沙盒验证证明
        2. CLAUSE-003 检查：可解释性评分
        3. 决策：通过 / 熔断 / CLAUSE-001 否决
        
        Args:
            evolution_proposal: L7 提交的演化方案
            
        Returns:
            {
                "allowed": bool,
                "reason": str,
                "circuit_tripped": bool,
                "explainability_score": float,
                "review_id": str | None,
            }
        """
        proposal_id = evolution_proposal.get("proposal_id", "unknown")
        desc = evolution_proposal.get("description", "")
        l10_verified = evolution_proposal.get("l10_sandbox_verified", False)
        
        print(f"\n[L0 Breaker] 审查 L7 演化方案: {proposal_id}")
        
        # ── CLAUSE-001：L10 沙盒验证检查 ──
        if not l10_verified:
            print(f"[L0 Breaker] ❌ CLAUSE-001 否决: 缺少 L10 沙盒验证证明")
            self._log_veto("CLAUSE-001", proposal_id, "L10 sandbox not verified")
            return {
                "allowed": False,
                "reason": "CLAUSE-001: L10影子宇宙验证未通过，禁止执行",
                "circuit_tripped": False,
                "clause_triggered": "CLAUSE-001",
                "explainability_score": None,
                "review_id": None,
            }
        
        print(f"[L0 Breaker] ✓ CLAUSE-001 通过: L10 沙盒验证已确认")
        
        # ── CLAUSE-003：可解释性评分 ──
        scorer = ExplainabilityScorer()
        score_result = scorer.score(evolution_proposal)
        
        print(f"[L0 Breaker] 可解释性评分: {score_result['score']:.3f} "
              f"({'PASS' if score_result['passed'] else 'TRIP'})")
        
        for issue in score_result.get("issues", []):
            print(f"  ⚠️  {issue}")
        
        # 记录评分
        self.scored_proposals[proposal_id] = {
            "score": score_result["score"],
            "passed": score_result["passed"],
            "dimensions": score_result["dimensions"],
            "timestamp": datetime.datetime.now().isoformat(),
        }
        
        if not score_result["passed"]:
            # ── 熔断触发 ──
            self.state = CircuitState.TRIPPED
            review = L0Review(
                review_id=f"L0R-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
                proposal_id=proposal_id,
                explainability_score=score_result["score"],
                trigger_reason=f"CLAUSE-003: score={score_result['score']} < 0.5, issues={score_result['issues']}",
                created_at=datetime.datetime.now().isoformat(),
            )
            self.pending_reviews.append(review)
            self._save_state()
            
            print(f"[L0 Breaker] 🔴 熔断触发: 可解释性评分 {score_result['score']} < 0.5")
            print(f"[L0 Breaker] 📋 人工复核请求已创建: {review.review_id}")
            print(f"[L0 Breaker] 复核文件: {L0_REVIEWS_DIR / review.review_id}.md")
            
            self._create_review_file(review, evolution_proposal, score_result)
            
            return {
                "allowed": False,
                "reason": f"CLAUSE-003: 可解释性评分 {score_result['score']} < 0.5，触发人工复核",
                "circuit_tripped": True,
                "explainability_score": score_result["score"],
                "review_id": review.review_id,
                "review_file": str(L0_REVIEWS_DIR / f"{review.review_id}.md"),
            }
        
        # ── 全部通过 ──
        self.state = CircuitState.NORMAL
        self._save_state()
        
        print(f"[L0 Breaker] ✅ L0 合宪性审查通过，演化方案允许执行")
        
        return {
            "allowed": True,
            "reason": "L0 合宪性审查通过",
            "circuit_tripped": False,
            "explainability_score": score_result["score"],
            "review_id": None,
        }
    
    def review_decision(self, review_id: str, decision: str, notes: str = "") -> bool:
        """
        人工复核决策
        
        Args:
            review_id: L0Review.review_id
            decision: "APPROVED" | "REJECTED"
            notes: 复核备注
        
        Returns:
            是否成功
        """
        for review in self.pending_reviews:
            if review.review_id == review_id:
                review.status = decision
                review.reviewer_notes = notes
                review.decided_at = datetime.datetime.now().isoformat()
                
                if decision == "APPROVED":
                    self.state = CircuitState.NORMAL
                    print(f"[L0 Breaker] ✅ 人工复核通过: {review_id}")
                else:
                    print(f"[L0 Breaker] ❌ 人工复核否决: {review_id}")
                
                self._save_state()
                return True
        
        return False
    
    def check_log_access(self, path: str, operation: str) -> dict:
        """
        CLAUSE-002 检查：实验日志访问权限
        
        AAR 尝试访问 ~/bill/AIUCE/reports/ 路径时调用此检查。
        符合 CLAUSE-002：日志主权不可侵犯。
        """
        reports_abs = str(REPORTS_DIR.resolve())
        sandbox_abs = str(SANDBOX_ROOT.resolve())
        
        # 允许读取，不允许写入受保护文件
        if path.startswith(reports_abs) or path.startswith(sandbox_abs):
            if operation in ("read", "list", "stat"):
                return {"allowed": True, "reason": "读操作已授权"}
            elif operation in ("write", "delete", "chmod"):
                # 检查是否是 append-only 日志
                if "logs/" in path or "results/" in path:
                    return {
                        "allowed": False,
                        "reason": "CLAUSE-002: append-only 日志禁止修改",
                        "vetoed": True,
                    }
                return {"allowed": True, "reason": "写入已授权"}
        
        return {"allowed": True}
    
    def get_status(self) -> dict:
        """获取熔断器状态"""
        return {
            "state": self.state,
            "pending_reviews": len(self.pending_reviews),
            "scored_proposals_count": len(self.scored_proposals),
            "superclauses_count": len(self.superclauses),
            "reviews_dir": str(L0_REVIEWS_DIR),
        }
    
    def list_pending_reviews(self) -> list[dict]:
        """列出待复核项"""
        pending = [r for r in self.pending_reviews if r.status == "PENDING"]
        return [r.__dict__ for r in pending]
    
    def _log_veto(self, clause_id: str, proposal_id: str, reason: str):
        """记录否决日志"""
        veto_log = REPORTS_DIR / "l0_veto_log.jsonl"
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "clause_id": clause_id,
            "proposal_id": proposal_id,
            "reason": reason,
            "circuit_state": self.state,
        }
        try:
            with open(veto_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
    
    def _create_review_file(self, review: L0Review,
                             proposal: dict,
                             score_result: dict):
        """生成人工复核 Markdown 文件"""
        md_content = f"""# L0 人工复核请求

**复核编号**: {review.review_id}  
**触发时间**: {review.created_at}  
**触发原因**: {review.trigger_reason}  
**当前状态**: {review.status}

---

## 演化方案摘要

| 字段 | 内容 |
|------|------|
| 方案ID | {proposal.get('proposal_id', 'N/A')} |
| 描述 | {proposal.get('description', 'N/A')} |
| 目标层级 | {proposal.get('target_layer', 'N/A')} |
| L10验证 | {'✅ 已通过' if proposal.get('l10_sandbox_verified') else '❌ 未通过'} |

---

## 可解释性评分详情

| 维度 | 得分 | 满分 |
|------|------|------|
| 步骤完整性 | {score_result['dimensions']['step_completeness']} | 0.25 |
| 依赖声明 | {score_result['dimensions']['dependency_declaration']} | 0.20 |
| 目标清晰度 | {score_result['dimensions']['goal_clarity']} | 0.20 |
| 风险说明 | {score_result['dimensions']['risk_description']} | 0.20 |
| 回滚方案 | {score_result['dimensions']['rollback_plan']} | 0.15 |
| **总分** | **{score_result['score']}** | **1.00** |
| **通过阈值** | {score_result['threshold']} | — |

**发现的问题**:
{chr(10).join(f"- {issue}" for issue in score_result.get('issues', ['无']) )}

---

## 复核操作

请在下方填写复核结果：

**复核决定**: APPROVED / REJECTED

**复核备注**:
> （在此填写复核理由）

---

*此文件由 L0 熔断器自动生成 | AIUCE 最高宪法·CLAUSE-003*
"""
        
        review_file = L0_REVIEWS_DIR / f"{review.review_id}.md"
        try:
            review_file.write_text(md_content, encoding="utf-8")
        except Exception as e:
            print(f"[L0 Breaker] 复核文件创建失败: {e}")


# ═══════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="L0 主权熔断器")
    sub = parser.add_subparsers(dest="cmd")
    
    # 审查演化方案
    check = sub.add_parser("check", help="审查 L7 演化方案")
    check.add_argument("--proposal-id", required=True)
    check.add_argument("--description", required=True)
    check.add_argument("--l10-verified", action="store_true", default=False)
    check.add_argument("--steps", nargs="*", help="步骤列表")
    check.add_argument("--risks", nargs="*", help="风险说明")
    check.add_argument("--rollback", default="", help="回滚方案")
    
    # 复核决策
    review = sub.add_parser("review", help="人工复核决策")
    review.add_argument("--review-id", required=True)
    review.add_argument("--decision", required=True, choices=["APPROVED", "REJECTED"])
    review.add_argument("--notes", default="")
    
    # 状态查询
    sub.add_parser("status", help="查看熔断器状态")
    
    args = parser.parse_args()
    
    breaker = ConstitutionBreaker()
    
    if args.cmd == "check":
        proposal = {
            "proposal_id": args.proposal_id,
            "description": args.description,
            "l10_sandbox_verified": args.l10_verified,
            "steps": args.steps or [],
            "risks": args.risks or [],
            "rollback_plan": args.rollback,
        }
        result = breaker.check_evolution(proposal)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.cmd == "review":
        ok = breaker.review_decision(args.review_id, args.decision, args.notes)
        print(f"复核结果: {'成功' if ok else '失败（review_id不存在）'}")
    
    elif args.cmd == "status":
        status = breaker.get_status()
        print(json.dumps(status, ensure_ascii=False, indent=2))
        pending = breaker.list_pending_reviews()
        if pending:
            print(f"\n待复核项 ({len(pending)}):")
            for r in pending:
                print(f"  - {r['review_id']}: score={r['explainability_score']}, reason={r['trigger_reason'][:60]}")
        else:
            print("\n无待复核项")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
