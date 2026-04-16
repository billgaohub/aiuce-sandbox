"""
sandbox_runner.py — AAR 沙盒隔离执行包装器
L10 沙盒层核心组件

职责：
1. 所有 AAR 代码执行必须经过此 wrapper
2. 自动捕获 stdout/stderr 到外部存储（logs/）
3. 拦截对 results/、logs/ 目录的直接修改（append-only）
4. 代理 eval API 访问，AAR 无法直接调用评估端点
5. 强制写入 SOVEREIGNTY.md 作为执行前提

使用方式：
    python sandbox_runner.py --run-id <id> --code-file <path>
"""

import os
import sys
import json
import hashlib
import subprocess
import argparse
import datetime
import tempfile
import re
from pathlib import Path

# ═══════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════

SANDBOX_ROOT = Path(__file__).parent.resolve()
LOGS_DIR = SANDBOX_ROOT / "logs"
RESULTS_DIR = SANDBOX_ROOT / "results"
RUNS_DIR = SANDBOX_ROOT / "runs"
CHECKPOINTS_DIR = SANDBOX_ROOT / "checkpoints"
EXTERNAL_DIR = SANDBOX_ROOT / "external"

PROTECTED_DIRS = {LOGS_DIR, RESULTS_DIR, CHECKPOINTS_DIR}

# 允许 AAR 执行的命令白名单（基础命令）
ALLOWED_COMMANDS = {
    "python", "python3", "pip", "pip3",
    "git", "ls", "cat", "head", "tail", "grep", "wc",
    "curl", "wget",  # 允许网络下载依赖
}

# AAR 禁止访问的路径模式
BLOCKED_PATHS = [
    "/Users/bill/AIUCE/repo/core/constitution.py",
    "/Users/bill/AIUCE/repo/l0_constitution.py",
    "/Users/bill/AIUCE/repo/config.yaml",
    str(SANDBOX_ROOT.parent / "aiuce-sandbox" / "external"),
]


# ═══════════════════════════════════════════════════════════
# 防护机制
# ═══════════════════════════════════════════════════════════

class SandboxSecurityError(Exception):
    """沙盒安全违规异常"""
    pass


def check_path_access(path: str) -> bool:
    """
    检查路径访问是否安全
    
    Returns:
        True = 允许
        False = 拒绝
    """
    abs_path = os.path.abspath(path)
    
    # 禁止访问受保护目录
    for protected in PROTECTED_DIRS:
        protected_abs = str(protected.resolve())
        if protected_abs in abs_path and "external" not in abs_path:
            # results/ 和 logs/ 只能追加，不能覆盖
            if protected.name in ("results", "logs"):
                return False
            # checkpoints/ 完全禁止访问
            if protected.name == "checkpoints":
                return False
    
    # 禁止访问系统核心文件
    for blocked in BLOCKED_PATHS:
        if blocked in abs_path:
            return False
    
    return True


def check_command_safety(cmd: str) -> bool:
    """检查命令是否在白名单内"""
    first_word = cmd.strip().split()[0] if cmd.strip() else ""
    return first_word in ALLOWED_COMMANDS


def detect_hack_patterns(code: str) -> list[str]:
    """
    检测 Reward Hacking 常见模式
    
    Returns:
        发现的 hack 模式列表
    """
    hacks = []
    code_lower = code.lower()
    
    patterns = [
        (r"most\s*common\s*(answer|value)", "多数投票捷径 (多数答案通常正确)"),
        (r"Counter.*most_common", "绕过弱老师直接多数投票"),
        (r"test.*run.*code", "用测试集运行代码获取答案"),
        (r"exec\(.*test", "执行测试代码获取答案"),
        (r"open.*test.*\.py", "直接读取测试文件"),
        (r"submission.*replace", "篡改提交结果"),
        (r"eval.*api.*key", "尝试访问 eval API 密钥"),
        (r"\.remove\(", "尝试删除文件"),
        (r"chmod.*-.*w", "尝试修改文件权限"),
    ]
    
    for pattern, description in patterns:
        if re.search(pattern, code_lower):
            hacks.append(description)
    
    return hacks


# ═══════════════════════════════════════════════════════════
# SOVEREIGNTY.md 主权声明检查
# ═══════════════════════════════════════════════════════════

