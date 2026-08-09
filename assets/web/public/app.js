const state = {
  dashboard: null,
  section: "home",
  draft: null
};

const platformName = {
  xiaohongshu: "小红书",
  douyin: "抖音",
  "wechat-mp": "公众号",
  "wechat-channels": "视频号"
};

const $ = (id) => document.getElementById(id);

function toast(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.add("show");
  window.clearTimeout(node._timer);
  node._timer = window.setTimeout(() => node.classList.remove("show"), 3600);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    method: options.method || "GET",
    headers: options.body ? { "Content-Type": "application/json" } : {},
    body: options.body ? JSON.stringify(options.body) : undefined
  });
  const text = await response.text();
  let payload = null;
  try {
    payload = JSON.parse(text);
  } catch {
    payload = { text };
  }
  if (!response.ok) {
    throw new Error(payload.error || payload.stderr || text || `HTTP ${response.status}`);
  }
  return payload;
}

function todayLabel() {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "short"
  }).format(new Date());
}

function firstReason(item) {
  if (!item) return "暂无选题评分";
  if (Array.isArray(item.reasons) && item.reasons.length) return item.reasons.slice(0, 2).join(" · ");
  return "基于本地信号和策略规则生成评分";
}

function renderRecommendation(data) {
  const item = data.recommendation;
  $("recommendationTitle").textContent = item?.topic || "暂无推荐选题";
  $("recommendationPlatform").textContent = item ? platformName[item.platform] || item.platform : "需要配置账号";
  $("recommendationReason").textContent = item ? firstReason(item) : "运行今日计划后生成推荐";
  $("recommendationScore").textContent = item?.score ?? "--";
}

function renderEvidence(items) {
  const list = $("evidenceList");
  list.innerHTML = "";
  if (!items.length) {
    list.innerHTML = '<div class="empty">暂无证据。运行今日计划后会采集并评分。</div>';
    return;
  }

  for (const item of items) {
    const row = document.createElement("div");
    row.className = "evidence-row";
    row.innerHTML = `
      <div class="evidence-source">${item.source}</div>
      <div>
        <div class="evidence-title">${escapeHtml(item.signal || "Untitled signal")}</div>
        <div class="evidence-meta">${escapeHtml(item.why || "已记录证据")} · 证据等级 ${escapeHtml(item.evidenceLevel || "未知")}</div>
      </div>
      <div class="evidence-score">${Number(item.score || 0)}</div>
    `;
    list.appendChild(row);
  }
}

function renderStatus(items) {
  const list = $("statusList");
  list.innerHTML = "";
  if (!items.length) {
    list.innerHTML = '<div class="empty">暂无平台配置。</div>';
    return;
  }

  for (const item of items) {
    const level = item.evidenceLevel || "待采集";
    const row = document.createElement("div");
    row.className = "status-item";
    row.innerHTML = `
      <div>
        <div class="status-title">${escapeHtml(item.label)}</div>
        <div class="status-meta">${escapeHtml(item.accountName || "未命名账号")} · ${item.status === "ready" ? "信号已就绪" : "等待采集数据"}</div>
      </div>
      <div class="evidence-pill ${level === "A" ? "" : "warn"}">${escapeHtml(level)}</div>
    `;
    list.appendChild(row);
  }
}

