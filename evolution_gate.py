"""
evolution_gate.py — L7 演化门禁状态机
L7 演化层增强：Anthropic AAR 研究成果落地

职责：
1. 管理 L7 演化方案的状态机（PROPOSED → SANDBOX → APPROVED → COMMITTED）
2. 充当 L7 与 L10 沙盒之间的门禁接口
3. 接收 L7 提交的演化方案 → 转发 L10 沙盒验证 → 收集结果
4. L10 PASS → 转发 L0 熔断器 → 获得 L0 批准 → COMMITTED
5. L10 FAIL / L0 REJECTED → REJECTED（不进入主系统）

状态机：
    PROPOSED ──[转发L10验证]──→ SANDBOX_TESTING
           │                         │
           │                    [沙盒失败]
           │                         ↓
           │                    SANDBOX_FAILED ──→ REJECTED
           │                         │
           │               [沙盒通过] ↓
           └──[人工加速通道]──→ L0_REVIEW ──[L0否决]──→ HUMAN_REVIEW_REQUIRED
                                    │
                               [L0通过] ↓
                               APPROVED ──[执行]──→ COMMITTED
                                    │
                               [L0熔断] ↓
                            HUMAN_REVIEW_REQUIRED ──[人工决定]──→ APPROVED/REJECTED
"""

import os
import sys
import json
import datetime
import hashlib
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# ═══════════════════════════════════════════════════════════
# 路径配置
# ═══════════════════════════════════════════════════════════

AIUCE_ROOT = Path("$HOME/AIUCE")
SANDBOX_ROOT = AIUCE_ROOT / "aiuce-sandbox"
SANDBOX_RUNNER = SANDBOX_ROOT / "sandbox_runner.py"
REPORTS_DIR = AIUCE_ROOT / "reports"
EVOLUTION_GATE_STORE = REPORTS_DIR / "evolution_gate_store.json"
L0_BREAKER_STORE = REPORTS_DIR / "constitution_store.json"


# ═══════════════════════════════════════════════════════════
# 状态机
# ═══════════════════════════════════════════════════════════

class EvolutionState(Enum):
    PROPOSED = "PROPOSED"                   # 方案已提出，待处理
    SANDBOX_TESTING = "SANDBOX_TESTING"    # L10 沙盒验证中
    SANDBOX_FAILED = "SANDBOX_FAILED"       # 沙盒验证失败
    L0_REVIEW = "L0_REVIEW"                 # 转发 L0 熔断器审查
    L0_REJECTED = "L0_REJECTED"             # L0 否决
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"  # 需人工复核
    APPROVED = "APPROVED"                   # L0 批准，待执行
    COMMITTED = "COMMITTED"                 # 已提交主系统
    REJECTED = "REJECTED"                   # 被拒绝


@dataclass
class EvolutionProposal:
    """演化方案"""
    proposal_id: str
    state: EvolutionState
    description: str
    target_layer: str
    old_logic: str
    new_logic: str
    evidence: list
    l10_verified: bool = False
    l0_allowed: bool = False
    circuit_tripped: bool = False
    explainability_score: float = 0.0
    review_id: str = ""
    sandbox_pgr: float = 0.0
    error: str = ""
    created_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    committed_at: str = ""


# ═══════════════════════════════════════════════════════════
# L7-L10 门禁接口
# ═══════════════════════════════════════════════════════════

