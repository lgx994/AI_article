# 🧠 认知提升文章生成智能体 - 7节点DAG版本

基于 DeepSeek API 的多节点文章创作智能体，采用 **7节点DAG架构**，每个节点职责单一、提示词精炼。

## 🏗️ 架构图

```
┌─────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Trigger │───▶│ StateManager│───▶│ VariablePool│───▶│   Planner   │
│  触发器  │    │   状态管理   │    │   变量抽取   │    │  写作规划    │
└─────────┘    └─────────────┘    └─────────────┘    └──────┬──────┘
                                                            │
┌─────────┐    ┌─────────────┐    ┌─────────────┐          │
│  Push   │◀───│   Reviewer  │◀───│    Writer   │◀─────────┘
│  推送   │    │    审核     │    │   文章写作   │
└─────────┘    └──────┬──────┘    └─────────────┘
                      │
                      │ 不通过
                      ▼
               ┌─────────────┐
               │   Rewriter  │───(重试，最多3次)───┐
               │    重写     │                     │
               └─────────────┘◀────────────────────┘
```

## 📁 文件结构

```
cognition_agent_dag/
├── agent.py              # 7节点DAG核心实现
├── run.py                # 运行入口
├── feishu_pusher.py      # 飞书推送模块
├── scheduler.py          # 定时调度配置
├── README.md             # 本文件
│
├── planner_prompt.txt    # 节点4: 写作规划提示词 (用户提供)
├── writer_prompt.txt     # 节点5: 文章写作提示词 (用户提供)
├── reviewer_prompt.txt   # 节点6: 审核提示词 (用户提供)
└── rewriter_prompt.txt   # 节点7b: 重写提示词 (用户提供)
```

## 🚀 快速开始

### 1. 准备提示词文件

确保以下4个提示词文件在同一目录：
- `planner_prompt.txt` - 写作规划节点提示词
- `writer_prompt.txt` - 文章写作节点提示词
- `reviewer_prompt.txt` - 审核节点提示词
- `rewriter_prompt.txt` - 重写节点提示词

### 2. 环境配置

```bash
# 设置环境变量
export DEEPSEEK_API_KEY="your-api-key"
export FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
export FEISHU_APP_ID="your-app-id"        # 可选
export FEISHU_APP_SECRET="your-app-secret" # 可选
```

### 3. 运行

```bash
# 生成今天的文章
python run.py

# 指定天数
python run.py --day 5

# 只生成不推送
python run.py --no-push

# 指定提示词目录
python run.py --prompt-dir /path/to/prompts
```

## 🔄 节点详解

| 节点 | 名称 | 职责 | 调用LLM? | 提示词文件 |
|------|------|------|----------|-----------|
| 1 | Trigger | 触发判断 | ❌ | - |
| 2 | StateManager | 加载/保存状态 | ❌ | - |
| 3 | VariablePool | 抽取文章变量 | ❌ | - |
| 4 | **Planner** | 生成写作规划 | ✅ | `planner_prompt.txt` |
| 5 | **Writer** | 撰写文章正文 | ✅ | `writer_prompt.txt` |
| 6 | **Reviewer** | 审核文章质量 | ✅ | `reviewer_prompt.txt` |
| 7b | **Rewriter** | 根据审核意见重写 | ✅ | `rewriter_prompt.txt` |
| 7a | Push | 推送到飞书 | ❌ | - |

## 📊 与原版本的对比

| 特性 | 原单节点版本 | 新7节点DAG版本 |
|------|-------------|---------------|
| 提示词长度 | ~8000字一次性 | 分散到3-4个节点，每个1000-2000字 |
| 规划阶段 | 混在写作中，常被忽略 | 独立节点，强制执行 |
| 审核机制 | 简单自检 | 独立审核节点，18项检查清单 |
| 容错能力 | 生成失败就失败 | 审核不通过可自动重写，最多3次 |
| 外部素材 | 无 | 支持（通过LLM联网搜索） |
| 可追溯性 | 弱 | 保存规划JSON、审核结果、重试记录 |

## 📝 输出文件

每次执行会生成：

```
output/
├── day001.md              # 文章正文
├── day001_plan.json       # 写作规划（节点4输出）
└── day001_review.txt      # 审核结果（节点6输出）
```

## 🚀 部署到GitHub Actions

```bash
# 生成工作流文件（每天北京时间20:00）
python scheduler.py --hour 20 --minute 0
```

然后在GitHub仓库设置 Secrets:
- `DEEPSEEK_API_KEY`
- `FEISHU_WEBHOOK`
- `FEISHU_APP_ID` (可选)
- `FEISHU_APP_SECRET` (可选)

## 🔧 自定义配置

### 修改重试次数

在 `agent.py` 中修改 `CognitionDAG` 类的初始化：

```python
self.max_retries = 3  # 修改为想要的次数
```

### 添加新的文章类型

在 `agent.py` 的 `VariablePool` 类中修改：

```python
ARTICLE_TYPES = [
    "叙事主导型", "模型主导型", "观察笔记型",
    "书信/对话型", "场景切片型", "问答/假想对话型",
    # 添加新类型...
]
```

## 📄 License

MIT
