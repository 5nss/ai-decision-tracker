// src/app.js — Frontend SPA for SMART DECISION TRACKER
// Served by FastAPI at http://127.0.0.1:8000
// All API calls go to the same origin (/api/...) — no CORS issues.

const API = "/api";

// ── Toast notification helper ─────────────────────────────────────────────────
let toastTimer = null;
function showToast(msg, type = "info", durationMs = 3500) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = msg;
  el.className = `toast ${type} show`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    el.classList.remove("show");
  }, durationMs);
}

// ── Tiny DOM helper ───────────────────────────────────────────────────────────
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class")   { node.className = v; }
    else if (k === "data") { Object.entries(v).forEach(([dk, dv]) => node.dataset[dk] = dv); }
    else if (typeof v === "function") { node.addEventListener(k, v); }
    else                 { node.setAttribute(k, v); }
  }
  for (const child of children) {
    if (child == null) continue;
    node.appendChild(typeof child === "string"
      ? document.createTextNode(child)
      : child);
  }
  return node;
}

// ── HTML setter (for rich strings) ───────────────────────────────────────────
function elHTML(tag, attrs = {}, html = "") {
  const node = el(tag, attrs);
  node.innerHTML = html;
  return node;
}

// ── Spinner element ───────────────────────────────────────────────────────────
function spinner() {
  return el("div", { class: "spinner" });
}

