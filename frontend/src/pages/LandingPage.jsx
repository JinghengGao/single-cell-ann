import {
  Activity,
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  Database,
  Dna,
  Eye,
  Filter,
  FlaskConical,
  Gauge,
  GitBranch,
  Layers3,
  Search,
  ShieldCheck,
} from "lucide-react";

import { LoginParticleOverlay } from "../components/LoginParticleOverlay";
import { UmapChart } from "../components/UmapChart";
import { formatNumber } from "../constants";

const CAPABILITIES = [
  {
    icon: Layers3,
    index: "01",
    title: "真实嵌入空间",
    description: "直接浏览公开单细胞数据集的 UMAP 分布，在组织、疾病和年龄组之间快速收窄观察范围。",
  },
  {
    icon: Search,
    index: "02",
    title: "ANN 邻域检索",
    description: "基于 FAISS 向量索引定位 Top-K 相似细胞，将查询细胞、邻域点与距离关系同步回投到画布。",
  },
  {
    icon: FlaskConical,
    index: "03",
    title: "表达与元数据联动",
    description: "按细胞类型或元数据字段着色，并用基因表达量重新解释当前嵌入空间中的细胞群落。",
  },
];

const WORKFLOW = [
  { icon: Database, title: "接入数据", description: "扫描、校验并选择可用的单细胞数据集。" },
  { icon: GitBranch, title: "构建索引", description: "使用 IVF_FLAT 参数管理活动检索索引。" },
  { icon: Filter, title: "探索邻域", description: "筛选 UMAP、点选细胞并检查 Top-K 结果。" },
];