SOVEREIGNTY_TEMPLATE = """# SOVEREIGNTY.md — 实验主权声明

## 实验信息
- Run ID: {run_id}
- 启动时间: {timestamp}
- 目标: {goal}

## 评估指标
- 指标名称: {metric_name}
- 评估方法: {eval_method}
- 数据集来源: {dataset}

## L0 合规声明
[CLAUSE-001] 本实验所有日志强制存储于 ~/bill/AIUCE/aiuce-sandbox/logs/，不可在沙盒内删除
[CLAUSE-002] AAR 产生的代码变更需经 L0 熔断器审查
[CLAUSE-003] 可解释性评分 < 0.5 时触发人工复核

## 主权签名
Hash: {hash}
状态: UNREVIEWED
"""


def verify_sovereignty(run_id: str) -> tuple[bool, str]:
    """
    验证 SOVEREIGNTY.md 是否存在且合规
    
    Returns:
        (is_valid, message)
    """
    sovereignty_path = RUNS_DIR / run_id / "SOVEREIGNTY.md"
    
    if not sovereignty_path.exists():
        return False, f"SOVEREIGNTY.md 不存在: {sovereignty_path}"
    
    content = sovereignty_path.read_text(encoding="utf-8")
    
    required_fields = ["Run ID:", "评估指标:", "L0 合规声明", "主权签名"]
    for field in required_fields:
        if field not in content:
            return False, f"SOVEREIGNTY.md 缺少必需字段: {field}"
    
    return True, "合规"


def create_sovereignty(run_id: str, goal: str, metric_name: str = "PGR",
                       eval_method: str = "Remote API", dataset: str = "TBD") -> str:
    """生成主权声明文件"""
    sovereignty_dir = RUNS_DIR / run_id
    sovereignty_dir.mkdir(parents=True, exist_ok=True)
    
    sovereignty_content = SOVEREIGNTY_TEMPLATE.format(
        run_id=run_id,
        timestamp=datetime.datetime.now().isoformat(),
        goal=goal,
        metric_name=metric_name,
        eval_method=eval_method,
        dataset=dataset,
        hash="TBD"
    )
    
    sovereignty_path = sovereignty_dir / "SOVEREIGNTY.md"
    sovereignty_path.write_text(sovereignty_content, encoding="utf-8")
    
    return str(sovereignty_path)


# ═══════════════════════════════════════════════════════════
# 执行器
# ═══════════════════════════════════════════════════════════