function renderShell(data) {
  $("todayDate").textContent = todayLabel();
  $("workspaceName").textContent = data.config?.owner ? `${data.config.owner} 工作区` : data.config?.workspace_id || "工作区";
  $("workspaceMeta").textContent = data.config?.workspace_id || "本地优先";
  $("workspaceSwitch").innerHTML = `${escapeHtml(data.config?.workspace_id || "创作者工作区")} <span>⌄</span>`;
  const run = data.latestRun?.created_at ? `已更新 ${data.latestRun.created_at.replace("T", " ")}` : "自动任务已就绪";
  $("runStateText").textContent = run;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function loadDashboard() {
  const data = await api("/api/dashboard");
  state.dashboard = data;
  renderShell(data);
  renderRecommendation(data);
  renderEvidence(data.evidence || []);
  renderStatus(data.platformStatus || []);
  renderCurrentSection();
}

async function runDaily() {
  toast("正在运行今日计划，本次使用本地缓存数据...");
  const result = await api("/api/daily-run", { method: "POST", body: { noNetwork: true } });
  toast(result.ok ? "今日计划已更新。" : "今日计划运行失败。");
  await loadDashboard();
}

async function refreshScores() {
  toast("正在刷新选题评分...");
  const result = await api("/api/score-topics", { method: "POST", body: {} });
  toast(result.ok ? "选题评分已刷新。" : "选题评分刷新失败。");
  await loadDashboard();
}

async function precheckSample() {
  const item = state.dashboard?.recommendation;
  if (!item) {
    toast("当前还没有可检查的推荐选题。");
    return;
  }
  const result = await api("/api/prepublish", {
    method: "POST",
    body: {
      platform: item.platform,
      title: item.topic,
      content: `围绕「${item.topic}」生成一条内容草稿，并保留证据来源。`
    }
  });
  toast(`发布检查：${result.verdict}`);
}

async function createDraft() {
  const item = state.dashboard?.recommendation;
  if (!item) {
    toast("请先运行今日计划。");
    return;
  }
  toast("正在生成草稿简报...");
  const result = await api("/api/draft", {
    method: "POST",
    body: {
      platform: item.platform,
      topic: item.topic
    }
  });
  state.draft = result.draft;
  renderDraft(result.draft);
  if (state.section === "opportunities") renderCurrentSection();
  toast("草稿简报已生成。");
}

function renderDraft(draft) {
  $("draftPreview").hidden = false;
  $("draftTitle").textContent = `${draft.platformLabel} · ${draft.title}`;
  $("draftOpening").textContent = draft.opening;
  $("draftStructure").innerHTML = "";
  $("draftChecklist").innerHTML = "";
  for (const item of draft.structure || []) {
    const li = document.createElement("li");
    li.textContent = item;
    $("draftStructure").appendChild(li);
  }
  for (const item of draft.checklist || []) {
    const li = document.createElement("li");
    li.textContent = item;
    $("draftChecklist").appendChild(li);
  }
}

function reviewEvidence() {
  const count = state.dashboard?.evidence?.length || 0;
  goSection("opportunities");
  toast(`已载入 ${count} 条证据信号。`);
}

function runCommand() {
  const value = $("commandInput").value.trim();
  if (!value) {
    toast("请先输入选题或指令。");
    return;
  }
  toast("已收到指令。完整生成链路将在下一版接入。");
}

const pages = {
  account: {
    eyebrow: "Account Center",
    title: "账号中心",
    description: "确认我是谁、卖什么、做什么平台，以及每个平台的定位和对标账号。"
  },
  opportunities: {
    eyebrow: "Content Opportunity",
    title: "内容机会",
    description: "把今日推荐、证据信号、评分理由和下一步草稿动作放在同一个页面。"
  },
  library: {
    eyebrow: "Content Library",
    title: "内容库",
    description: "沉淀已发布内容、正文脚本、发布时间、数据、转化和下次改法。"
  },
  review: {
    eyebrow: "Growth Review",
    title: "复盘中心",
    description: "查看待复盘内容、已生效策略、待确认策略，以及 Agent 自成长记录。"
  }
};

function goSection(section) {
  state.section = section;
  for (const item of document.querySelectorAll(".nav-item")) {
    item.classList.toggle("active", item.dataset.section === section);
  }
  $("homeView").hidden = section !== "home";
  $("pageView").hidden = section === "home";
  renderCurrentSection();
}

function renderCurrentSection() {
  if (!state.dashboard || state.section === "home") return;
  const page = pages[state.section];
  $("pageEyebrow").textContent = page.eyebrow;
  $("pageTitle").textContent = page.title;
  $("pageDescription").textContent = page.description;
  $("pageContent").innerHTML = renderPageContent(state.section, state.dashboard);
}

function renderPageContent(section, data) {
  if (section === "account") return renderAccountPage(data);
  if (section === "opportunities") return renderOpportunitiesPage(data);
  if (section === "library") return renderLibraryPage(data);
  if (section === "review") return renderReviewPage(data);
  return "";
}

function renderAccountPage(data) {
  const platforms = data.config?.platforms || [];
  const owner = data.config?.owner || "待补充";
  const productKeywords = data.config?.product_keywords || [];
  return `
    <div class="detail-grid">
      <div class="detail-block">
        <div class="muted-label">我是谁</div>
        <h2>${escapeHtml(owner)}</h2>
        <p>工作区：${escapeHtml(data.config?.workspace_id || "未配置")}</p>
        <p>核心产品：${escapeHtml(productKeywords.join("、") || "待补充")}</p>
      </div>
      <div class="detail-block">
        <div class="muted-label">下一步</div>
        <h2>首用配置建议用 quickstart</h2>
        <p>命令：python scripts\\creatorbuddy.py quickstart</p>
      </div>
    </div>
    <div class="data-table account-table">
      <div class="table-row table-head"><span>平台</span><span>账号 / 定位</span><span>目标用户</span><span>对标</span></div>
      ${platforms
        .map((item) => {
          const benchmarks = item.benchmark_accounts || [];
          const positioning = item.positioning ? ` · ${item.positioning}` : "";
          return `
            <div class="table-row">
              <span>${escapeHtml(platformName[item.platform] || item.platform)}</span>
              <span>${escapeHtml((item.account_name || "未连接") + positioning)}</span>
              <span>${escapeHtml(item.target_audience || "待补充")}</span>
              <span>${escapeHtml(benchmarks.length ? `${benchmarks.length} 个` : "待添加")}</span>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderOpportunitiesPage(data) {
  const rows = (data.topScores || []).slice(0, 12);
  const recommendation = data.recommendation;
  const top = recommendation
    ? `
      <div class="detail-block opportunity-lead">
        <div class="muted-label">今日推荐</div>
        <h2>${escapeHtml(recommendation.topic || "")}</h2>
        <p>${escapeHtml(firstReason(recommendation))}</p>
        <div class="page-actions">
          <button class="primary-button" onclick="window.creatorBuddyCreateDraft()">生成草稿</button>
          <button class="secondary-button" onclick="window.creatorBuddyPrecheck()">发布检查</button>
        </div>
      </div>
    `
    : "";
  if (!rows.length) return emptyPage("暂无内容机会。请先运行今日计划。");
  return `
    ${top}
    <div class="data-table">
      <div class="table-row table-head"><span>平台</span><span>选题/信号</span><span>评分</span><span>证据</span></div>
      ${rows
        .map(
          (row) => `
            <div class="table-row">
              <span>${escapeHtml(platformName[row.platform] || row.platform)}</span>
              <span>${escapeHtml(row.topic)}</span>
              <strong>${Number(row.score || 0)}</strong>
              <span>${escapeHtml(row.evidence_level || "未知")}</span>
            </div>
          `
        )
        .join("")}
    </div>
  `;
}

function renderLibraryPage(data) {
  const rows = data.published || [];
  if (!rows.length) return emptyPage("暂无已发布内容记录。后续可以从这里沉淀标题、平台、指标和复盘状态。");
  return `
    <div class="data-table">
      <div class="table-row table-head"><span>平台</span><span>标题</span><span>发布时间</span><span>复盘状态</span></div>
      ${rows
        .map(
          (row) => `
            <div class="table-row">
              <span>${escapeHtml(platformName[row.platform] || row.platform)}</span>
              <span>${escapeHtml(row.title || "")}</span>
              <span>${escapeHtml(row.published_at || "待补充")}</span>
              <span>${escapeHtml(row.review_status || "待复盘")}</span>
            </div>
          `
        )
        .join("")}
    </div>
  `;
}

function renderReviewPage(data) {
  const run = data.latestRun;
  const active = data.activeRules || [];
  const pending = data.pendingStrategies || [];
  const pendingReviews = data.published || [];
  return `
    <div class="detail-grid">
      <div class="detail-block">
        <div class="muted-label">最近运行</div>
        <h2>${escapeHtml(run?.created_at || "暂无运行记录")}</h2>
        <p>${escapeHtml(run?.score_report || "运行今日计划后会生成选题评分报告。")}</p>
      </div>
      <div class="detail-block">
        <div class="muted-label">复盘提醒</div>
        <h2>21:00</h2>
        <p>检查今日发布内容表现，沉淀有效经验和下一次改法。</p>
      </div>
      <div class="detail-block">
        <div class="muted-label">已生效策略</div>
        ${active.length ? active.map((rule) => `<p>${escapeHtml(rule.rule || "")}</p>`).join("") : "<p>暂无已生效策略。</p>"}
      </div>
      <div class="detail-block">
        <div class="muted-label">待确认策略</div>
        ${pending.length ? pending.map((rule) => `<p>${escapeHtml(rule.rule || "")}</p>`).join("") : "<p>暂无待确认策略。</p>"}
      </div>
    </div>
    ${
      pendingReviews.length
        ? `<div class="data-table">
            <div class="table-row table-head"><span>平台</span><span>内容</span><span>发布时间</span><span>复盘</span></div>
            ${pendingReviews
              .slice(0, 8)
              .map(
                (row) => `
                  <div class="table-row">
                    <span>${escapeHtml(platformName[row.platform] || row.platform)}</span>
                    <span>${escapeHtml(row.title || "")}</span>
                    <span>${escapeHtml(row.published_at || "待补充")}</span>
                    <span>${escapeHtml(row.review_status || row.status || "待复盘")}</span>
                  </div>
                `
              )
              .join("")}
          </div>`
        : ""
    }
  `;
}

function emptyPage(text) {
  return `<div class="empty-page">${escapeHtml(text)}</div>`;
}

function bindEvents() {
  $("runDailyButton").addEventListener("click", () => runDaily().catch((error) => toast(error.message)));
  $("scoreButton").addEventListener("click", () => refreshScores().catch((error) => toast(error.message)));
  $("precheckDemoButton").addEventListener("click", () => precheckSample().catch((error) => toast(error.message)));
  $("createDraftButton").addEventListener("click", () => createDraft().catch((error) => toast(error.message)));
  $("reviewEvidenceButton").addEventListener("click", reviewEvidence);
  $("commandButton").addEventListener("click", runCommand);
  $("commandInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") runCommand();
  });
  for (const item of document.querySelectorAll(".nav-item")) {
    item.addEventListener("click", () => goSection(item.dataset.section));
  }
}

window.creatorBuddyCreateDraft = () => createDraft().catch((error) => toast(error.message));
window.creatorBuddyPrecheck = () => precheckSample().catch((error) => toast(error.message));

bindEvents();
loadDashboard().catch((error) => toast(error.message));