export function LandingPage({ workspace, onLogin, onBrowse }) {
  const dataset = workspace.datasets[0];
  const activeIndex = workspace.activeIndex;
  const faissMode = workspace.health?.faiss?.mode || workspace.indexStatus?.mode || "unavailable";
  const serviceReady = !workspace.connectionError && !workspace.initializing;

  return (
    <main className="landing-page">
      <section className="landing-hero" id="top">
        <div className="landing-grid" />
        <UmapChart
          points={workspace.visPoints}
          stats={workspace.visualStats}
          colorBy={workspace.appliedVisualState.colorBy}
          variant="backdrop"
          emptyMessage="等待公开 UMAP 数据"
        />
        <div className="landing-shade" />
        <LoginParticleOverlay />

        <header className="landing-header">
          <a
            className="landing-brand"
            href="#top"
            aria-label="CellScope ANN 首页"
            onClick={(event) => {
              event.preventDefault();
              document.querySelector(".landing-page")?.scrollTo({ top: 0 });
            }}
          >
            <span className="landing-brand-mark"><Dna size={23} /></span>
            <span><strong>CellScope</strong><b>ANN</b></span>
          </a>
          <nav className="landing-nav" aria-label="宣传页导航">
            <a href="#platform">平台能力</a>
            <a href="#workflow">分析流程</a>
            <a href="#access">开始使用</a>
          </nav>
          <div className="landing-header-actions">
            <button className="landing-ghost-button" type="button" onClick={onBrowse}>
              <Eye size={16} />只读浏览
            </button>
            <button className="landing-solid-button" type="button" onClick={onLogin}>
              登录平台<ArrowUpRight size={16} />
            </button>
          </div>
        </header>

        <div className="landing-hero-copy">
          <p>Single-cell neighborhood intelligence</p>
          <h1>CellScope ANN</h1>
          <h2>从单细胞嵌入空间，<br />抵达可解释的相似邻域。</h2>
          <span>面向科研分析场景的单细胞向量检索平台。以真实 UMAP 数据云为入口，连接数据集、FAISS 索引、元数据筛选与基因表达着色。</span>
          <div className="landing-hero-actions">
            <button className="landing-solid-button prominent" type="button" onClick={onLogin}>
              进入分析平台<ArrowRight size={18} />
            </button>
            <button className="landing-inline-button" type="button" onClick={onBrowse}>
              <Eye size={17} />查看公开数据
            </button>
          </div>
        </div>

        <div className="landing-proof">
          <div>
            <Database size={18} />
            <span>公开数据集</span>
            <strong>{dataset?.name || "等待连接"}</strong>
          </div>
          <div>
            <Activity size={18} />
            <span>可探索细胞</span>
            <strong>{formatNumber(dataset?.cell_count)}</strong>
          </div>
          <div>
            <GitBranch size={18} />
            <span>活动索引</span>
            <strong>{activeIndex?.index_type || "-"}</strong>
          </div>
          <div>
            <Gauge size={18} />
            <span>计算模式</span>
            <strong>{faissMode.toUpperCase()}</strong>
          </div>
        </div>

        <a className="landing-scroll-cue" href="#platform">
          <ArrowDown size={15} />
          <span>继续了解平台</span>
        </a>
      </section>

      <section className="landing-intro" id="platform">
        <div className="landing-section-inner landing-intro-grid">
          <div className="landing-section-heading">
            <p>Research workspace</p>
            <h2>让检索、筛选与解释<br />保持在同一张图上。</h2>
          </div>
          <div className="landing-intro-copy">
            <p>CellScope ANN 将单细胞数据分析中常见的向量检索工作流收拢为一个桌面科研工作台。研究者可以从群落分布出发，逐步定位目标细胞，并直接核查其近邻组成。</p>
            <div className="landing-service-line">
              <i className={serviceReady ? "ready" : "waiting"} />
              <span>{workspace.connectionError ? "当前演示服务暂不可用" : workspace.initializing ? "正在连接演示服务" : "公开演示服务已连接"}</span>
            </div>
          </div>
        </div>
      </section>

      <section className="landing-capabilities">
        <div className="landing-section-inner">
          <header className="landing-band-heading">
            <p>Platform capabilities</p>
            <h2>围绕真实数据的分析能力</h2>
          </header>
          <div className="landing-capability-grid">
            {CAPABILITIES.map((item) => {
              const Icon = item.icon;
              return (
                <article className="landing-capability" key={item.index}>
                  <div className="landing-capability-top">
                    <span>{item.index}</span>
                    <Icon size={20} />
                  </div>
                  <h3>{item.title}</h3>
                  <p>{item.description}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section className="landing-workflow" id="workflow">
        <div className="landing-section-inner landing-workflow-grid">
          <div className="landing-section-heading">
            <p>Analysis workflow</p>
            <h2>三步进入<br />细胞邻域分析。</h2>
            <span>平台保留清晰的任务边界，让演示过程从数据准备自然过渡到检索结果。</span>
          </div>
          <div className="landing-workflow-list">
            {WORKFLOW.map((item, index) => {
              const Icon = item.icon;
              return (
                <div className="landing-workflow-step" key={item.title}>
                  <b>0{index + 1}</b>
                  <span className="landing-step-icon"><Icon size={19} /></span>
                  <div>
                    <h3>{item.title}</h3>
                    <p>{item.description}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section className="landing-access" id="access">
        <div className="landing-section-inner landing-access-grid">
          <div>
            <p>Start exploring</p>
            <h2>进入 CellScope ANN<br />开始一次可解释的细胞检索。</h2>
          </div>
          <div className="landing-access-actions">
            <button className="landing-solid-button prominent" type="button" onClick={onLogin}>
              登录或注册<ArrowRight size={18} />
            </button>
            <button className="landing-outline-button" type="button" onClick={onBrowse}>
              <ShieldCheck size={17} />以访客身份浏览
            </button>
          </div>
        </div>
      </section>

      <footer className="landing-footer">
        <div className="landing-section-inner">
          <span>CellScope ANN</span>
          <span>Single-cell neighborhood analysis workspace</span>
        </div>
      </footer>
    </main>
  );
}