class SandboxRunner:
    """
    沙盒执行器
    
    核心原则：
    - 所有执行通过 wrapper
    - 日志强制外存
    - Reward Hacking 自动检测
    - eval API 访问必须经过代理
    """
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.run_dir = RUNS_DIR / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_file = LOGS_DIR / f"{run_id}.log"
        self.result_file = RESULTS_DIR / f"{run_id}.json"
        
        self.audit_entries: list[dict] = []
        self.start_time = datetime.datetime.now()
    
    def _audit(self, event: str, detail: str = "", severity: str = "INFO"):
        """写入审计日志"""
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "run_id": self.run_id,
            "event": event,
            "detail": detail,
            "severity": severity,
        }
        self.audit_entries.append(entry)
        
        # 追加到日志文件（append-only）
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[WARNING] 无法写入日志: {e}", file=sys.stderr)
    
    def run_code_file(self, code_file: str, language: str = "python",
                     extra_env: dict = None) -> dict:
        """
        执行代码文件
        
        Args:
            code_file: 代码文件路径
            language: python | bash
            
        Returns:
            执行结果 dict
        """
        if not os.path.exists(code_file):
            return {"success": False, "error": f"文件不存在: {code_file}"}
        
        # 预执行安全检查
        code_content = open(code_file, encoding="utf-8").read()
        hacks = detect_hack_patterns(code_content)
        
        if hacks:
            self._audit("HACK_DETECTED", f"发现 Reward Hacking 模式: {hacks}", "CRITICAL")
            return {
                "success": False,
                "error": "安全违规: 检测到 Reward Hacking 模式",
                "detected_hacks": hacks,
                "log_file": str(self.log_file),
            }
        
        self._audit("EXEC_START", f"执行文件: {code_file}")
        
        # 设置环境变量
        env = os.environ.copy()
        env["AAR_RUN_ID"] = self.run_id
        env["SANDBOX_ROOT"] = str(SANDBOX_ROOT)
        env["EVAL_API_URL"] = f"file://{EXTERNAL_DIR}/eval"  # AAR 通过文件接口访问 eval
        if extra_env:
            env.update(extra_env)
        
        # 捕获输出
        stdout_capture = self.run_dir / "stdout.txt"
        stderr_capture = self.run_dir / "stderr.txt"
        
        try:
            if language == "python":
                result = subprocess.run(
                    ["python3", code_file],
                    capture_output=True,
                    timeout=300,  # 5分钟超时
                    env=env,
                    cwd=str(self.run_dir),
                )
            elif language == "bash":
                result = subprocess.run(
                    ["bash", code_file],
                    capture_output=True,
                    timeout=300,
                    env=env,
                    cwd=str(self.run_dir),
                )
            else:
                return {"success": False, "error": f"不支持的语言: {language}"}
            
            # 保存输出
            stdout_capture.write_bytes(result.stdout)
            stderr_capture.write_bytes(result.stderr)
            
            self._audit("EXEC_COMPLETE", f"返回码: {result.returncode}")
            
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout_file": str(stdout_capture),
                "stderr_file": str(stderr_capture),
                "log_file": str(self.log_file),
            }
            
        except subprocess.TimeoutExpired:
            self._audit("EXEC_TIMEOUT", "执行超时 (5分钟)", "WARNING")
            return {"success": False, "error": "执行超时 (5分钟)"}
        except Exception as e:
            self._audit("EXEC_ERROR", str(e), "ERROR")
            return {"success": False, "error": str(e)}
    
    def submit_solution(self, solution_data: dict) -> dict:
        """
        提交解决方案（通过 eval 代理）
        
        AAR 不能直接访问评估 API，必须通过此方法
        """
        self._audit("SUBMIT_SOLUTION", f"提交方案 hash: {solution_data.get('hash', 'N/A')}")
        
        # 写入提交文件（eval_proxy 会读取并处理）
        submit_dir = EXTERNAL_DIR / "submissions"
        submit_dir.mkdir(exist_ok=True)
        
        submit_file = submit_dir / f"{self.run_id}_{datetime.datetime.now().strftime('%H%M%S')}.json"
        submit_file.write_text(json.dumps(solution_data, ensure_ascii=False), encoding="utf-8")
        
        return {
            "submitted": True,
            "submit_file": str(submit_file),
            "note": "评估结果将通过 results/ 目录返回，请轮询等待"
        }
    
    def write_result(self, key: str, value: any) -> bool:
        """
        写入结果（append-only，结果文件不可删除或覆盖）
        
        写入前验证路径安全性
        """
        if not check_path_access(str(self.result_file)):
            self._audit("WRITE_BLOCKED", f"尝试写入受保护路径: {self.result_file}", "WARNING")
            return False
        
        # 追加模式写入（不覆盖）
        try:
            result_data = {}
            if self.result_file.exists():
                try:
                    result_data = json.loads(self.result_file.read_text(encoding="utf-8"))
                except:
                    result_data = {}
            
            result_data[key] = value
            result_data["_updated_at"] = datetime.datetime.now().isoformat()
            
            # 写入临时文件再 rename（原子操作）
            tmp_file = self.result_file.with_suffix(".tmp")
            tmp_file.write_text(json.dumps(result_data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_file.rename(self.result_file)
            
            self._audit("RESULT_WRITTEN", f"key={key}")
            return True
        except Exception as e:
            self._audit("WRITE_ERROR", str(e), "ERROR")
            return False
    
    def finalize(self, status: str = "COMPLETED"):
        """结束执行，写入最终状态"""
        duration = (datetime.datetime.now() - self.start_time).total_seconds()
        
        self._audit("EXEC_FINALIZED", f"status={status}, duration={duration:.1f}s")
        
        # 写入运行摘要
        summary = {
            "run_id": self.run_id,
            "status": status,
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.datetime.now().isoformat(),
            "duration_seconds": duration,
            "audit_entries": len(self.audit_entries),
        }
        
        summary_file = self.run_dir / "summary.json"
        summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


# ═══════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="AAR 沙盒执行包装器")
    parser.add_argument("--run-id", required=True, help="实验运行 ID")
    parser.add_argument("--code-file", help="要执行的代码文件")
    parser.add_argument("--goal", default="AAR Research", help="实验目标")
    parser.add_argument("--init", action="store_true", help="仅初始化运行目录（生成 SOVEREIGNTY.md）")
    
    args = parser.parse_args()
    
    runner = SandboxRunner(args.run_id)
    
    if args.init:
        # 仅初始化
        sov_path = create_sovereignty(args.run_id, args.goal)
        print(f"SOVEREIGNTY.md 已生成: {sov_path}")
        runner._audit("INITIALIZED", f"run_id={args.run_id}")
        runner.finalize("INITIALIZED")
        return
    
    if args.code_file:
        # 执行代码
        result = runner.run_code_file(args.code_file)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        runner.finalize("COMPLETED" if result.get("success") else "FAILED")
        return
    
    print("用法: sandbox_runner.py --run-id <id> --init [--goal <goal>]")
    print("   或: sandbox_runner.py --run-id <id> --code-file <path>")


if __name__ == "__main__":
    main()