// ── SPA Router ────────────────────────────────────────────────────────────────
function router() {
  const hash = location.hash.replace(/^#\/?/, "").split("?")[0];
  const app  = document.getElementById("app");
  app.innerHTML = "";

  // Update active nav link
  document.querySelectorAll(".nav-link").forEach(a => {
    a.classList.toggle("active", a.getAttribute("href") === location.hash ||
      (hash === "" && a.getAttribute("href") === "#/"));
  });

  switch (hash) {
    case "decision": app.appendChild(renderDecisionForm()); break;
    case "outcome":  app.appendChild(renderOutcomeForm());  break;
    case "insights": app.appendChild(renderInsights());     break;
    default:         app.appendChild(renderHome());         break;
  }
}

// ── Home ──────────────────────────────────────────────────────────────────────
function renderHome() {
  // Stats row
  const statsRow = el("div", { class: "stats-row" });
  const totalStat   = el("div", { class: "stat-card" },
    el("span", { class: "stat-value", id: "stat-total" }, "—"),
    el("span", { class: "stat-label" }, "Decisions Logged")
  );
  const outcomeStat = el("div", { class: "stat-card" },
    el("span", { class: "stat-value", id: "stat-outcomes" }, "—"),
    el("span", { class: "stat-label" }, "Outcomes Recorded")
  );
  const behaviorStat = el("div", { class: "stat-card" },
    el("span", { class: "stat-value", id: "stat-behaviors" }, "—"),
    el("span", { class: "stat-label" }, "Behavioral Patterns")
  );
  statsRow.append(totalStat, outcomeStat, behaviorStat);

  // Nav buttons
  const nav = el("div", { class: "card-nav" },
    el("a", { href: "#/decision", class: "button" },          "＋ New Decision"),
    el("a", { href: "#/outcome",  class: "button secondary" }, "📋 Record Outcome"),
    el("a", { href: "#/insights", class: "button secondary" }, "🔍 View AI Insights")
  );

  // Hero card
  const heroCard = el("div", { class: "glass-card" },
    el("h2", {}, "Decision Dashboard"),
    el("p", { class: "hero-tagline" },
      "Log decisions, capture your reasoning, record outcomes — then let the AI surface patterns you'd otherwise miss."),
    statsRow,
    nav
  );

  // Recent decisions list
  const listWrap = el("div", { class: "glass-card" },
    el("h3", {}, "Recent Decisions"),
    el("div", { id: "decisions-list" }, spinner())
  );

  fetchHomeData();

  return el("div", {}, heroCard, listWrap);
}

async function fetchHomeData() {
  try {
    const [decisions, outcomes, behaviors] = await Promise.all([
      fetch(`${API}/decisions`).then(r => r.json()),
      fetch(`${API}/outcomes`).then(r => r.json()),
      fetch(`${API}/behaviors`).then(r => r.json()),
    ]);

    const statTotal   = document.getElementById("stat-total");
    const statOutcome = document.getElementById("stat-outcomes");
    const statBehav   = document.getElementById("stat-behaviors");
    if (statTotal)   statTotal.textContent   = decisions.length;
    if (statOutcome) statOutcome.textContent = outcomes.length;
    if (statBehav)   statBehav.textContent   = behaviors.length;

    const listEl = document.getElementById("decisions-list");
    if (!listEl) return;

    if (decisions.length === 0) {
      listEl.innerHTML = "";
      listEl.appendChild(
        el("p", { style: "color:var(--muted);font-size:.9rem;" },
          "No decisions yet. Click '＋ New Decision' to get started.")
      );
      return;
    }

    const ul = el("ul", { class: "decisions-list" });
    [...decisions].reverse().slice(0, 8).forEach(d => {
      const hasOutcome = outcomes.some(o => o.decision_id === d.id);
      const li = el("li", { class: "decision-item" },
        el("span", { class: "decision-id" }, `#${d.id}`),
        d.decision_text,
        el("span", { class: `decision-badge ${hasOutcome ? "badge-done" : "badge-pending"}` },
          hasOutcome ? "✓ Outcome" : "⏳ Pending"),
        el("span", { class: "decision-meta" },
          `Expected: ${d.expected_outcome.slice(0, 90)}${d.expected_outcome.length > 90 ? "…" : ""}`)
      );
      ul.appendChild(li);
    });
    listEl.innerHTML = "";
    listEl.appendChild(ul);

  } catch (e) {
    console.error(e);
    const listEl = document.getElementById("decisions-list");
    if (listEl) {
      listEl.innerHTML = "";
      listEl.appendChild(
        el("p", { style: "color:var(--danger);font-size:.9rem;" },
          "⚠ Could not connect to the backend. Make sure the server is running on port 8000.")
      );
    }
  }
}

// ── Decision Form ─────────────────────────────────────────────────────────────
function renderDecisionForm() {
  const submitBtn = el("button", { type: "submit", class: "button" }, "Save Decision");

  const form = el("form", { class: "glass-card",
    submit: async (e) => {
      e.preventDefault();
      submitBtn.disabled  = true;
      submitBtn.textContent = "Saving…";
      const payload = Object.fromEntries(new FormData(form));
      payload.user_id = Number(payload.user_id);
      try {
        const resp = await fetch(`${API}/decisions/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          throw new Error(err.detail || "Server error");
        }
        const created = await resp.json();
        showToast(`✅ Decision #${created.id} saved successfully!`, "success");
        setTimeout(() => { location.hash = "#/"; }, 800);
      } catch (err) {
        console.error(err);
        showToast(`❌ ${err.message}`, "error");
        submitBtn.disabled  = false;
        submitBtn.textContent = "Save Decision";
      }
    }
  },
    el("h2", {}, "Log a Decision"),
    el("p", {}, "Record your decision, the reasoning behind it, and what you expect to happen."),
    el("label", { class: "field-label" }, "User ID"),
    el("input",    { type: "number", name: "user_id",         placeholder: "e.g. 1",                        class: "input-field", required: "true", min: "1" }),
    el("label", { class: "field-label" }, "Decision Summary"),
    el("input",    { type: "text",   name: "decision_text",   placeholder: "One-line summary of the decision",class: "input-field", required: "true" }),
    el("label", { class: "field-label" }, "Reasoning & Rationale"),
    el("textarea", { name: "reasoning",       placeholder: "Why are you making this decision? What do you think/assume/believe?",  class: "input-field", rows: "4", required: "true" }),
    el("label", { class: "field-label" }, "Expected Outcome"),
    el("textarea", { name: "expected_outcome", placeholder: "What should happen if this decision is right?", class: "input-field", rows: "2", required: "true" }),
    el("label", { class: "field-label" }, "Constraints (optional)"),
    el("textarea", { name: "constraints",      placeholder: "Time, budget, dependencies, risks…",            class: "input-field", rows: "2" }),
    el("div", { class: "card-nav" },
      submitBtn,
      el("a", { href: "#/", class: "button secondary" }, "← Cancel")
    )
  );

  return form;
}

// ── Outcome Form ──────────────────────────────────────────────────────────────
function renderOutcomeForm() {
  const submitBtn = el("button", { type: "submit", class: "button" }, "Save Outcome");

  const form = el("form", { class: "glass-card",
    submit: async (e) => {
      e.preventDefault();
      submitBtn.disabled  = true;
      submitBtn.textContent = "Saving…";
      const payload = Object.fromEntries(new FormData(form));
      payload.decision_id = Number(payload.decision_id);
      try {
        const resp = await fetch(`${API}/outcomes/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          throw new Error(err.detail || "Server error");
        }
        const created = await resp.json();
        showToast(`✅ Outcome recorded! AI features auto-extracted.`, "success");
        setTimeout(() => { location.hash = "#/insights"; }, 1200);
      } catch (err) {
        console.error(err);
        showToast(`❌ ${err.message}`, "error");
        submitBtn.disabled  = false;
        submitBtn.textContent = "Save Outcome";
      }
    }
  },
    el("h2", {}, "Record an Outcome"),
    el("p", {}, "Link the actual outcome back to your decision. This triggers automatic feature extraction and behavior analysis."),
    el("label", { class: "field-label" }, "Decision ID"),
    el("input",    { type: "number", name: "decision_id",    placeholder: "Decision ID (from your dashboard)", class: "input-field", required: "true", min: "1" }),
    el("label", { class: "field-label" }, "What Actually Happened"),
    el("textarea", { name: "actual_outcome", placeholder: "Describe what actually happened…",  class: "input-field", rows: "4", required: "true" }),
    el("label", { class: "field-label" }, "Context & Notes (optional)"),
    el("textarea", { name: "context",        placeholder: "Any extra context, surprises, or lessons…", class: "input-field", rows: "3" }),
    el("div", { class: "card-nav" },
      submitBtn,
      el("a", { href: "#/", class: "button secondary" }, "← Cancel")
    )
  );

  return form;
}

// ── Insights ──────────────────────────────────────────────────────────────────
function renderInsights() {
  const analysisResultDiv = el("div", { id: "analysis-result" });
  const behaviorsDiv      = el("div", { id: "behaviors-section" }, spinner());

  // Behavior tab content
  const behaviorsCard = el("div", { class: "glass-card" },
    el("h3", {}, "🧬 Behavioral Patterns"),
    el("p", {}, "Patterns detected across all your decisions — updated automatically when you record outcomes."),
    behaviorsDiv
  );

  // Analysis picker card
  const pickerCard = el("div", { class: "glass-card" },
    el("h2", {}, "AI Habit Analysis"),
    el("p", {}, "Analyze your entire decision history to identify macro-level habits, strengths, and blind spots."),
    el("div", { id: "insights-pick", style: "margin-top:.75rem;" }, spinner()),
    analysisResultDiv,
    el("div", { class: "card-nav", style: "margin-top:1rem;" },
      el("a", { href: "#/", class: "button secondary" }, "← Back to Dashboard")
    )
  );

  // Load behaviors
  _loadBehaviors(behaviorsDiv);
  // Load habit analyzer
  _loadHabitAnalyzer();

  return el("div", {}, pickerCard, behaviorsCard);
}

async function _loadBehaviors(container) {
  try {
    const behaviors = await fetch(`${API}/behaviors`).then(r => r.json());
    container.innerHTML = "";

    if (!behaviors.length) {
      container.appendChild(
        el("p", { style: "color:var(--muted);font-size:.9rem;" },
          "No behavioral patterns yet. Record outcomes for your decisions to start building your behavior profile.")
      );
      return;
    }

    // Group by confidence tier
    const high   = behaviors.filter(b => b.confidence >= 0.5);
    const medium = behaviors.filter(b => b.confidence >= 0.2 && b.confidence < 0.5);
    const low    = behaviors.filter(b => b.confidence < 0.2);

    const _section = (title, items, cls) => {
      if (!items.length) return null;
      const wrap = el("div", { class: "behavior-section" },
        el("p", { class: "behavior-tier-label" }, title)
      );
      items.forEach(b => {
        const bar = el("div", { class: "confidence-bar" });
        bar.style.setProperty("--pct", `${Math.round(b.confidence * 100)}%`);
        wrap.appendChild(
          el("div", { class: `behavior-chip ${cls}` },
            el("div", { class: "behavior-chip-top" },
              el("span", { class: "behavior-tag" }, _humanizeTag(b.behavior)),
              el("span", { class: "behavior-freq" }, `×${b.frequency}`)
            ),
            bar,
            el("span", { class: "behavior-conf" }, `${Math.round(b.confidence * 100)}% confidence`)
          )
        );
      });
      return wrap;
    };

    const sections = [
      _section("⚠️ Strong patterns (high confidence)", high,   "chip-high"),
      _section("📊 Emerging patterns",                 medium, "chip-medium"),
      _section("🔍 Weak signals (low confidence)",     low,    "chip-low"),
    ].filter(Boolean);

    sections.forEach(s => container.appendChild(s));

  } catch (e) {
    container.innerHTML = "<p style='color:var(--danger)'>Could not load behavior data.</p>";
  }
}

function _humanizeTag(tag) {
  const MAP = {
    "ignores_constraints":       "🚧 Ignores Constraints",
    "poor_outcome_track_record": "📉 Outcomes Below Expectations",
    "good_outcome_track_record": "📈 Consistent Good Outcomes",
    "over_assumes":              "💭 Over-Assumes",
    "makes_assumptions":         "🤔 Makes Assumptions",
    "active_in_study":           "📚 Study Domain",
    "active_in_work":            "💼 Work Domain",
    "active_in_habit":           "🔁 Habit Domain",
    "active_in_finance":         "💰 Finance Domain",
    "active_in_social":          "🤝 Social Domain",
    "active_in_other":           "🌐 Mixed Domains",
  };
  return MAP[tag] || tag.replace(/_/g, " ");
}

function _loadHabitAnalyzer() {
  fetch(`${API}/decisions`)
    .then(r => r.json())
    .then(decisions => {
      const pickDiv = document.getElementById("insights-pick");
      if (!pickDiv) return;
      pickDiv.innerHTML = "";

      if (decisions.length < 3) {
        pickDiv.appendChild(el("p", { style: "color:var(--muted);" }, `🔒 AI Habit Analysis locked. Log at least 3 decisions to unlock. (Currently ${decisions.length}/3)`));
        return;
      }

      const analyzeBtn = el("button", { class: "button",
        click: () => _runHabitAnalysis(analyzeBtn)
      }, "🧠 Analyze My Decision Habits");

      pickDiv.append(analyzeBtn);
    })
    .catch(() => {
      const pickDiv = document.getElementById("insights-pick");
      if (pickDiv) pickDiv.innerHTML = "<p style='color:var(--danger)'>Could not load decisions.</p>";
    });
}

async function _runHabitAnalysis(btn) {
  btn.disabled = true;
  btn.textContent = "Analyzing…";

  const res = document.getElementById("analysis-result");
  if (res) { res.innerHTML = ""; res.appendChild(spinner()); }

  try {
    const resp = await fetch(`${API}/ai/analyze_user?user_id=1`, { method: "POST" });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || "Analysis failed");
    }
    const data = await resp.json();

    if (res) {
      res.innerHTML = "";
      res.appendChild(_renderAnalysisCard(data));
    }

    // Refresh behavior panel after analysis
    const behDiv = document.getElementById("behaviors-section");
    if (behDiv) { behDiv.innerHTML = ""; behDiv.appendChild(spinner()); _loadBehaviors(behDiv); }

  } catch (err) {
    showToast("❌ " + err.message, "error");
    if (res) res.innerHTML = "";
  } finally {
    btn.disabled = false;
    btn.textContent = "🧠 Analyze My Decision Habits";
  }
}

function _renderAnalysisCard(data) {
  const wrap = el("div", { class: "analysis-wrap" });

  // ── Source badge ─────────────────────────────────────────────
  const isGemini = data.analysis_source === "gemini";
  wrap.appendChild(
    el("div", { class: `source-badge ${isGemini ? "source-gemini" : "source-rule"}` },
      isGemini ? "✨ Powered by Google Gemini" : "📐 Rule-Based Analysis (set GEMINI_API_KEY to unlock AI)"
    )
  );

  // ── AI error notice (if key missing / call failed) ────────────
  if (data.ai_error) {
    wrap.appendChild(
      el("div", { class: "ai-error-notice" },
        el("p", {}, `⚠ AI unavailable: ${data.ai_error}`)
      )
    );
  }

  // ── GEMINI INSIGHT BLOCK ──────────────────────────────────────
  if (data.ai_insight) {
    const ai = data.ai_insight;

    // AI Summary
    if (ai.summary) {
      wrap.appendChild(
        el("div", { class: "insight-section ai-summary-card" },
          el("h3", {}, "🧠 Macro-Analysis Summary"),
          el("p", { class: "ai-summary-text" }, ai.summary)
        )
      );
    }

    // Overall Reasoning Score
    if (ai.overall_reasoning_score) {
      const scoreClass = ai.overall_reasoning_score >= 7 ? "score-high" : ai.overall_reasoning_score >= 4 ? "score-mid" : "score-low";
      const rqCard = el("div", { class: "insight-section reasoning-card" },
        el("h3", {}, "🎯 Overall Reasoning Quality"),
        el("div", { class: "score-row" },
          el("span", { class: `score-badge ${scoreClass}` }, `${ai.overall_reasoning_score}/10`),
          el("span", { class: "score-verdict" }, "Based on consistency and logic across all logged decisions")
        )
      );
      wrap.appendChild(rqCard);
    }

    // Strengths
    if (ai.strengths && ai.strengths.length) {
      const strengthsCard = el("div", { class: "insight-section outcome-analysis-card" },
        el("h3", {}, "⭐ Notable Strengths")
      );
      const ul = el("ul", { class: "pattern-list" });
      ai.strengths.forEach(s => ul.appendChild(el("li", {}, s)));
      strengthsCard.appendChild(ul);
      wrap.appendChild(strengthsCard);
    }

    // Blind Spots
    if (ai.common_blind_spots && ai.common_blind_spots.length) {
      const bsCard = el("div", { class: "insight-section assumption-card" },
        el("h3", {}, "⚠️ Common Blind Spots")
      );
      const ul = el("ul", { class: "assumption-list" });
      ai.common_blind_spots.forEach(b => ul.appendChild(el("li", {}, b)));
      bsCard.appendChild(ul);
      wrap.appendChild(bsCard);
    }

    // Habitual Patterns
    if (ai.habitual_patterns && ai.habitual_patterns.length) {
      const bpCard = el("div", { class: "insight-section behavior-ai-card" },
        el("h3", {}, "🧬 Habitual Patterns")
      );
      const ul = el("ul", { class: "pattern-list" });
      ai.habitual_patterns.forEach(p => ul.appendChild(el("li", {}, p)));
      bpCard.appendChild(ul);
      wrap.appendChild(bpCard);
    }
    
    // Recommendations
    if (ai.macro_recommendations && ai.macro_recommendations.length) {
      const recCard = el("div", { class: "insight-section recommendations" },
        el("h3", {}, "💡 Macro Recommendations")
      );
      const ul = el("ul", { class: "rec-list" });
      ai.macro_recommendations.forEach(r => ul.appendChild(el("li", {}, r)));
      recCard.appendChild(ul);
      wrap.appendChild(recCard);
    }
  } else if (data.recommendations && data.recommendations.length) {
      // Fallback rule-based recommendations
      const recCard = el("div", { class: "insight-section recommendations" },
        el("h3", {}, "💡 Recommendations")
      );
      const ul = el("ul", { class: "rec-list" });
      data.recommendations.forEach(r => ul.appendChild(el("li", {}, r)));
      recCard.appendChild(ul);
      wrap.appendChild(recCard);
  }

  return wrap;
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
window.addEventListener("hashchange", router);
window.addEventListener("load", router);
