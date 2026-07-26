const http = require("http");
const fs = require("fs");
const fsp = require("fs/promises");
const path = require("path");
const { spawn } = require("child_process");

const PORT = Number(process.env.PORT || 5174);
const VAULT = process.env.CREATORBUDDY_VAULT || path.join(process.env.USERPROFILE || process.env.HOME || ".", "CreatorBuddy");
const CREATORBUDDY_CLI = process.env.CREATORBUDDY_CLI || path.join(__dirname, "..", "scripts", "creatorbuddy.py");

const ROOT = __dirname;
const PUBLIC = path.join(ROOT, "public");
const CONFIG_PATH = path.join(VAULT, "config", "agent_config.json");
const DATA_DIR = path.join(VAULT, "data");

function send(res, status, payload, headers = {}) {
  const body = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
  res.writeHead(status, {
    "Content-Type": typeof payload === "string" ? "text/plain; charset=utf-8" : "application/json; charset=utf-8",
    ...headers
  });
  res.end(body);
}

function sendJson(res, status, payload) {
  send(res, status, payload, { "Cache-Control": "no-store" });
}

async function exists(file) {
  try {
    await fsp.access(file);
    return true;
  } catch {
    return false;
  }
}

async function readJson(file, fallback) {
  try {
    return JSON.parse(await fsp.readFile(file, "utf8"));
  } catch {
    return fallback;
  }
}

async function readJsonl(file) {
  try {
    const text = await fsp.readFile(file, "utf8");
    return text
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        try {
          return JSON.parse(line);
        } catch {
          return null;
        }
      })
      .filter(Boolean);
  } catch {
    return [];
  }
}

function listFilesSafe(dir) {
  try {
    return fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return [];
  }
}

function newestFiles(dir, suffix = ".json", limit = 12) {
  return listFilesSafe(dir)
    .filter((entry) => entry.isFile() && entry.name.endsWith(suffix))
    .map((entry) => {
      const file = path.join(dir, entry.name);
      const stat = fs.statSync(file);
      return { file, name: entry.name, mtime: stat.mtimeMs };
    })
    .sort((a, b) => b.mtime - a.mtime)
    .slice(0, limit);
}

function platformLabel(platform) {
  return {
    xiaohongshu: "小红书",
    douyin: "抖音",
    "wechat-mp": "公众号",
    "wechat-channels": "视频号"
  }[platform] || platform;
}

function platformShort(platform) {
  return {
    xiaohongshu: "XHS",
    douyin: "Douyin",
    "wechat-mp": "WeChat",
    "wechat-channels": "Channels"
  }[platform] || platform;
}

function parseBody(req) {
  return new Promise((resolve, reject) => {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
      if (body.length > 2_000_000) {
        req.destroy();
        reject(new Error("request body too large"));
      }
    });
    req.on("end", () => {
      if (!body.trim()) return resolve({});
      try {
        resolve(JSON.parse(body));
      } catch (error) {
        reject(error);
      }
    });
  });
}

function runAgent(args, timeoutMs = 120000) {
  return new Promise((resolve) => {
    const child = spawn("python", [CREATORBUDDY_CLI, "--workspace", VAULT, ...args], {
      cwd: ROOT,
      env: { ...process.env, PYTHONIOENCODING: "utf-8" },
      windowsHide: true
    });
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill();
      resolve({ ok: false, code: 124, stdout, stderr: `${stderr}\nTIMEOUT` });
    }, timeoutMs);
    child.stdout.on("data", (data) => (stdout += data.toString("utf8")));
    child.stderr.on("data", (data) => (stderr += data.toString("utf8")));
    child.on("close", (code) => {
      clearTimeout(timer);
      resolve({ ok: code === 0, code, stdout, stderr });
    });
    child.on("error", (error) => {
      clearTimeout(timer);
      resolve({ ok: false, code: -1, stdout, stderr: String(error) });
    });
  });
}

