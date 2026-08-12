"""一键启动脚本：启动 Web 服务并打印可点击的访问地址"""
import uvicorn

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 简历解析与岗配评估 Agent 服务启动中...")
    print("=" * 50)
    print("👉 在浏览器中访问以下地址使用 Web 界面：")
    print("   http://127.0.0.1:8000")
    print("=" * 50)
    print("按 CTRL+C 可停止服务\n")

    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
