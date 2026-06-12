import { Boxes, Cpu, Database, GitBranch, Layers3, LoaderCircle, Play, ServerCog } from "lucide-react";

import { formatNumber, statusTone } from "../constants";
import { AccessNotice, EmptyState, Field, StatusBadge } from "../components/ui";

function IndexStat({ icon, label, value }) {
  return (
    <div className="index-stat">
      {icon}
      <span>{label}</span>
      <strong>{value ?? "-"}</strong>
    </div>
  );
}

export function IndexPage({ workspace, guestMode }) {
  const activeIndex = workspace.activeIndex || {};
  const buildDisabled = Boolean(workspace.busy) || !workspace.canBuildIndex || !workspace.selectedDatasetIds.length;
  const faissMode = activeIndex.ready ? activeIndex.mode : workspace.health?.faiss?.mode || activeIndex.mode || "-";

  return (
    <div className="index-page">
      <section className="active-index-band">
        <div className="active-index-title">
          <span className="section-icon"><GitBranch size={20} /></span>
          <div className="active-index-copy">
            <p>当前索引：Active vector index</p>
            <h2>{activeIndex.index_id || "尚未构建服务索引"}</h2>
            <span>当前查询服务使用的 FAISS IVF_FLAT 索引状态。</span>
          </div>
          <StatusBadge value={activeIndex.status || "not_built"} tone={statusTone(activeIndex.status)} />
        </div>
        <div className="index-stat-strip">
          <IndexStat icon={<Boxes size={17} />} label="向量数" value={formatNumber(activeIndex.vector_count)} />
          <IndexStat icon={<Layers3 size={17} />} label="向量维度" value={activeIndex.dimension || "-"} />
          <IndexStat icon={<Database size={17} />} label="数据集" value={activeIndex.dataset_count ?? "-"} />
          <IndexStat icon={<Cpu size={17} />} label="FAISS" value={faissMode.toUpperCase()} />
        </div>
      </section>

      {!workspace.canBuildIndex ? (
        <AccessNotice>{guestMode ? "只读浏览模式下可查看索引状态。登录后可构建和切换服务索引。" : "当前角色没有构建或切换索引的权限。"}</AccessNotice>
      ) : null}

      <div className="index-grid">
        <section className="index-config-panel">
          <header className="page-section-header compact">
            <div>
              <p>构建参数：Build configuration</p>
              <h2>构建新索引</h2>
              <span>基于当前选中的数据集生成服务索引。</span>
            </div>
          </header>
          <div className="selected-dataset-box">
            <span>已选择数据集</span>
            <strong>{workspace.selectedDatasets.map((dataset) => dataset.name).join(", ") || "未选择数据集"}</strong>
          </div>
          <div className="index-form-grid">
            <Field label="构建模式">
              <select value={workspace.indexMode} onChange={(event) => workspace.setIndexMode(event.target.value)} disabled={!workspace.canBuildIndex}>
                <option value="combined">联合索引</option>
                <option value="separate">独立索引</option>
              </select>
            </Field>
            <Field label="nlist" hint="范围 1 - 65536">
              <input type="number" min="1" max="65536" value={workspace.nlist} onChange={(event) => workspace.setNlist(event.target.value)} onBlur={workspace.normalizeIndexParameters} disabled={!workspace.canBuildIndex} />
            </Field>
            <Field label="nprobe" hint="范围 1 - nlist">
              <input type="number" min="1" max="65536" value={workspace.nprobe} onChange={(event) => workspace.setNprobe(event.target.value)} onBlur={workspace.normalizeIndexParameters} disabled={!workspace.canBuildIndex} />
            </Field>
          </div>
          <button className="primary-button full-button" onClick={workspace.handleBuildIndex} disabled={buildDisabled}>
            {workspace.busy === "index" ? <LoaderCircle size={17} className="spin" /> : <Play size={17} />}
            构建索引
          </button>
        </section>

        <section className="index-list-panel">
          <header className="page-section-header compact">
            <div>
              <p>索引列表：Index inventory</p>
              <h2>可用索引</h2>
              <span>检查历史索引并切换当前服务版本。</span>
            </div>
          </header>
          {workspace.indexOptions.length ? (
            <div className="index-list">
              {workspace.indexOptions.map((item) => (
                <article className={`index-list-row ${item.index_id === activeIndex.index_id ? "active" : ""}`} key={item.index_id}>
                  <span className="index-list-icon"><ServerCog size={18} /></span>
                  <div className="index-list-copy">
                    <strong>{item.index_id}</strong>
                    <span>{(item.dataset_ids || []).join(", ") || "-"} · {item.build_mode || "-"}</span>
                  </div>
                  <div className="index-list-meta">
                    <StatusBadge value={item.status} />
                    <span>{formatNumber(item.vector_count)} vectors</span>
                  </div>
                  <button
                    className="secondary-button small-button"
                    onClick={() => workspace.handleSwitchIndex(item.index_id)}
                    disabled={Boolean(workspace.busy) || !workspace.canSwitchIndex || item.index_id === activeIndex.index_id}
                  >
                    {item.index_id === activeIndex.index_id ? "当前服务" : "切换"}
                  </button>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="暂无可用索引" description="选择数据集并构建索引后，服务版本将显示在此处。" />
          )}
        </section>
      </div>
    </div>
  );
}
