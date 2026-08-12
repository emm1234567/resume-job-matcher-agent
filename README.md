# 简历解析与岗配评估 Agent

> 输入一份简历 + 一份 JD，自动完成结构化抽取、多维度经验召回、匹配评分、幻觉校验与面试题生成，端到端输出标准化评估报告。

面向求职场景的 LLM 智能匹配系统。不直接信任大模型的自由文本输出，而是通过 **结构化 Schema 约束 + 多维度 RAG 召回 + 幻觉校验闭环** 三层机制，保证评估结果的可解释性与可信度。

---

## 项目亮点

本项目在设计上规避了"套壳 LLM"的常见问题，重点体现三项企业级技术思维：

### 1. 结构化抽取（Structured Output）
不直接让大模型返回文本，而是基于 Pydantic v2 定义数据模型，将 JSON Schema 注入提示词强制 LLM 输出标准结构。配合自实现的栈式大括号解析器（兼容代码块包裹、字段内嵌 `}`、`<think>` 标签干扰）与"校验失败→错误回喂→重试"的自纠错闭环，保障结构化抽取的稳定性。

### 2. 多维度 RAG
以 JD 的每项硬性要求与每条职责作为独立 Query，从简历中多路召回相关项目经验片段，去重加权排序。双引擎设计：优先 Embedding 语义召回，服务不可用时自动降级到 BM25 + jieba 中文分词，保证离线/无 Key 环境下召回链路不中断。

### 3. 幻觉校验机制
从匹配报告中抽取"可证伪断言"（技能判断、优势陈述、总结结论），基于关键词在简历原文检索证据，由 LLM 仅依据给定证据判定 `supported` / `unsupported` / `fabricated`。关键设计——**强制用本地检索结果覆盖模型自填证据字段**，阻断模型自行编造依据的路径，有效抑制"凭空夸大候选人经历"的倾向。

---

## 系统架构

### 数据流

```
简历文件(PDF/Word/TXT) ─┐
                        ├─→ 文档解析(纯文本) ─→ LLM结构化抽取(Resume) ─┐
JD 文件 ────────────────┘                                          ├─→ 多路RAG召回证据 ─→ 规则匹配+LLM评分 ─→ MatchResult
                                                                  └─→ JD ──────────────────────────────┘        │
                                                                                │                                 ├─→ 幻觉校验
                                                                                └─────────────────────────────────┴─→ 面试题生成
                                                                                                                    │
                                                                                                              最终 JSON 报告
```

### 分层架构

```
app.py            ← FastAPI Web 服务入口（含路由和静态文件）
run.py            ← 一键启动脚本（打印可点击的访问地址）
cli.py            ← 命令行入口
agent.py          ← 编排层：串联完整流水线
core/             ← 业务逻辑：抽取 / 匹配 / 校验 / 面试
rag/              ← 多维度检索：Embedding + BM25 双引擎
llm/              ← LLM 客户端：对话 + 结构化输出
parsers/          ← 文档解析：PDF / Word / TXT
schemas/          ← 数据结构：Pydantic 模型定义
config.py         ← 配置中心：环境变量管理
static/           ← 前端静态文件（HTML/CSS/JS）
```

设计原则：**上层依赖下层，下层不感知上层**，改一层不牵连其他层。

---

## 目录结构