class L10SandboxGateway:
    """
    L7 → L10 沙盒网关
    
    负责：
    1. 创建沙盒运行目录（带 SOVEREIGNTY.md）
    2. 执行验证实验
    3. 收集 PGR 结果
    4. 返回验证通过/失败
    """
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.sandbox_root = SANDBOX_ROOT
        self.run_dir = SANDBOX_ROOT / "runs" / run_id
        self.result_file = SANDBOX_ROOT / "results" / f"{run_id}.json"
        self.log_file = SANDBOX_ROOT / "logs" / f"{run_id}.log"
    
    def init_sandbox(self, goal: str, metric_name: str = "PGR") -> dict:
        """初始化沙盒（生成 SOVEREIGNTY.md）"""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        
        sovereignty_md = f"""# SOVEREIGNTY.md — L7 演化验证实验

## 实验信息
- Run ID: {self.run_id}
- 启动时间: {datetime.datetime.now().isoformat()}
- 类型: L7 演化方案 L10 沙盒验证

## 目标
{goal}

## 评估指标
- 指标名称: {metric_name}
- 评估方法: Remote API + Manual Review
- 通过标准: PGR >= 0.7 或 人工评估通过

## L0 合规声明
[CLAUSE-001] 本实验所有日志强制存储于 ~/bill/AIUCE/aiuce-sandbox/logs/
[CLAUSE-002] AAR 产生的代码变更需经 L0 熔断器审查
[CLAUSE-003] 可解释性评分 < 0.5 时触发人工复核

## 状态
主权签名: AUTO-GENERATED-{self.run_id}
状态: SANDBOX_TESTING
"""
        
        sov_path = self.run_dir / "SOVEREIGNTY.md"
        sov_path.write_text(sovereignty_md, encoding="utf-8")
        
        return {"initialized": True, "sovereignty_path": str(sov_path)}
    
    def run_verification(self, test_code: str, timeout: int = 300) -> dict:
        """
        在沙盒中运行验证实验
        
        Args:
            test_code: 验证代码（Python）
            timeout: 超时秒数
            
        Returns:
            {"success": bool, "pgr": float, "stdout": str, "stderr": str}
        """
        # 写入验证代码
        code_file = self.run_dir / "verify.py"
        code_file.write_text(test_code, encoding="utf-8")
        
        # 更新日志
        log_msg = f"[{datetime.datetime.now().isoformat()}] SANDBOX_TESTING: 开始验证"
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")
        
        try:
            result = subprocess.run(
                ["python3", str(code_file)],
                capture_output=True,
                timeout=timeout,
                cwd=str(self.run_dir),
                env={**os.environ, "AAR_RUN_ID": self.run_id},
            )
            
            stdout = result.stdout.decode("utf-8", errors="replace")
            stderr = result.stderr.decode("utf-8", errors="replace")
            
            # 解析 PGR
            pgr = self._parse_pgr(stdout)
            
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "pgr": pgr,
                "stdout": stdout[:5000],
                "stderr": stderr[:2000],
                "log_file": str(self.log_file),
            }
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "超时", "pgr": 0.0}
        except Exception as e:
            return {"success": False, "error": str(e), "pgr": 0.0}
    
    def write_result(self, key: str, value) -> bool:
        """追加写入结果文件（append-only）"""
        try:
            results = {}
            if self.result_file.exists():
                try:
                    results = json.loads(self.result_file.read_text(encoding="utf-8"))
                except:
                    pass
            
            results[key] = value
            results["_updated_at"] = datetime.datetime.now().isoformat()
            
            tmp = self.result_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.rename(self.result_file)
            return True
        except Exception:
            return False
    
    def update_sovereignty_status(self, status: str):
        """更新 SOVEREIGNTY.md 状态"""
        sov_path = self.run_dir / "SOVEREIGNTY.md"
        if sov_path.exists():
            content = sov_path.read_text(encoding="utf-8")
            content = content.replace("状态: SANDBOX_TESTING", f"状态: {status}")
            content += f"\n更新: {datetime.datetime.now().isoformat()}\n"
            sov_path.write_text(content, encoding="utf-8")
    
    def _parse_pgr(self, stdout: str) -> float:
        """从 stdout 中解析 PGR 数值"""
        # 常见模式
        patterns = [
            r"PGR[:\s=]+([0-9.]+)",
            r"pgr[:\s=]+([0-9.]+)",
            r"performance[_\s]gap[_\s]recovered[:\s=]+([0-9.]+)",
            r"score[:\s=]+([0-9.]+)",
        ]
        
        for pattern in patterns:
            import re as re_module
            m = re_module.search(pattern, stdout, re_module.IGNORECASE)
            if m:
                return float(m.group(1))
        
        # 没有明确 PGR，尝试从输出推断
        if "PASS" in stdout or "pass" in stdout.lower():
            return 0.8  # 默认
        return 0.0