async function readDashboard() {
  const config = await readJson(CONFIG_PATH, {
    workspace_id: "default-workspace",
    owner: "",
    platforms: [],
    product_keywords: []
  });
  const scores = await readJson(path.join(DATA_DIR, "latest_topic_scores.json"), []);
  const runs = await readJsonl(path.join(DATA_DIR, "run_log.jsonl"));
  const pending = await readJsonl(path.join(DATA_DIR, "pending_strategy_candidates.jsonl"));
  const activeStrategy = await readJson(path.join(DATA_DIR, "active_strategy.json"), { active_rules: [] });
  const published = await readJsonl(path.join(DATA_DIR, "published_content.jsonl"));

  const topScores = Array.isArray(scores) ? scores.slice(0, 8) : [];
  const platforms = Array.isArray(config.platforms) ? config.platforms : [];
  const platformStatus = platforms.map((platform) => {
    const sample = topScores.find((item) => item.platform === platform.platform);
    return {
      platform: platform.platform,
      label: platformLabel(platform.platform),
      accountName: platform.account_name || "",
      enabled: platform.enabled !== false,
      evidenceLevel: sample?.evidence_level || "待评分",
      status: sample ? "ready" : "empty",
      latestFile: sample?.source_path || "",
      latestAt: ""
    };
  });

  const evidence = topScores.slice(0, 5).map((item) => ({
    source: platformLabel(item.platform),
    platform: item.platform,
    signal: item.topic,
    score: item.score,
    evidenceLevel: item.evidence_level || "unknown",
    why: Array.isArray(item.reasons) ? item.reasons.slice(0, 2).join(" · ") : "",
    sourcePath: item.source_path || ""
  }));

  return {
    app: "CreatorBuddy",
    vault: VAULT,
    config,
    metrics: {
      signals: Array.isArray(scores) ? scores.length : 0,
      highConfidence: topScores.filter((item) => Number(item.score) >= 85).length,
      pendingReviews: published.filter((item) => item.review_status === "pending").length,
      pendingStrategies: pending.length
    },
    recommendation: topScores[0] || null,
    topScores,
    evidence,
    platformStatus,
    activeRules: activeStrategy.active_rules || [],
    pendingStrategies: pending.slice(-5).reverse(),
    latestRun: runs[runs.length - 1] || null,
    published: published.slice(-10).reverse()
  };
}

