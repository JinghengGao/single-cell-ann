import { useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  Download,
  Eraser,
  Filter,
  FlaskConical,
  Layers3,
  LoaderCircle,
  Maximize2,
  Play,
  RefreshCw,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";

import { CHART_PALETTE, COLOR_FIELD_LABELS, METADATA_FIELDS, colorByLabel, formatNumber } from "../constants";
import { UmapChart } from "../components/UmapChart";
import { AccessNotice, EmptyState, Field, IconButton, StatusBadge } from "../components/ui";

function LegendRows({ items = [], limit = 12 }) {
  if (!items.length) return <p className="mini-empty">暂无分组数据</p>;
  return items.slice(0, limit).map((item, index) => (
    <div className="legend-row" key={`${item.value}-${index}`}>
      <span className="legend-swatch" style={{ backgroundColor: CHART_PALETTE[index % CHART_PALETTE.length] }} />
      <span title={item.value || "-"}>{item.value || "-"}</span>
      <strong>{formatNumber(item.count)}</strong>
    </div>
  ));
}

function ResultsTable({ hits, compact = false }) {
  if (!hits?.length) {
    return <EmptyState title="暂无检索结果" description="选择细胞并执行查询后，Top-K 邻域将在此显示。" />;
  }
  if (compact) {
    return (
      <div className="compact-results">
        {hits.slice(0, 6).map((hit, index) => (
          <div className="compact-result-row" key={`${hit.dataset_id}:${hit.cell_id}`} style={{ "--reveal-order": index }}>
            <strong>{hit.rank}</strong>
            <div>
              <span>{hit.cell_id}</span>
              <small>{hit.cell_type || "-"}</small>
            </div>
            <b>{hit.distance.toFixed(4)}</b>
          </div>
        ))}
      </div>
    );
  }
  return (
    <div className="table-scroll result-drawer-table">
      <table>
        <thead>
          <tr>
            <th>Rank</th>
            <th>数据集</th>
            <th>Cell ID</th>
            <th>细胞类型</th>
            <th>Disease</th>
            <th>Age group</th>
            <th>Tissue</th>
            <th>Distance</th>
          </tr>
        </thead>
        <tbody>
          {hits.map((hit, index) => (
            <tr className="result-drawer-row" key={`${hit.dataset_id}:${hit.cell_id}`} style={{ "--reveal-order": Math.min(index, 10) }}>
              <td><strong>{hit.rank}</strong></td>
              <td>{hit.dataset_name || hit.dataset_id}</td>
              <td className="mono-cell">{hit.cell_id}</td>
              <td>{hit.cell_type || "-"}</td>
              <td>{hit.disease || "-"}</td>
              <td>{hit.AgeGroup || "-"}</td>
              <td>{hit.tissue || "-"}</td>
              <td>{hit.distance.toFixed(4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function matchesVisualFilters(cell, filters = {}) {
  return Object.entries(filters).every(([fieldName, value]) => !value || cell?.[fieldName] === value);
}

export function AnalysisPage({ workspace, guestMode }) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const appliedColorBy = workspace.appliedVisualState.colorBy;
  const legendItems = workspace.visualStats?.by_color?.length
    ? workspace.visualStats.by_color
    : workspace.visualStats?.by_dataset || [];
  const hasHits = Boolean(workspace.searchResult?.hits?.length);
  const totalHitCount = workspace.searchResult?.hits?.length || 0;
  const visibleOverlayHitCount = useMemo(
    () => (workspace.searchResult?.hits || []).filter((hit) => hit.umap && matchesVisualFilters(hit, workspace.appliedVisualState.filters)).length,
    [workspace.appliedVisualState.filters, workspace.searchResult],
  );
  const queryDisabled =
    Boolean(workspace.busy) || !workspace.canSearch || !workspace.queryCellId || !workspace.activeIndex?.ready;
  const selectedDatasetText = useMemo(
    () => workspace.appliedVisualDatasets.map((dataset) => dataset.name).join(", ") || "未选择数据集",
    [workspace.appliedVisualDatasets],
  );

  useEffect(() => {
    if (!drawerOpen) return undefined;
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setDrawerOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [drawerOpen]);

  function submitSearch(event) {
    event.preventDefault();
    workspace.handleSearch();
  }

  return (
    <>
      <div className="analysis-layout">
        <aside className="analysis-rail filter-rail">
          <div className="rail-heading">
            <div>
              <p>Visualization</p>
              <h2>视图控制</h2>
            </div>
            <SlidersHorizontal size={18} />
          </div>

          <section className="control-section">
            <h3><Layers3 size={15} />嵌入视图</h3>
            <Field label="着色字段">
              <select value={workspace.visualColorBy} onChange={(event) => workspace.setVisualColorBy(event.target.value)}>
                {workspace.visualColorBy.startsWith("gene:") ? (
                  <option value={workspace.visualColorBy}>{colorByLabel(workspace.visualColorBy)}</option>
                ) : null}
                <option value="dataset">数据集</option>
                {METADATA_FIELDS.map((fieldName) => (
                  <option key={fieldName} value={fieldName}>{COLOR_FIELD_LABELS[fieldName]}</option>
                ))}
              </select>
            </Field>
            <div className="inline-fields">
              <Field label="抽样点数">
                <input
                  type="number"
                  min="100"
                  max="5000"
                  step="100"
                  value={workspace.visualLimit}
                  onChange={(event) => workspace.setVisualLimit(event.target.value)}
                  onBlur={workspace.normalizeVisualLimit}
                />
              </Field>
              <Field label="抽样方式">
                <select value={workspace.visualSampleStrategy} onChange={(event) => workspace.setVisualSampleStrategy(event.target.value)}>
                  <option value="even">均匀</option>
                  <option value="random">随机</option>
                </select>
              </Field>
            </div>
          </section>

          <section className="control-section">
            <h3><Filter size={15} />元数据过滤</h3>
            {METADATA_FIELDS.map((fieldName) => (
              <Field key={fieldName} label={COLOR_FIELD_LABELS[fieldName]}>
                <select
                  value={workspace.visualFilters[fieldName] || ""}
                  onChange={(event) => workspace.setVisualFilters({ ...workspace.visualFilters, [fieldName]: event.target.value })}
                >
                  <option value="">全部</option>
                  {(workspace.visOptions?.categorical_fields?.[fieldName] || []).slice(0, 80).map((item) => (
                    <option key={item.value} value={item.value}>{item.value} ({item.count})</option>
                  ))}
                </select>
              </Field>
            ))}
          </section>

          <section className="control-section">
            <h3><FlaskConical size={15} />基因表达</h3>
            <Field label="基因名或 Ensembl ID">
              <input value={workspace.visualGeneQuery} onChange={(event) => workspace.setVisualGeneQuery(event.target.value)} />
            </Field>
            <button className="secondary-button full-button" onClick={workspace.handleApplyGeneColor} disabled={Boolean(workspace.busy) || workspace.visualLoading || !workspace.selectedDatasetIds.length}>
              <FlaskConical size={16} />
              应用表达量着色
            </button>
          </section>

          <div className="rail-actions">
            <div className={`view-sync-row ${workspace.visualDirty ? "pending" : "synced"}`}>
              <span>{workspace.visualDirty ? "有未应用更改" : "视图已同步"}</span>
              <small>{workspace.visualDirty ? "点击下方按钮更新画布" : "画布与筛选设置一致"}</small>
            </div>
            <button className="primary-button full-button" onClick={() => workspace.handleRefreshVisualization()} disabled={Boolean(workspace.busy) || workspace.visualLoading || !workspace.selectedDatasetIds.length}>
              {workspace.visualLoading ? <LoaderCircle size={16} className="spin" /> : <RefreshCw size={16} />}
              应用视图设置
            </button>
            <div className="rail-action-grid">
              <button className="text-button" onClick={workspace.handleClearVisualFilters} disabled={workspace.visualLoading}>
                <Eraser size={15} />清除过滤
              </button>
              <button className="text-button" onClick={workspace.exportVisualizationCsv} disabled={!workspace.visPoints.length}>
                <Download size={15} />导出 CSV
              </button>
            </div>
          </div>
        </aside>

        <section className="embedding-workspace">
          <header className="embedding-header">
            <div>
              <p>Embedding / UMAP</p>
              <h2>{selectedDatasetText}</h2>
            </div>
            <div className="embedding-summary">
              <span><b>{formatNumber(workspace.visualStats?.visible_cells)}</b> 可见细胞</span>
              <span><b>{formatNumber(workspace.visualStats?.sampled_points)}</b> 当前采样</span>
              <StatusBadge value={colorByLabel(appliedColorBy)} tone="teal" />
              <IconButton label="刷新 UMAP" onClick={() => workspace.handleRefreshVisualization()} disabled={Boolean(workspace.busy) || workspace.visualLoading}>
                <RefreshCw size={16} className={workspace.visualLoading ? "spin" : ""} />
              </IconButton>
            </div>
          </header>
          <div className="embedding-canvas">
            <UmapChart
              points={workspace.visPoints}
              queryCell={workspace.searchResult?.query_cell}
              hits={workspace.searchResult?.hits || []}
              colorBy={appliedColorBy}
              stats={workspace.visualStats}
              filters={workspace.appliedVisualState.filters}
              onPickCell={workspace.handlePickVisualizationCell}
              emptyMessage={workspace.visualLoading ? "正在更新 UMAP 数据" : "当前筛选条件下没有可见细胞"}
            />
            <div className="embedding-axis x-axis">UMAP 1</div>
            <div className="embedding-axis y-axis">UMAP 2</div>
            <div className="plot-key">
              <span><i className="query-key" /> 查询细胞</span>
              <span><i className="hit-key" /> Top-K 邻域{hasHits ? ` ${visibleOverlayHitCount}/${totalHitCount}` : ""}</span>
            </div>
            {workspace.visualLoading ? (
              <div className="plot-refresh-overlay" aria-live="polite">
                <span><LoaderCircle size={14} className="spin" />正在更新视图</span>
              </div>
            ) : null}
          </div>
        </section>

        <aside className="analysis-rail inspector-rail">
          <div className="rail-heading">
            <div>
              <p>ANN Inspector</p>
              <h2>邻域检索</h2>
            </div>
            <Search size={18} />
          </div>

          {!workspace.canSearch ? <AccessNotice>{guestMode ? "当前处于只读浏览模式。登录后可执行 ANN 邻域检索。" : "当前角色没有执行检索的权限。"}</AccessNotice> : null}

          <form className="inspector-form" onSubmit={submitSearch}>
            <Field label="查询数据集">
              <select value={workspace.queryDatasetId} onChange={(event) => workspace.setQueryDatasetId(event.target.value)}>
                <option value="">自动匹配</option>
                {workspace.selectedDatasets.map((dataset) => (
                  <option key={dataset.dataset_id} value={dataset.dataset_id}>{dataset.name}</option>
                ))}
              </select>
            </Field>
            <Field label="细胞 ID">
              <input value={workspace.queryCellId} onChange={(event) => workspace.setQueryCellId(event.target.value)} placeholder="选择图中细胞或输入 ID" />
            </Field>
            <Field label="Top-K">
              <input type="number" min="1" max="100" value={workspace.topK} onChange={(event) => workspace.setTopK(event.target.value)} onBlur={workspace.normalizeTopK} />
            </Field>
            <button className="primary-button full-button" type="submit" disabled={queryDisabled}>
              {workspace.busy === "search" ? <LoaderCircle size={17} className="spin" /> : <Play size={17} />}
              执行检索
            </button>
          </form>

          <section className={`metric-row ${hasHits ? "has-results" : ""}`} key={workspace.searchResult?.query_time_ms ?? "empty"}>
            <div><span>查询耗时</span><strong>{workspace.searchResult ? `${workspace.searchResult.query_time_ms} ms` : "-"}</strong></div>
            <div><span>命中结果</span><strong>{workspace.searchResult?.result_count ?? "-"}</strong></div>
          </section>

          <section className="inspector-section result-preview">
            <div className="section-title-row">
              <h3><BarChart3 size={15} />Top-K 结果</h3>
              <button className="link-button" onClick={() => setDrawerOpen(true)} disabled={!hasHits}>
                <Maximize2 size={14} />完整表格
              </button>
            </div>
            <ResultsTable hits={workspace.searchResult?.hits} compact />
            {hasHits && visibleOverlayHitCount < totalHitCount ? (
              <p className="filtered-overlay-note">当前过滤视图显示 {visibleOverlayHitCount} / {totalHitCount} 个命中点</p>
            ) : null}
          </section>

          <section className="inspector-section">
            <h3>{colorByLabel(appliedColorBy)}</h3>
            {workspace.visualStats?.expression ? (
              <div className="expression-summary">
                <span>表达细胞 {(workspace.visualStats.expression.expressing_fraction * 100).toFixed(1)}%</span>
                <span>均值 {workspace.visualStats.expression.mean.toFixed(3)}</span>
                <span>范围 {workspace.visualStats.expression.min.toFixed(2)} - {workspace.visualStats.expression.max.toFixed(2)}</span>
              </div>
            ) : null}
            <LegendRows items={legendItems} />
          </section>

          <section className="inspector-section">
            <h3>Top-K 细胞组成</h3>
            <LegendRows items={workspace.topKTypeStats} limit={8} />
            {workspace.topKDistanceStats ? (
              <div className="distance-summary">
                <span>最小距离 <b>{workspace.topKDistanceStats.min.toFixed(4)}</b></span>
                <span>平均距离 <b>{workspace.topKDistanceStats.mean.toFixed(4)}</b></span>
                <span>最大距离 <b>{workspace.topKDistanceStats.max.toFixed(4)}</b></span>
              </div>
            ) : null}
          </section>
        </aside>
      </div>

      {drawerOpen ? (
        <div className="drawer-layer">
          <button className="drawer-backdrop" aria-label="关闭结果抽屉" onClick={() => setDrawerOpen(false)} />
          <aside className="result-drawer">
            <header>
              <div>
                <p>ANN neighborhood</p>
                <h2>Top-K 检索结果</h2>
                <span>查询细胞：{workspace.searchResult?.query_cell?.cell_id || workspace.queryCellId}</span>
              </div>
              <IconButton label="关闭抽屉" onClick={() => setDrawerOpen(false)}><X size={18} /></IconButton>
            </header>
            <ResultsTable hits={workspace.searchResult?.hits} />
          </aside>
        </div>
      ) : null}
    </>
  );
}
