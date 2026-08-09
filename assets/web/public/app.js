const state = {
  dashboard: null,
  section: "home",
  draft: null,
  publisher: null,
  quickstartResult: null
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


function formValue(form, name) {
  return String(new FormData(form).get(name) || "").trim();
}

async function submitQuickstart(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button[type='submit']");
  const payload = {
    owner: formValue(form, "owner"),
    platform: formValue(form, "platform"),
    accountName: formValue(form, "accountName"),
    accountId: formValue(form, "accountId"),
    positioning: formValue(form, "positioning"),
    targetAudience: formValue(form, "targetAudience"),
    contentDirections: formValue(form, "contentDirections"),
    commercialGoal: formValue(form, "commercialGoal"),
    coreProduct: formValue(form, "coreProduct"),
    keywords: formValue(form, "keywords"),
    benchmarkName: formValue(form, "benchmarkName"),
    benchmarkUrl: formValue(form, "benchmarkUrl"),
    firstTitle: formValue(form, "firstTitle"),
    firstBody: formValue(form, "firstBody")
  };
  button.disabled = true;
  button.textContent = "正在初始化";
  try {
    toast("正在写入账号配置和第一条内容资产...");
    const result = await api("/api/quickstart", { method: "POST", body: payload });
    state.quickstartResult = result.quickstart;
    state.dashboard = result.dashboard || (await api("/api/dashboard"));
    renderShell(state.dashboard);
    renderRecommendation(state.dashboard);
    renderEvidence(state.dashboard.evidence || []);
    renderStatus(state.dashboard.platformStatus || []);
    renderCurrentSection();
    toast("初始化完成。下一步可以生成今日机会。");
  } finally {
    button.disabled = false;
    button.textContent = "完成初始化";
  }
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

async function createWechatPreview() {
  if (!state.draft) {
    toast("请先生成公众号草稿。");
    return;
  }
  if (state.draft.platform !== "wechat-mp") {
    toast("公众号预览只适用于公众号平台草稿。");
    return;
  }
  toast("正在生成公众号复制预览...");
  const result = await api("/api/wechat-publish", {
    method: "POST",
    body: {
      title: state.draft.title,
      content: state.draft.body,
      digest: state.draft.opening,
      layout: "component"
    }
  });
  state.publisher = result.publisher;
  renderWechatPublishResult(result.publisher, result.previewUrl);
  await loadDashboard();
  toast("公众号预览已生成，并已写入内容库。");
}

function renderWechatPublishResult(publisher, previewUrl = "") {
  const box = $("wechatPublishResult");
  if (!publisher) {
    box.hidden = true;
    box.innerHTML = "";
    return;
  }
  box.hidden = false;
  box.innerHTML = `
    <div class="publish-result-head">
      <div>
        <div class="muted-label">公众号预览</div>
        <strong>${escapeHtml(publisher.title || "已生成预览")}</strong>
      </div>
      ${previewUrl ? `<a class="secondary-button" href="${escapeAttr(previewUrl)}" target="_blank" rel="noreferrer">打开预览</a>` : ""}
    </div>
    <div class="publish-result-meta">
      <span>内容库：${escapeHtml(publisher.content_id || "已记录")}</span>
      <span>排版：${escapeHtml(publisher.layout || "component")}</span>
      <span>检查：${escapeHtml(publisher.precheck?.verdict || "待确认")}</span>
    </div>
    <code>${escapeHtml(publisher.preview_path || "")}</code>
  `;
}

function renderDraft(draft) {
  $("draftPreview").hidden = false;
  $("draftTitle").textContent = `${draft.platformLabel} · ${draft.title}`;
  $("draftOpening").textContent = draft.opening;
  $("wechatPreviewButton").hidden = draft.platform !== "wechat-mp";
  renderWechatPublishResult(null);
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
  const primaryPlatform = platforms.find((item) => item.account_name || item.positioning) || platforms[0] || {};
  const quickstartOutcome = renderQuickstartOutcome(state.quickstartResult);
  return `
    <form class="quickstart-form" id="quickstartForm">
      <div class="form-head">
        <div>
          <div class="muted-label">首次初始化</div>
          <h2>把你的账号交给 CreatorBuddy</h2>
        </div>
        <button class="primary-button" type="submit">完成初始化</button>
      </div>
      <div class="form-grid">
        <label>
          <span>你是谁</span>
          <input name="owner" value="${escapeAttr(data.config?.owner || "")}" placeholder="例如：Gelen / 张三 / 某某工作室" />
        </label>
        <label>
          <span>主平台</span>
          <select name="platform">
            ${renderPlatformOptions(primaryPlatform.platform || "xiaohongshu")}
          </select>
        </label>
        <label>
          <span>账号名称</span>
          <input name="accountName" value="${escapeAttr(primaryPlatform.account_name || "")}" placeholder="例如：Gelen AI成长" required />
        </label>
        <label>
          <span>账号 ID / 备注</span>
          <input name="accountId" value="${escapeAttr(primaryPlatform.account_id || "")}" placeholder="没有就填账号名" />
        </label>
        <label class="wide">
          <span>账号定位</span>
          <input name="positioning" value="${escapeAttr(primaryPlatform.positioning || "")}" placeholder="例如：帮助普通人快速学习 AI 并实现内容获客" required />
        </label>
        <label>
          <span>目标用户</span>
          <input name="targetAudience" value="${escapeAttr(primaryPlatform.target_audience || "")}" placeholder="例如：自媒体新手、知识付费创业者" required />
        </label>
        <label>
          <span>内容方向</span>
          <input name="contentDirections" value="${escapeAttr((primaryPlatform.content_directions || []).join("，"))}" placeholder="多个用逗号隔开" required />
        </label>
        <label>
          <span>商业目标</span>
          <input name="commercialGoal" value="${escapeAttr(primaryPlatform.commercial_goal || "")}" placeholder="例如：内容获客、私信咨询、课程成交" />
        </label>
        <label>
          <span>核心产品</span>
          <input name="coreProduct" value="${escapeAttr(primaryPlatform.core_product || "")}" placeholder="例如：AI训练营 / 咨询 / Skill" />
        </label>
        <label>
          <span>行业关键词</span>
          <input name="keywords" value="${escapeAttr((primaryPlatform.benchmark_industries || []).join("，"))}" placeholder="例如：AI工具教程、AI变现" />
        </label>
        <label>
          <span>对标账号</span>
          <input name="benchmarkName" value="${escapeAttr((primaryPlatform.benchmark_accounts || [])[0]?.account_name || "")}" placeholder="填一个你想参考的账号" />
        </label>
        <label class="wide">
          <span>对标主页链接</span>
          <input name="benchmarkUrl" value="${escapeAttr((primaryPlatform.benchmark_accounts || [])[0]?.url || "")}" placeholder="可选，后续用于对标采集" />
        </label>
        <label>
          <span>发过的一条内容</span>
          <input name="firstTitle" placeholder="标题，可选" />
        </label>
        <label>
          <span>正文 / 脚本</span>
          <input name="firstBody" placeholder="可选，先贴一小段也行" />
        </label>
      </div>
    </form>
    ${quickstartOutcome}
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

function renderQuickstartOutcome(result) {
  if (!result) return "";
  const opportunity = result.first_opportunity || {};
  return `
    <div class="quickstart-outcome">
      <div>
        <div class="muted-label">初始化已完成</div>
        <h2>${escapeHtml(opportunity.topic || "已生成首次内容机会")}</h2>
        <p>系统已写入账号配置，并生成首次机会报告和第一条草稿。</p>
      </div>
      <div class="outcome-links">
        ${result.first_report ? `<a class="secondary-button" href="${escapeAttr(toWorkspaceFileUrl(result.first_report))}" target="_blank" rel="noreferrer">打开首次报告</a>` : ""}
        ${result.first_draft_path ? `<a class="secondary-button" href="${escapeAttr(toWorkspaceFileUrl(result.first_draft_path))}" target="_blank" rel="noreferrer">打开第一条草稿</a>` : ""}
        <button class="primary-button" type="button" onclick="window.creatorBuddyCreateDraft()">继续生成草稿</button>
      </div>
    </div>
  `;
}

function toWorkspaceFileUrl(filePath) {
  const vault = state.dashboard?.vault || "";
  if (!filePath || !vault || !filePath.toLowerCase().startsWith(vault.toLowerCase())) return "";
  const relative = filePath.slice(vault.length).replace(/^[\\/]+/, "").replace(/\\/g, "/");
  return `/file/${encodeURIComponent(relative)}`;
}

function renderPlatformOptions(selected) {
  return Object.entries(platformName)
    .map(([value, label]) => `<option value="${escapeAttr(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(label)}</option>`)
    .join("");
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/'/g, "&#39;");
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
  $("precheckDemoButton").addEventListener("click", () => precheckSample().catch((error) => toast(error.message)));
  $("createDraftButton").addEventListener("click", () => createDraft().catch((error) => toast(error.message)));
  $("wechatPreviewButton").addEventListener("click", () => createWechatPreview().catch((error) => toast(error.message)));
  $("reviewEvidenceButton").addEventListener("click", reviewEvidence);
  $("commandButton").addEventListener("click", runCommand);
  $("commandInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") runCommand();
  });
  for (const item of document.querySelectorAll(".nav-item")) {
    item.addEventListener("click", () => goSection(item.dataset.section));
  }
  document.addEventListener("submit", (event) => {
    if (event.target?.id === "quickstartForm") {
      submitQuickstart(event).catch((error) => toast(error.message));
    }
  });
}

window.creatorBuddyCreateDraft = () => createDraft().catch((error) => toast(error.message));
window.creatorBuddyPrecheck = () => precheckSample().catch((error) => toast(error.message));
window.creatorBuddyWechatPreview = () => createWechatPreview().catch((error) => toast(error.message));

bindEvents();
loadDashboard().catch((error) => toast(error.message));