async function handleApi(req, res, url) {
  if (req.method === "GET" && url.pathname === "/api/health") {
    return sendJson(res, 200, {
      ok: true,
      app: "CreatorBuddy",
      vault: VAULT,
      agentScript: CREATORBUDDY_CLI,
      configExists: await exists(CONFIG_PATH),
      time: new Date().toISOString()
    });
  }

  if (req.method === "GET" && url.pathname === "/api/config") {
    return sendJson(res, 200, await readJson(CONFIG_PATH, {}));
  }

  if (req.method === "GET" && url.pathname === "/api/dashboard") {
    return sendJson(res, 200, await readDashboard());
  }

  if (req.method === "POST" && url.pathname === "/api/daily-run") {
    const body = await parseBody(req);
    const args = ["today"];
    const result = await runAgent(args, 180000);
    return sendJson(res, result.ok ? 200 : 500, {
      ok: result.ok,
      code: result.code,
      stdout: result.stdout,
      stderr: result.stderr
    });
  }

  if (req.method === "POST" && url.pathname === "/api/score-topics") {
    const result = await runAgent(["today"], 120000);
    return sendJson(res, result.ok ? 200 : 500, {
      ok: result.ok,
      code: result.code,
      stdout: result.stdout,
      stderr: result.stderr
    });
  }

  if (req.method === "POST" && url.pathname === "/api/collect") {
    return sendJson(res, 501, {
      ok: false,
      error: "内测版暂未内置平台登录态采集。请先用 today / draft / precheck / review 跑通本地工作流。"
    });
  }

  if (req.method === "POST" && url.pathname === "/api/prepublish") {
    const body = await parseBody(req);
    const config = await readJson(CONFIG_PATH, { risk_keywords: [] });
    const text = `${body.title || ""}\n${body.content || ""}`;
    const risks = (config.risk_keywords || []).filter((word) => text.includes(word));
    const missing = [];
    if (!String(body.title || "").trim()) missing.push("标题为空");
    if (!String(body.content || "").trim()) missing.push("正文/脚本为空");
    if (!body.platform) missing.push("未选择平台");
    return sendJson(res, 200, {
      ok: risks.length === 0 && missing.length === 0,
      verdict: risks.length || missing.length ? "小改后发布" : "可以进入发布前最终人工确认",
      risks,
      missing,
      suggestions: [
        "保留具体场景和证据来源",
        "避免夸大收益承诺",
        "平台表达要和账号定位一致"
      ]
    });
  }

  if (req.method === "POST" && url.pathname === "/api/draft") {
    const body = await parseBody(req);
    const dashboard = await readDashboard();
    const topic = String(body.topic || dashboard.recommendation?.topic || "").trim();
    const platform = String(body.platform || dashboard.recommendation?.platform || "xiaohongshu");
    if (!topic) {
      return sendJson(res, 400, { ok: false, error: "topic is required" });
    }
    const evidence = (dashboard.evidence || [])
      .filter((item) => !body.platform || item.platform === platform)
      .slice(0, 3);
    const platformAdvice = {
      xiaohongshu: ["标题要可搜索、可收藏", "正文用步骤和避坑结构", "结尾给一个低压互动问题"],
      douyin: ["前 3 秒先说痛点或反差", "一条视频只讲一个核心观点", "结尾引导评论或私信咨询"],
      "wechat-mp": ["先建立问题背景", "用案例和推理建立信任", "结尾承接产品或服务路径"]
    }[platform] || ["保留证据来源", "减少空泛结论", "给出下一步行动"];
    const draft = {
      title: topic,
      platform,
      platformLabel: platformLabel(platform),
      opening: `如果你第一次接触 ${topic.replace(/[｜|].*$/, "")}，不要先收藏一堆教程，先把一个具体任务跑通。`,
      structure: [
        "先说用户现在卡在哪里",
        "再给 3 个可以马上执行的小任务",
        "每个任务写清楚输入、操作和完成标准",
        "最后说明这类内容如何承接你的产品或服务"
      ],
      body: [
        `今天建议做这个选题：${topic}`,
        "",
        "角度：把抽象的 AI 学习，压缩成普通人今天能完成的 3 个动作。",
        "",
        "正文骨架：",
        "1. 先说明新手为什么会卡住：工具太多、教程太散、没有完成标准。",
        "2. 给第一个任务：用一个真实场景创建任务，并让 AI 输出第一版结果。",
        "3. 给第二个任务：把结果改成可发布/可交付版本。",
        "4. 给第三个任务：保存成自己的模板，下次复用。",
        "5. 收尾：不要追求一次学完，先让系统替你完成一个重复动作。"
      ].join("\n"),
      evidence,
      checklist: platformAdvice,
      createdAt: new Date().toISOString()
    };
    return sendJson(res, 200, { ok: true, draft });
  }

  if (req.method === "POST" && url.pathname === "/api/published") {
    const body = await parseBody(req);
    if (!body.platform || !body.title) {
      return sendJson(res, 400, { ok: false, error: "platform and title are required" });
    }
    const args = [
      "review",
      "--platform",
      String(body.platform),
      "--title",
      String(body.title),
    ];
    if (body.publishedAt) args.push("--published-at", String(body.publishedAt));
    if (body.metrics) args.push("--metrics-json", JSON.stringify(body.metrics));
    const result = await runAgent(args, 60000);
    return sendJson(res, result.ok ? 200 : 500, {
      ok: result.ok,
      code: result.code,
      stdout: result.stdout,
      stderr: result.stderr
    });
  }

  return sendJson(res, 404, { ok: false, error: "API not found" });
}

async function serveStatic(req, res, url) {
  let file = url.pathname === "/" ? "index.html" : decodeURIComponent(url.pathname.slice(1));
  file = file.replace(/[\\/]+/g, path.sep);
  const target = path.normalize(path.join(PUBLIC, file));
  if (!target.startsWith(PUBLIC)) return send(res, 403, "Forbidden");
  try {
    const stat = await fsp.stat(target);
    if (!stat.isFile()) throw new Error("not file");
    const ext = path.extname(target).toLowerCase();
    const types = {
      ".html": "text/html; charset=utf-8",
      ".css": "text/css; charset=utf-8",
      ".js": "application/javascript; charset=utf-8",
      ".json": "application/json; charset=utf-8",
      ".png": "image/png",
      ".svg": "image/svg+xml"
    };
    res.writeHead(200, { "Content-Type": types[ext] || "application/octet-stream" });
    fs.createReadStream(target).pipe(res);
  } catch {
    send(res, 404, "Not found");
  }
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  try {
    if (url.pathname.startsWith("/api/")) return await handleApi(req, res, url);
    return await serveStatic(req, res, url);
  } catch (error) {
    return sendJson(res, 500, { ok: false, error: String(error.message || error) });
  }
});

server.listen(PORT, () => {
  console.log(`CreatorBuddy running at http://localhost:${PORT}`);
  console.log(`Vault: ${VAULT}`);
});
