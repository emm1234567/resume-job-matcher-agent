"""简历解析与岗配评估 Agent - FastAPI Web 服务入口"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ============ 启动检查 ============
# 检查 python-multipart 依赖（FastAPI 文件上传必需）
try:
    import multipart  # noqa: F401
    _MULTIPART_AVAILABLE = True
except ImportError:
    _MULTIPART_AVAILABLE = False
    print("=" * 60, file=sys.stderr)
    print("[错误] 缺少依赖: python-multipart", file=sys.stderr)
    print("FastAPI 处理文件上传需要此库。", file=sys.stderr)
    print("请运行: pip install python-multipart", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

# 检查核心业务模块
try:
    from agent import ResumeJobMatcherAgent
    _AGENT_AVAILABLE = True
except Exception as e:
    _AGENT_AVAILABLE = False
    print(f"[警告] Agent 模块加载失败: {e}", file=sys.stderr)
    print("文件上传和匹配功能将不可用。请检查 .env 配置。", file=sys.stderr)
# ===================================

app = FastAPI(
    title="简历解析与岗配评估 Agent",
    description="输入简历与 JD，输出结构化评估报告",
    version="1.0.0",
)

# 静态文件目录
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)


class MatchResponse(BaseModel):
    """API 响应模型"""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


@app.get("/")
async def root():
    """返回前端页面"""
    html_file = STATIC_DIR / "index.html"
    if not html_file.exists():
        raise HTTPException(status_code=404, detail="前端页面未找到")
    return FileResponse(str(html_file))


@app.get("/api/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "ok",
        "service": "resume-job-matcher-agent",
        "python_multipart_ready": _MULTIPART_AVAILABLE,
        "agent_ready": _AGENT_AVAILABLE,
        "hint": "如果 python_multipart_ready 为 False，请运行 'pip install python-multipart'",
    }


# ============ 只有当依赖完整时才注册文件上传接口 ============
if _MULTIPART_AVAILABLE and _AGENT_AVAILABLE:
    from fastapi import UploadFile, File

    @app.post("/api/match", response_model=MatchResponse)
    async def match_resume(
        resume: UploadFile = File(..., description="简历文件 (PDF/Word/TXT)"),
        jd: UploadFile = File(..., description="岗位描述文件 (PDF/Word/TXT)"),
    ):
        """执行简历-JD 匹配评估"""
        try:
            # 创建临时目录
            with tempfile.TemporaryDirectory() as tmp_dir:
                # 保存上传的文件
                resume_path = Path(tmp_dir) / resume.filename
                jd_path = Path(tmp_dir) / jd.filename

                with open(resume_path, "wb") as f:
                    f.write(await resume.read())
                with open(jd_path, "wb") as f:
                    f.write(await jd.read())

                # 调用 Agent 执行评估
                agent = ResumeJobMatcherAgent()
                report = agent.run(str(resume_path), str(jd_path), verbose=False)

                # 返回结果
                # AgentReport 是 dataclass 而非 Pydantic 模型，
                # 用它自带的 to_json() 序列化，再解析回 dict 交给 FastAPI
                import json
                return MatchResponse(success=True, data=json.loads(report.to_json()))

        except Exception as e:
            import traceback
            traceback.print_exc()
            return MatchResponse(success=False, error=str(e))
else:
    # 依赖不完整时，注册一个禁用版本的接口，给出明确错误信息
    @app.post("/api/match")
    async def match_disabled():
        """依赖不完整时的占位接口"""
        error_msg = ""
        if not _MULTIPART_AVAILABLE:
            error_msg = "缺少依赖 python-multipart。请运行: pip install python-multipart"
        elif not _AGENT_AVAILABLE:
            error_msg = "Agent 模块加载失败。请检查 .env 文件中的 LLM_API_KEY 配置。"
        return MatchResponse(success=False, error=error_msg)