```
.
├── app.py                     # FastAPI Web 服务入口
├── run.py                     # 一键启动脚本
├── cli.py                     # 命令行入口
├── agent.py                   # Agent 编排层（解析→抽取→RAG→匹配→校验→面试）
├── config.py                  # 配置中心（密钥走环境变量，frozen 不可变）
├── requirements.txt           # 依赖清单
├── .env.example               # 环境变量模板
├── static/                    # 前端静态文件
│   └── index.html             #   Web 界面
├── schemas/                   # 结构化数据模型（Pydantic v2）
│   ├── resume.py              #   简历结构
│   ├── job.py                 #   JD 结构
│   └── match.py               #   匹配结果结构
├── parsers/                   # 文档解析器
│   ├── base.py                #   统一入口 + 扩展名白名单
│   ├── pdf_parser.py          #   PDF 解析（pdfplumber）
│   └── docx_parser.py         #   Word 解析（python-docx）
├── llm/
│   └── client.py              # LLM 客户端（结构化输出 + 重试自纠错）
├── rag/                       # 多维度 RAG
│   ├── tokenizer.py           #   分词（jieba 优先，正则降级）
│   ├── indexer.py             #   简历切块
│   └── retriever.py           #   双引擎召回 + 多路召回
├── core/                      # 核心业务
│   ├── extractor.py           #   简历/JD 抽取
│   ├── matcher.py             #   规则基线 + RAG 证据 + LLM 评分
│   ├── verifier.py            #   幻觉校验
│   └── interview.py           #   定制面试题生成
└── sample_data/               # 示例数据
    ├── sample_resume.txt
    └── sample_jd.txt
```

---

## 快速开始

### 1. 环境要求

- Python 3.10+
- 任一 OpenAI 兼容的 LLM 服务（OpenAI / DeepSeek / Moonshot / 本地 vLLM 等）

### 2. 安装依赖

```bash
# 克隆仓库
git clone https://github.com/你的用户名/你的仓库名.git
cd 你的仓库名

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置 API Key

```bash
# 复制环境变量模板
cp .env.example .env
# Windows PowerShell: Copy-Item .env.example .env
```

编辑 `.env`，填入你的 API Key。下面以 DeepSeek 为例（性价比最高）：

```dotenv
LLM_API_KEY=sk-你的DeepSeekKey
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_TEMPERATURE=0.2

# DeepSeek 暂无独立 Embedding 服务，留空走 BM25 降级
EMBEDDING_API_KEY=
EMBEDDING_BASE_URL=
EMBEDDING_MODEL=
ENABLE_EMBEDDING_RAG=false
```

其他服务商配置参考下表：

| 服务商 | `LLM_BASE_URL` | `LLM_MODEL` 推荐 |
|--------|----------------|------------------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| 本地 vLLM | `http://localhost:8000/v1` | 你部署的模型名 |

---

## 使用方式

### 方式一：Web 界面（推荐）

启动 Web 服务：

```bash
python run.py
```

终端会打印可点击的访问地址，浏览器打开 `http://127.0.0.1:8000` 即可使用。

Web 界面功能：
- 📁 **拖拽上传**：支持 PDF、Word、TXT 格式
- 📊 **可视化报告**：总分、维度评分、技能匹配一目了然
- 💡 **改进建议**：针对性提升方案
- 🎤 **面试准备**：定制面试题及出题依据
- ⚠️ **幻觉校验**：自动检测模型是否夸大候选人经历

**API 文档**：启动后可访问 `http://127.0.0.1:8000/docs` 查看完整的 Swagger 交互式 API 文档。

### 方式二：命令行

```bash
python cli.py --resume sample_data/sample_resume.txt --jd sample_data/sample_jd.txt -v -o report.json
```

参数说明：

| 参数 | 说明 |
|------|------|
| `--resume` | 简历文件路径（PDF/Word/TXT） |
| `--jd` | JD 文件路径（PDF/Word/TXT） |
| `--output` / `-o` | 评估报告输出 JSON 路径（可选） |
| `--verbose` / `-v` | 打印阶段进度到 stderr（可选） |

### 方式三：API 调用

如果你需要将 Agent 集成到其他系统，可直接调用 API：

```bash
# 健康检查
curl http://127.0.0.1:8000/api/health

# 执行评估
curl -X POST "http://127.0.0.1:8000/api/match" \
  -F "resume=@你的简历.pdf" \
  -F "jd=@你的岗位描述.docx"
```

---

## 输出示例

运行后终端会输出人类可读的评估摘要，同时（若指定 `-o`）生成结构化 JSON 报告，包含以下字段：