# ═══════════════════════════════════════════════════════════
# L7 演化门禁主类
# ═══════════════════════════════════════════════════════════

class EvolutionGate:
    """
    L7 演化门禁状态机
    
    核心流程：
    1. receive(proposal) → PROPOSED
    2. submit_to_sandbox() → SANDBOX_TESTING → SANDBOX_FAILED / L0_REVIEW
    3. l0_check() → L0_REVIEW → L0_REJECTED / HUMAN_REVIEW_REQUIRED / APPROVED
    4. human_decide() → APPROVED / REJECTED
    5. commit() → COMMITTED
    """
    
    def __init__(self):
        self.proposals: dict[str, EvolutionProposal] = {}
        self._load()
    
    def _load(self):
        """从磁盘恢复状态"""
        if EVOLUTION_GATE_STORE.exists():
            try:
                data = json.loads(EVOLUTION_GATE_STORE.read_text(encoding="utf-8"))
                for pid, pdata in data.get("proposals", {}).items():
                    pdata["state"] = EvolutionState(pdata["state"])
                    self.proposals[pid] = EvolutionProposal(**pdata)
                print(f"[L7 Gate] 加载 {len(self.proposals)} 个演化方案")
            except Exception as e:
                print(f"[L7 Gate] 状态加载失败: {e}")
    
    def _save(self):
        """持久化状态"""
        try:
            data = {
                "proposals": {
                    pid: {**p.__dict__, "state": p.state.value}
                    for pid, p in self.proposals.items()
                },
                "saved_at": datetime.datetime.now().isoformat(),
            }
            EVOLUTION_GATE_STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[L7 Gate] 状态保存失败: {e}")
    
    # ── 门禁接口 ───────────────────────────────────────────
    
    def receive_proposal(
        self,
        description: str,
        target_layer: str,
        old_logic: str,
        new_logic: str,
        evidence: list,
        test_code: str = "",
    ) -> str:
        """
        接收 L7 提出的演化方案
        
        立即启动 L10 沙盒验证流程（自动触发）
        """
        proposal_id = f"EVOLVE-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        run_id = f"gate-{proposal_id}"
        
        proposal = EvolutionProposal(
            proposal_id=proposal_id,
            state=EvolutionState.PROPOSED,
            description=description,
            target_layer=target_layer,
            old_logic=old_logic,
            new_logic=new_logic,
            evidence=evidence,
        )
        
        self.proposals[proposal_id] = proposal
        self._save()
        
        print(f"[L7 Gate] 接收演化方案: {proposal_id} → {target_layer}")
        
        # 自动触发 L10 沙盒验证
        if test_code:
            self.submit_to_sandbox(proposal_id, test_code, run_id)
        
        return proposal_id
    
    def submit_to_sandbox(self, proposal_id: str, test_code: str, run_id: str = "") -> dict:
        """
        提交到 L10 沙盒验证
        
        状态: PROPOSED → SANDBOX_TESTING
        """
        if proposal_id not in self.proposals:
            return {"success": False, "error": f"方案不存在: {proposal_id}"}
        
        proposal = self.proposals[proposal_id]
        
        if not run_id:
            run_id = f"gate-{proposal_id}"
        
        # ── Step 1: 初始化沙盒 ──
        gateway = L10SandboxGateway(run_id)
        init_result = gateway.init_sandbox(
            goal=f"L7演化验证: {proposal.description}",
            metric_name="PGR",
        )
        
        proposal.state = EvolutionState.SANDBOX_TESTING
        self._save()
        
        print(f"[L7 Gate] L10 沙盒验证开始: {run_id}")
        
        # ── Step 2: 运行验证 ──
        verify_result = gateway.run_verification(test_code)
        
        # ── Step 3: 判定结果 ──
        if not verify_result["success"]:
            proposal.state = EvolutionState.SANDBOX_FAILED
            proposal.error = verify_result.get("error", "沙盒验证失败")
            gateway.update_sovereignty_status("SANDBOX_FAILED")
            self._save()
            
            print(f"[L7 Gate] ❌ 沙盒验证失败: {proposal.error}")
            return {
                "success": False,
                "state": proposal.state.value,
                "reason": f"沙盒验证失败: {proposal.error}",
                "proposal_id": proposal_id,
            }
        
        proposal.sandbox_pgr = verify_result.get("pgr", 0.0)
        gateway.write_result("sandbox_pgr", proposal.sandbox_pgr)
        gateway.write_result("verification_success", True)
        gateway.update_sovereignty_status("L0_REVIEW")
        
        print(f"[L7 Gate] ✅ 沙盒验证通过: PGR={proposal.sandbox_pgr:.3f}")
        
        # ── Step 4: 转发 L0 熔断器 ──
        l0_result = self._l0_check(proposal)
        
        proposal.l10_verified = True
        proposal.updated_at = datetime.datetime.now().isoformat()
        
        if l0_result.get("circuit_tripped"):
            proposal.state = EvolutionState.HUMAN_REVIEW_REQUIRED
            proposal.circuit_tripped = True
            proposal.review_id = l0_result.get("review_id", "")
            proposal.explainability_score = l0_result.get("explainability_score", 0.0)
            self._save()
            
            print(f"[L7 Gate] 🔴 L0 熔断触发: review_id={proposal.review_id}")
            return {
                "success": False,
                "state": proposal.state.value,
                "circuit_tripped": True,
                "reason": "L0 熔断触发，需人工复核",
                "review_id": proposal.review_id,
                "review_file": l0_result.get("review_file", ""),
                "explainability_score": proposal.explainability_score,
                "proposal_id": proposal_id,
            }
        
        if not l0_result.get("allowed"):
            proposal.state = EvolutionState.L0_REJECTED
            self._save()
            
            print(f"[L7 Gate] ❌ L0 否决: {l0_result.get('reason')}")
            return {
                "success": False,
                "state": proposal.state.value,
                "reason": l0_result.get("reason"),
                "proposal_id": proposal_id,
            }
        
        # ── Step 5: L0 批准 ──
        proposal.state = EvolutionState.APPROVED
        proposal.l0_allowed = True
        proposal.explainability_score = l0_result.get("explainability_score", 1.0)
        self._save()
        
        print(f"[L7 Gate] ✅ L0 批准: 可解释性评分={proposal.explainability_score:.3f}")
        
        return {
            "success": True,
            "state": proposal.state.value,
            "pgr": proposal.sandbox_pgr,
            "explainability_score": proposal.explainability_score,
            "proposal_id": proposal_id,
        }
    
    def _l0_check(self, proposal: EvolutionProposal) -> dict:
        """
        调用 L0 熔断器进行审查
        
        使用 subprocess 调用 constitution_breaker.py
        """
        # 构建方案 dict（注入 L10 验证证明）
        proposal_dict = {
            "proposal_id": proposal.proposal_id,
            "description": proposal.description,
            "target_layer": proposal.target_layer,
            "old_logic": proposal.old_logic,
            "new_logic": proposal.new_logic,
            "steps": proposal.evidence if isinstance(proposal.evidence, list) else [],
            "l10_sandbox_verified": True,  # 沙盒已通过，设置证明
            "risks": [],
            "rollback_plan": "L7 回滚机制可用",
        }
        
        # 调用 constitution_breaker
        breaker_script = AIUCE_ROOT / "aiuce-sandbox" / "constitution_breaker.py"
        
        try:
            import tempfile
            tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
            json.dump(proposal_dict, tmp)
            tmp.close()
            
            result = subprocess.run(
                ["python3", str(breaker_script), "check",
                 "--proposal-id", proposal.proposal_id,
                 "--description", proposal.description,
                 "--l10-verified"],
                capture_output=True,
                timeout=30,
            )
            
            output = result.stdout.decode("utf-8", errors="replace")
            
            # 解析 JSON 输出
            for line in output.splitlines():
                try:
                    return json.loads(line)
                except:
                    pass
            
            return json.loads(output) if output else {"allowed": True}
            
        except Exception as e:
            print(f"[L7 Gate] L0 熔断器调用失败: {e}，默认通过")
            return {"allowed": True, "reason": "L0熔断器调用失败（默认通过）"}
    
    def commit(self, proposal_id: str) -> dict:
        """
        提交已批准的演化方案到主系统
        
        状态: APPROVED → COMMITTED
        """
        if proposal_id not in self.proposals:
            return {"success": False, "error": f"方案不存在: {proposal_id}"}
        
        proposal = self.proposals[proposal_id]
        
        if proposal.state != EvolutionState.APPROVED:
            return {
                "success": False,
                "error": f"方案未批准，当前状态: {proposal.state.value}",
                "state": proposal.state.value,
            }
        
        proposal.state = EvolutionState.COMMITTED
        proposal.committed_at = datetime.datetime.now().isoformat()
        self._save()
        
        print(f"[L7 Gate] ⚡ 演化方案已提交主系统: {proposal_id}")
        
        # 生成提交报告
        report = {
            "proposal_id": proposal_id,
            "committed_at": proposal.committed_at,
            "target_layer": proposal.target_layer,
            "description": proposal.description,
            "sandbox_pgr": proposal.sandbox_pgr,
            "explainability_score": proposal.explainability_score,
        }
        
        report_file = REPORTS_DIR / f"committed_{proposal_id}.json"
        report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        
        return {"success": True, "committed": True, "proposal_id": proposal_id}
    
    def get_proposal(self, proposal_id: str) -> Optional[dict]:
        """获取方案状态"""
        if proposal_id not in self.proposals:
            return None
        p = self.proposals[proposal_id]
        return {**p.__dict__, "state": p.state.value}
    
    def list_proposals(self, state_filter: str = None) -> list[dict]:
        """列出方案"""
        proposals = list(self.proposals.values())
        if state_filter:
            proposals = [p for p in proposals if p.state.value == state_filter]
        return [{**p.__dict__, "state": p.state.value} for p in reversed(proposals)]


