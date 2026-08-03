# NL2SQL 端到端评测

评测集 `nl2sql_golden.yaml` 基于 `scripts/mysql/init/04-dw-data.sql` 的固定种子数据维护。每条 `expected_rows` 必须由可信 SQL 人工核验，不能直接采用 Agent 输出。

先启动中间件，并完成一次知识库构建：

```bash
./run.sh start middleware
./run.sh build-kb
```

运行 100 条黄金集：

```bash
uv run python -m backend.app.scripts.run_nl2sql_eval
```

运行器会调用完整的检索、LLM、SQL 校验和执行链路，并把 JSON 报告写入 `eval/reports/`。默认通过率门槛为 80%，未达到时命令以退出码 `1` 结束。

可指定报告位置或临时调整门槛：

```bash
uv run python -m backend.app.scripts.run_nl2sql_eval \
  --report /tmp/nl2sql-eval.json \
  --min-pass-rate 0.8
```

## 召回评测

`recall_golden.yaml` 评测检索层的三个数据源：字段（Qdrant）、指标（Qdrant）和字段取值（Elasticsearch）。每个样本指定一个检索表达和必须出现在 Top K 内的元数据 ID，运行器输出 Macro / Micro Recall@K。

该评测有意不调用 LLM 扩词，而是直接对同一个 Qdrant 或 Elasticsearch repository 发起查询。这样结果可复现，适合对比 `top_k`、分数阈值、embedding 模型或元数据别名调整前后的召回质量；它与端到端 NL2SQL 评测互补，不替代后者。

知识库构建完成后运行：

```bash
uv run python -m backend.app.scripts.run_recall_eval
```

默认阈值是 Macro Recall@5 不低于 80%。可以覆盖所有样本的 K 值，或者单独调整向量和取值全文检索阈值：

```bash
uv run python -m backend.app.scripts.run_recall_eval \
  --top-k 10 \
  --vector-score-threshold 0.5 \
  --value-score-threshold 0.4 \
  --report /tmp/recall-eval.json
```

报告同样写入 `eval/reports/`，包含每条样本的召回 ID、命中 ID、漏召回 ID、耗时，以及按 `column`、`metric`、`value` 分类的汇总。

## LLM-as-Judge 评测

这项评测复用同一份 100 条黄金集和完整生产图：检索、生成 SQL、验证、必要时纠错和执行均真实运行。随后由独立的非 GPT 裁判模型检查问题意图、SQL 对 schema/指标的依据，以及实际结果与黄金结果的业务等价性。

生成模型继续使用 `LLM_*`；裁判默认模型为 `deepseek-chat`，建议在 `.env` 单独设置以下变量，避免与生成模型共享：

```bash
JUDGE_LLM_MODEL_NAME=deepseek-chat
JUDGE_LLM_API_KEY=你的 DeepSeek API Key
JUDGE_LLM_BASE_URL=https://api.deepseek.com
JUDGE_LLM_USER_AGENT=storekeeper-nl2sql-eval
```

启动中间件并构建知识库后直接运行，无需启动 FastAPI 或前端：

```bash
uv run python -m backend.app.scripts.run_llm_judge_eval
```

裁判会输出 `pass`、`minor_error` 或 `major_error`，并给出 1 到 5 分、三个维度分数和可核验的证据。响应无法解析时只会请求模型再输出一次；Agent 执行失败、空 SQL 或包含写操作的 SQL 则由硬规则直接标记为严重错误。报告默认写入 `eval/reports/`，同时保留生成 SQL、筛选后的 schema/指标上下文、实际/黄金结果、原始裁判回复与确定性结果比对。

运行器会先向 Judge 模型发起一次连通性检查；若鉴权、余额、限流或网络失败，评测会在运行任何 Agent 用例前直接终止。运行过程中 Judge 调用失败同样会立即中止，不会继续消耗后续 100 条生成链路调用。

默认要求裁判通过率不低于 80%，可单独调整：

```bash
uv run python -m backend.app.scripts.run_llm_judge_eval \
  --min-judge-pass-rate 0.8 \
  --report /tmp/llm-judge-eval.json
```
