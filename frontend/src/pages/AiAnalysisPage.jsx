import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  BarChart3,
  Bot,
  BrainCircuit,
  CircleGauge,
  FileText,
  LoaderCircle,
  Network,
  Sparkles,
} from "lucide-react";

import { CHART_PALETTE, formatNumber } from "../constants";
import { EmptyState, Field, StatusBadge } from "../components/ui";
import { UmapChart } from "../components/UmapChart";

function SafeMarkdown({ text }) {
  if (!text) return null;
  try {
    return (
      <ReactMarkdown remarkPlugins={[remarkGfm]} className="ai-report-markdown">
        {text}
      </ReactMarkdown>
    );
  } catch {
    return <pre className="ai-report-markdown">{text}</pre>;
  }
}

function StatTile({ label, value, detail, icon: Icon }) {
  return (
    <div className="ai-stat-tile">
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        {detail ? <small>{detail}</small> : null}
      </div>
      <Icon size={18} />
    </div>
  );
}

function TypeBars({ items = [], total = 0 }) {
  if (!items.length) return <EmptyState title="暂无组成数据" description="执行检索后将显示 Top-K 细胞类型组成。" />;
  return (
    <div className="ai-type-bars">
      {items.slice(0, 8).map((item, index) => {
        const percent = total ? (item.count / total) * 100 : 0;
        return (
          <div className="ai-type-row" key={`${item.value}-${index}`}>
            <div className="ai-type-label">
              <span>{item.value || "-"}</span>
              <b>{item.count}</b>
            </div>
            <div className="ai-bar-track">
              <span style={{ width: `${percent}%`, backgroundColor: CHART_PALETTE[index % CHART_PALETTE.length] }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function DistanceGauge({ stats }) {
  if (!stats) return <EmptyState title="暂无距离统计" description="执行检索后将显示距离分布摘要。" />;
  const span = Math.max(stats.max - stats.min, 0.000001);
  const meanPercent = Math.min(100, Math.max(0, ((stats.mean - stats.min) / span) * 100));
  return (
    <div className="ai-distance-gauge">
      <div className="gauge-line">
        <span className="gauge-mean" style={{ left: `${meanPercent}%` }} />
      </div>
      <div className="gauge-values">
        <span>Min <b>{stats.min.toFixed(4)}</b></span>
        <span>Mean <b>{stats.mean.toFixed(4)}</b></span>
        <span>Max <b>{stats.max.toFixed(4)}</b></span>
      </div>
    </div>
  );
}

export function AiAnalysisPage({ workspace, guestMode }) {
  const hasHits = Boolean(workspace.searchResult?.hits?.length);
  const queryCell = workspace.searchResult?.query_cell;
  const totalHits = workspace.searchResult?.hits?.length || 0;
  const dominantType = workspace.topKTypeStats?.[0];
  const analysisDisabled = !hasHits || Boolean(workspace.busy) || workspace.llmBusy || !workspace.canSearch;
  const ragDisabled = !workspace.canSearch || Boolean(workspace.busy) || workspace.llmBusy || !workspace.activeIndex?.ready || !workspace.ragQuestion.trim();
  const reportTitle = queryCell?.cell_id ? `查询细胞 ${queryCell.cell_id}` : "等待检索结果";
  const usage = workspace.llmAnalysis?.usage;
  const tokenDetail = usage?.total_tokens ? `Token ${usage.total_tokens}` : "尚未生成报告";
  const datasetName = queryCell?.dataset_name || queryCell?.dataset_id || "-";
  const matrixHits = useMemo(() => workspace.searchResult?.hits || [], [workspace.searchResult]);
  function submitAnalysisFromKeyboard(event) {
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    if (!analysisDisabled) workspace.handleAnalyzeSearchResult();
  }

  function submitRagFromKeyboard(event) {
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    if (!ragDisabled) workspace.handleRagSearch();
  }

  return (
    <div className="ai-dashboard">
      <section className="ai-hero-panel">
        <div className="ai-hero-copy">
          <p>AI Analysis Board</p>
          <h2>智能邻域分析大屏</h2>
          <span>{hasHits ? `${reportTitle}，来自 ${datasetName}` : "先在分析工作台执行一次 Top-K 检索，再回到这里生成 AI 报告。"}</span>
        </div>
        <div className="ai-hero-actions">
          <StatusBadge value={workspace.llmAnalysis?.model || "Qwen/Qwen3-8B"} tone="teal" dot={false} />
          <label className="ai-thinking-toggle">
            <BrainCircuit size={15} />
            <span>思考模式</span>
            <input
              type="checkbox"
              checked={workspace.llmEnableThinking}
              onChange={(event) => workspace.setLlmEnableThinking(event.target.checked)}
              disabled={workspace.llmBusy}
            />
          </label>
        </div>
      </section>

      <section className="ai-dashboard-grid">
        <div className="ai-left-stack">
          <div className="ai-stat-grid">
            <StatTile label="Query Cell" value={queryCell?.cell_id || "-"} detail={datasetName} icon={Bot} />
            <StatTile label="Top-K Hits" value={formatNumber(totalHits)} detail={dominantType ? `主类型 ${dominantType.value}` : "暂无组成"} icon={Network} />
            <StatTile label="Mean Distance" value={workspace.topKDistanceStats ? workspace.topKDistanceStats.mean.toFixed(4) : "-"} detail={workspace.topKDistanceStats ? "ANN L2 distance" : "等待检索"} icon={CircleGauge} />
            <StatTile label="AI Report" value={workspace.llmAnalysis ? "Ready" : "Pending"} detail={tokenDetail} icon={FileText} />
          </div>

          <div className="ai-panel ai-control-panel">
            <div className="ai-panel-heading">
              <div>
                <p>Prompt Control</p>
                <h3><Sparkles size={16} />自然语言 RAG 检索</h3>
              </div>
              <StatusBadge value={workspace.llmEnableThinking ? "Thinking" : "Fast"} tone={workspace.llmEnableThinking ? "warm" : "good"} dot={false} />
            </div>
            {!workspace.canSearch ? (
              <p className="ai-panel-note">{guestMode ? "当前为只读浏览模式，登录后可生成 AI 分析。" : "当前角色没有生成 AI 分析的权限。"}</p>
            ) : null}
            <Field label="自然语言问题">
              <textarea
                className="ai-prompt-input"
                value={workspace.ragQuestion}
                onChange={(event) => workspace.setRagQuestion(event.target.value)}
                onKeyDown={submitRagFromKeyboard}
                placeholder="例如：帮我检索肝细胞中和健康样本相似的 Top-K 细胞，并解释这些邻域有什么特点"
                disabled={workspace.llmBusy}
              />
            </Field>
            <button className="primary-button full-button" onClick={workspace.handleRagSearch} disabled={ragDisabled}>
              {workspace.llmBusy ? <LoaderCircle size={17} className="spin" /> : <Sparkles size={17} />}
              执行 RAG 检索并回答
            </button>
            {workspace.ragResult?.retrieval_plan ? (
              <div className="rag-plan-box">
                <span>检索策略：{workspace.ragResult.retrieval_plan.strategy}</span>
                <span>数据集：{(workspace.ragResult.retrieval_plan.dataset_ids || []).join(", ") || "-"}</span>
                <span>条件：{Object.entries(workspace.ragResult.retrieval_plan.metadata_filters || {}).map(([key, value]) => `${key}=${value}`).join(", ") || "无"}</span>
                <span>代表细胞：{workspace.ragResult.retrieval_plan.cell_id || workspace.ragResult.retrieval_plan.representative_cell?.cell_id || "-"}</span>
              </div>
            ) : null}
          </div>

          <div className="ai-panel ai-control-panel">
            <div className="ai-panel-heading">
              <div>
                <p>Result Explanation</p>
                <h3><Sparkles size={16} />已有检索结果分析</h3>
              </div>
            </div>
            <Field label="分析重点">
              <textarea
                className="ai-prompt-input"
                value={workspace.llmQuestion}
                onChange={(event) => workspace.setLlmQuestion(event.target.value)}
                onKeyDown={submitAnalysisFromKeyboard}
                placeholder="例如：重点分析细胞类型组成、疾病差异或距离分布"
                disabled={workspace.llmBusy}
              />
            </Field>
            <button className="primary-button full-button" onClick={workspace.handleAnalyzeSearchResult} disabled={analysisDisabled}>
              {workspace.llmBusy ? <LoaderCircle size={17} className="spin" /> : <Sparkles size={17} />}
              生成 AI 分析报告
            </button>
            {workspace.llmError ? <p className="ai-analysis-error">{workspace.llmError}</p> : null}
          </div>

          <div className="ai-panel">
            <div className="ai-panel-heading">
              <div>
                <p>Cell Composition</p>
                <h3><BarChart3 size={16} />Top-K 细胞组成</h3>
              </div>
            </div>
            <TypeBars items={workspace.topKTypeStats} total={totalHits} />
          </div>

          <div className="ai-panel">
            <div className="ai-panel-heading">
              <div>
                <p>Distance Summary</p>
                <h3><CircleGauge size={16} />距离分布</h3>
              </div>
            </div>
            <DistanceGauge stats={workspace.topKDistanceStats} />
          </div>
        </div>

        <div className="ai-main-stack">
          <div className="ai-panel ai-umap-panel">
            <div className="ai-panel-heading">
              <div>
                <p>Spatial Retrieval View</p>
                <h3><Network size={16} />检索后 UMAP 空间图</h3>
              </div>
              <StatusBadge value={`${totalHits || 0} hits`} tone="teal" dot={false} />
            </div>
            <div className="ai-umap-canvas">
              <UmapChart
                points={workspace.visPoints}
                queryCell={queryCell}
                hits={matrixHits}
                colorBy={workspace.appliedVisualState.colorBy}
                stats={workspace.visualStats}
                filters={workspace.appliedVisualState.filters}
                onPickCell={workspace.handlePickVisualizationCell}
                emptyMessage="等待 UMAP 数据"
              />
            </div>
          </div>

          <div className="ai-panel ai-report-panel">
            <div className="ai-panel-heading">
              <div>
                <p>Generated Markdown Report</p>
                <h3><FileText size={16} />AI 分析报告</h3>
              </div>
              {usage?.total_tokens ? <StatusBadge value={`Token ${usage.total_tokens}`} tone="neutral" dot={false} /> : null}
            </div>
            {workspace.llmAnalysis?.analysis ? (
              <SafeMarkdown text={workspace.llmAnalysis.analysis} />
            ) : (
              <EmptyState title="暂无 AI 报告" description="执行检索后点击生成，模型会基于 Top-K 邻域和元数据输出 Markdown 分析。" />
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