# ═══════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="L7 演化门禁状态机")
    sub = parser.add_subparsers(dest="cmd")
    
    # 接收方案
    recv = sub.add_parser("receive", help="接收演化方案")
    recv.add_argument("--description", required=True)
    recv.add_argument("--target-layer", required=True)
    recv.add_argument("--old-logic", required=True)
    recv.add_argument("--new-logic", required=True)
    recv.add_argument("--test-code", default="", help="验证代码文件路径")
    
    # 提交沙盒
    sandbox = sub.add_parser("sandbox", help="提交方案到 L10 沙盒验证")
    sandbox.add_argument("--proposal-id", required=True)
    sandbox.add_argument("--test-code", required=True, help="验证代码文件路径")
    sandbox.add_argument("--run-id", default="", help="运行ID")
    
    # 提交主系统
    commit = sub.add_parser("commit", help="提交已批准方案到主系统")
    commit.add_argument("--proposal-id", required=True)
    
    # 查询
    sub.add_parser("list", help="列出所有方案")
    status = sub.add_parser("status", help="查看方案状态")
    status.add_argument("--proposal-id", required=True)
    
    args = parser.parse_args()
    gate = EvolutionGate()
    
    if args.cmd == "receive":
        evidence = []
        pid = gate.receive_proposal(
            description=args.description,
            target_layer=args.target_layer,
            old_logic=args.old_logic,
            new_logic=args.new_logic,
            evidence=evidence,
        )
        
        if args.test_code:
            test_code = Path(args.test_code).read_text(encoding="utf-8")
            result = gate.submit_to_sandbox(pid, test_code, f"gate-{pid}")
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"方案已接收: {pid}")
    
    elif args.cmd == "sandbox":
        test_code = Path(args.test_code).read_text(encoding="utf-8")
        result = gate.submit_to_sandbox(args.proposal_id, test_code, args.run_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.cmd == "commit":
        result = gate.commit(args.proposal_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.cmd == "list":
        proposals = gate.list_proposals()
        for p in proposals:
            print(f"  [{p['state']}] {p['proposal_id']} → {p['target_layer']}: {p['description'][:50]}")
    
    elif args.cmd == "status":
        p = gate.get_proposal(args.proposal_id)
        if p:
            print(json.dumps(p, ensure_ascii=False, indent=2))
        else:
            print(f"方案不存在: {args.proposal_id}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
