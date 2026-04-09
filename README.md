# Research Assistant Sys（科研助手系统）

这是一个基于 **Agno** 的科研助手系统。

当前已落地的专家是「论文结构化提取专家」，目标是：

- 搜索并下载 arXiv 论文
- 将 PDF 转为 Markdown
- 从论文中提取结构化优化问题（`MathOutline`）

> 当前版本以“论文结构化提取专家”为主，其它专家可在 `experts/` 按相同接口继续扩展。

## 三层架构

项目按三层组织：

- `interface/`：交互层（CLI / REPL 入口）
- `orchestrator/`：编排层（任务路由、执行、提取工作流）
- `experts/`：专家层（当前包含论文检索、定位、结构化提取等专家）

同时保留基础能力层：

- `foundation/`：配置、模型、适配器、执行框架、通用错误

## 快速开始

```bash
# 1) 安装（包名 research-assistant-sys；命令行入口 researchsys，仍保留 optibench 别名）
uv pip install -e .

# 2) 可选：安装更高质量 PDF 解析后端
uv pip install -e ".[marker]"   # 推荐
# 或
uv pip install -e ".[nougat]"

# 3) 配置模型 API（示例）
export OPENAI_API_KEY="sk-..."

# 4) 运行提取
python main.py "convex optimisation relaxation techniques"

# 指定论文
python main.py --arxiv-id 1406.0899
```

## 常用命令

```bash
# 搜索
python main.py search "convex optimisation" --max 5

# 下载（PDF + 可选 Markdown）
python main.py download 1406.0899
python main.py download 1406.0899 --output ./dataset --no-convert

# 本地 PDF 转 Markdown
python main.py convert-pdf path/to/paper.pdf -o paper.md

# 查看数据集条目
python main.py list

# 查看论文元数据
python main.py info 1406.0899

# REPL
python main.py repl --dataset-root ./dataset --top-k 5 --workers 1
```

## 输出结构

论文提取专家每次运行输出到 `dataset/<arxiv_id>/`，核心文件为：

- `paper.md`：论文 Markdown（若可用）
- `outline.json`：结构化提取结果
- `result.json`：简化结果索引
- `pipeline_metrics.json`：阶段指标（可选）

## 关键环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `OPTIBENCH_PROVIDER` | `openai` | 模型提供方 |
| `OPTIBENCH_MODEL` | `gpt-4o` | 模型 ID |
| `OPTIBENCH_WORKERS` | `1` | 批处理并发数 |
| `OPTIBENCH_DOMAIN` | `continuous` | arXiv 过滤域 |
| `OPTIBENCH_EXTRACTION_STRATEGY` | `unified` | `unified` / `locator_first` / `auto` |
| `OPTIBENCH_EXTRACT_MAX_CHARS` | `24000` | 提取输入裁切上限 |
| `OPTIBENCH_ARXIV_TIMEOUT` | `120` | arXiv 请求超时秒数 |

## 当前目录（精简后）

```text
.
├── main.py
├── interface/
├── orchestrator/
├── experts/
├── foundation/
├── docs/
├── scripts/
└── dataset/
```
