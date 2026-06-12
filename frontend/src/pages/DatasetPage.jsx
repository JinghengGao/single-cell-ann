import { useEffect, useState } from "react";
import { Database, FileCheck2, LoaderCircle, Play, RefreshCw, Upload } from "lucide-react";

import { formatBytes, formatNumber } from "../constants";
import { AccessNotice, EmptyState, StatusBadge } from "../components/ui";

export function DatasetPage({ workspace, guestMode }) {
  const [focusDatasetId, setFocusDatasetId] = useState("");
  const focusDataset =
    workspace.datasets.find((dataset) => dataset.dataset_id === focusDatasetId) ||
    workspace.datasets.find((dataset) => dataset.dataset_id === workspace.selectedDatasetIds[0]) ||
    workspace.datasets[0];
  const manageDisabled = Boolean(workspace.busy) || !workspace.canManageDatasets;

  useEffect(() => {
    if (focusDataset) setFocusDatasetId(focusDataset.dataset_id);
  }, [focusDataset?.dataset_id]);

  return (
    <div className="registry-layout">
      <section className="registry-main">
        <header className="page-section-header">
          <div>
            <p>数据源：Dataset registry</p>
            <h2>数据源登记与准备</h2>
            <span>选择用于联合或独立索引构建的单细胞数据集。</span>
          </div>
          <div className="toolbar-actions">
            <button className="secondary-button" onClick={workspace.handleScanDatasets} disabled={manageDisabled}>
              {workspace.busy === "scan" ? <LoaderCircle size={16} className="spin" /> : <RefreshCw size={16} />}
              扫描本地
            </button>
            <button className="secondary-button" onClick={workspace.handleValidateDatasets} disabled={manageDisabled || !workspace.selectedDatasetIds.length}>
              {workspace.busy === "validate" ? <LoaderCircle size={16} className="spin" /> : <FileCheck2 size={16} />}
              校验选中
            </button>
            <button className="primary-button" onClick={workspace.handleLoadSelectedDataset} disabled={Boolean(workspace.busy) || !workspace.canLoadDataset || workspace.selectedDatasetIds.length !== 1}>
              {workspace.busy === "load" ? <LoaderCircle size={16} className="spin" /> : <Play size={16} />}
              加载数据集
            </button>
          </div>
        </header>

        {!workspace.canManageDatasets ? (
          <AccessNotice>{guestMode ? "只读浏览模式下可查看数据集状态。登录后可扫描、上传和校验数据。" : "当前角色可查看数据集，但不能扫描、上传或校验数据。"}</AccessNotice>
        ) : null}

        <div className="upload-bar">
          <div>
            <Upload size={18} />
            <span>{workspace.uploadFile?.name || "选择 .h5ad 文件上传到数据集库"}</span>
          </div>
          <label className={`file-select-button ${!workspace.canManageDatasets ? "disabled" : ""}`}>
            选择文件
            <input type="file" accept=".h5ad" onChange={(event) => workspace.setUploadFile(event.target.files?.[0] || null)} disabled={!workspace.canManageDatasets} />
          </label>
          <button className="primary-button" onClick={workspace.handleUploadDataset} disabled={manageDisabled || !workspace.uploadFile}>
            {workspace.busy === "upload" ? <LoaderCircle size={16} className="spin" /> : <Upload size={16} />}
            上传
          </button>
        </div>

        <div className="table-scroll registry-table">
          <table>
            <thead>
              <tr>
                <th className="checkbox-column">选择</th>
                <th>数据集</th>
                <th>状态</th>
                <th>细胞数</th>
                <th>向量维度</th>
                <th>Embedding</th>
                <th>来源</th>
              </tr>
            </thead>
            <tbody>
              {workspace.datasets.map((dataset) => (
                <tr
                  key={dataset.dataset_id}
                  className={focusDataset?.dataset_id === dataset.dataset_id ? "selected-row" : ""}
                  onClick={() => setFocusDatasetId(dataset.dataset_id)}
                >
                  <td>
                    <input
                      type="checkbox"
                      checked={workspace.selectedDatasetIds.includes(dataset.dataset_id)}
                      onClick={(event) => event.stopPropagation()}
                      onChange={() => workspace.toggleDataset(dataset.dataset_id)}
                    />
                  </td>
                  <td>
                    <strong>{dataset.name}</strong>
                    <span className="table-subtitle">{dataset.dataset_id}</span>
                  </td>
                  <td><StatusBadge value={dataset.status} /></td>
                  <td>{formatNumber(dataset.cell_count)}</td>
                  <td>{dataset.vector_dim || "-"}</td>
                  <td>{dataset.embedding_method || "-"}</td>
                  <td>{dataset.source || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!workspace.datasets.length ? <EmptyState title="尚未登记数据集" description="登录后扫描本地目录或上传 .h5ad 文件。" /> : null}
        </div>
      </section>

      <aside className="detail-panel">
        <div className="detail-panel-heading">
          <Database size={18} />
          <div>
            <p>数据集详情：Dataset details</p>
            <h2>{focusDataset?.name || "未选择数据集"}</h2>
          </div>
        </div>
        {focusDataset ? (
          <>
            <dl className="detail-list">
              <div><dt>数据集 ID</dt><dd>{focusDataset.dataset_id}</dd></div>
              <div><dt>当前状态</dt><dd><StatusBadge value={focusDataset.status} /></dd></div>
              <div><dt>文件大小</dt><dd>{formatBytes(focusDataset.file_size_bytes)}</dd></div>
              <div><dt>细胞数</dt><dd>{formatNumber(focusDataset.cell_count)}</dd></div>
              <div><dt>向量维度</dt><dd>{focusDataset.vector_dim || "-"}</dd></div>
              <div><dt>可视化方法</dt><dd>{focusDataset.visualization_method || "-"}</dd></div>
            </dl>
            <section className="detail-section">
              <h3>元数据字段</h3>
              <div className="tag-list">
                {(focusDataset.metadata_fields || []).map((field) => <span key={field}>{field}</span>)}
              </div>
            </section>
            <section className="detail-section">
              <h3>示例 Cell ID</h3>
              <div className="sample-list">
                {(focusDataset.sample_cell_ids || []).slice(0, 5).map((cellId) => <span key={cellId}>{cellId}</span>)}
              </div>
            </section>
          </>
        ) : (
          <EmptyState title="暂无数据" description="工作区尚未读取到可用数据集。" />
        )}
      </aside>
    </div>
  );
}