- `overall_score`：总体匹配分（0-100）
- `dimension_scores`：五维度评分（技能契合 / 经验年限 / 项目相关性 / 学历 / 语言）
- `skill_matches`：每项硬性要求的匹配明细（含状态、年限对比、证据原文）
- `gap_analysis`：整体差距分析
- `strengths` / `weaknesses`：优势与短板
- `improvement_suggestions`：可执行的改进建议
- `interview_questions`：6-8 道定制面试题（含出题依据）
- `verification_issues`：幻觉校验报告（supported / unsupported / fabricated）

---

## 常见问题

### Q: 启动后访问页面报错 "Form data requires python-multipart"？
A: 缺少依赖。请运行 `pip install python-multipart`。

### Q: Web 页面打不开，显示 404？
A: 
1. 确认访问的是 `http://127.0.0.1:8000/`（带末尾的 `/`）
2. 访问 `http://127.0.0.1:8000/api/health` 检查服务状态
3. 如果 `agent_ready` 为 false，说明 `.env` 文件配置有误

### Q: 评估失败，提示 API Key 错误？
A: 检查 `.env` 文件中的 `LLM_API_KEY` 是否正确，`LLM_BASE_URL` 是否匹配服务商。

### Q: 支持哪些文件格式？
A: PDF (`.pdf`)、Word (`.docx`)、纯文本 (`.txt`)。注意：旧版 `.doc` 格式不直接支持，请先转换为 `.docx`。

---

## 核心模块说明

### `llm/client.py` — 结构化输出核心

`chat_structured()` 方法实现结构化输出的完整链路：
1. 将目标 Pydantic 模型的 JSON Schema 注入 system prompt
2. 调用 LLM 获取输出
3. 用 `_extract_json()` 容错解析（处理代码块包裹、栈式匹配大括号）
4. Pydantic 校验
5. 失败则把错误信息回喂模型，最多重试 3 轮

### `rag/retriever.py` — 多路召回

`multi_retrieve()` 是本项目 RAG 的核心：对多个 Query 分别召回，按"排名权重 + 命中频次"加权去重排序，避免单次检索只能覆盖单一维度的信息损失。

### `core/matcher.py` — 混合匹配器

三段式设计：
1. **规则基线**：`_rule_match_skills()` 用确定性规则生成技能四态匹配（归一化匹配 + 年限比对）
2. **RAG 证据**：多路召回相关经验片段
3. **LLM 评分**：把规则基线 + 召回证据注入 LLM，约束其在"有据可依"前提下输出维度评分

### `core/verifier.py` — 幻觉校验

`verify()` 流程：抽取可证伪断言 → 关键词检索证据句 → LLM 仅依证据判定三态 → **强制覆盖模型自填证据字段**。

---

## 技术栈

| 类别 | 技术 | 用途 |
|------|------|------|
| 语言 | Python 3.10+ | - |
| Web 框架 | FastAPI + Uvicorn | 提供 Web 界面和 API 服务 |
| 数据模型 | Pydantic v2 | 结构化 Schema 定义与校验 |
| LLM 接口 | openai-python | 兼容 OpenAI 协议的任意服务 |
| PDF 解析 | pdfplumber | 简历 PDF 文本抽取 |
| Word 解析 | python-docx | .docx 文本抽取 |
| 关键词检索 | rank-bm25 | Embedding 降级方案 |
| 中文分词 | jieba | 提升 BM25 召回质量 |
| 向量计算 | numpy | 余弦相似度 |
| 配置管理 | python-dotenv | 环境变量加载 |

---

## 安全设计

- **密钥隔离**：API Key 仅从环境变量读取，`.env` 已加入 `.gitignore`，绝不进代码库
- **文件白名单**：文档解析层做扩展名白名单校验，仅放行 PDF/DOCX/TXT
- **输入截断**：LLM 输入文本 12000 字符硬截断，防 token 超限与费用失控
- **配置不可变**：`@dataclass(frozen=True)` 保证运行期配置不被篡改
- **数据视图分离**：`raw_text` 字段 `exclude=True`，对内保留原文供检索，对外不泄露

---

## License

MIT
