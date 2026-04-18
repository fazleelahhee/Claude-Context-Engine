"""Embedded HTML page for the CCE dashboard.

Single-file SPA. Fetches data from /api/* on tab switch.
Polls /api/status every 5 seconds for live updates.
No external dependencies — all CSS and JS inline.
"""

PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CCE Dashboard</title>
<style>
:root {
  --bg: #0a0c10;
  --surface: #111318;
  --surface2: #181c24;
  --surface3: #1e2330;
  --border: #252b38;
  --border2: #2e3547;
  --text: #e2e8f0;
  --text2: #8892a4;
  --text3: #525e72;
  --accent: #4f8ef7;
  --accent-dim: #1a2d52;
  --green: #34d399;
  --green-dim: #0d2e22;
  --yellow: #fbbf24;
  --yellow-dim: #2a1f08;
  --red: #f87171;
  --red-dim: #2a1010;
  --purple: #a78bfa;
  --purple-dim: #1e1535;
  --radius: 10px;
  --radius-sm: 6px;
  --shadow: 0 1px 3px rgba(0,0,0,.4), 0 4px 16px rgba(0,0,0,.25);
  --shadow-sm: 0 1px 2px rgba(0,0,0,.3);
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  --mono: "SF Mono", "Fira Code", "Cascadia Code", monospace;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body { height: 100%; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font);
  font-size: 13.5px;
  line-height: 1.5;
  display: flex;
  overflow: hidden;
}

/* ── Sidebar ─────────────────────────────────────────────────────────── */

.sidebar {
  width: 220px;
  min-width: 220px;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 0;
  height: 100vh;
  position: sticky;
  top: 0;
}

.sidebar-logo {
  padding: 20px 20px 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-mark {
  width: 30px;
  height: 30px;
  background: linear-gradient(135deg, var(--accent) 0%, #7c6af7 100%);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 12px;
  letter-spacing: -0.5px;
  color: #fff;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(79,142,247,.35);
}

.logo-text {
  font-weight: 700;
  font-size: 14px;
  color: var(--text);
  letter-spacing: 0.3px;
}

.project-badge {
  margin: 10px 16px 4px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 7px 10px;
  display: flex;
  align-items: center;
  gap: 7px;
}

.project-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--green);
  flex-shrink: 0;
  box-shadow: 0 0 0 2px rgba(52,211,153,.2);
}

.project-name {
  font-size: 12px;
  color: var(--text2);
  font-family: var(--mono);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nav {
  padding: 8px 10px;
  flex: 1;
}

.nav-section {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: .8px;
  text-transform: uppercase;
  color: var(--text3);
  padding: 12px 8px 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--text2);
  font-size: 13px;
  font-weight: 500;
  border: none;
  background: none;
  width: 100%;
  text-align: left;
  transition: background .15s, color .15s;
  position: relative;
}

.nav-item svg { flex-shrink: 0; opacity: .7; }

.nav-item:hover { background: var(--surface2); color: var(--text); }
.nav-item:hover svg { opacity: 1; }

.nav-item.active {
  background: var(--accent-dim);
  color: var(--accent);
  font-weight: 600;
}
.nav-item.active svg { opacity: 1; }

.nav-item .badge-count {
  margin-left: auto;
  background: var(--surface3);
  color: var(--text3);
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 10px;
  min-width: 20px;
  text-align: center;
}

.nav-item.active .badge-count {
  background: rgba(79,142,247,.2);
  color: var(--accent);
}

.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--border);
}

.poll-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text3);
}

.poll-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--green);
  animation: pulse 2.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: .3; }
}

/* ── Main content ─────────────────────────────────────────────────────── */

.main {
  flex: 1;
  overflow-y: auto;
  height: 100vh;
  background: var(--bg);
}

.page { display: none; padding: 28px 32px; max-width: 960px; }
.page.active { display: block; }

/* ── Page header ─────────────────────────────────────────────────────── */

.page-header {
  margin-bottom: 24px;
}

.page-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: -.3px;
}

.page-sub {
  font-size: 13px;
  color: var(--text2);
  margin-top: 2px;
}

/* ── Stat cards ─────────────────────────────────────────────────────── */

.stat-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 24px;
}

.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px 20px;
  box-shadow: var(--shadow-sm);
  transition: border-color .2s;
}

.stat-card:hover { border-color: var(--border2); }

.stat-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
}

.stat-icon.blue  { background: rgba(79,142,247,.12); }
.stat-icon.green { background: rgba(52,211,153,.12); }
.stat-icon.yellow{ background: rgba(251,191,36,.12); }
.stat-icon.purple{ background: rgba(167,139,250,.12); }

.stat-num {
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -1px;
  line-height: 1;
  margin-bottom: 4px;
}

.stat-num.blue   { color: var(--accent); }
.stat-num.green  { color: var(--green); }
.stat-num.yellow { color: var(--yellow); }
.stat-num.purple { color: var(--purple); }

.stat-label {
  font-size: 11.5px;
  color: var(--text2);
  font-weight: 500;
}

/* ── Panels ─────────────────────────────────────────────────────────── */

.panel-row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }

.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  box-shadow: var(--shadow-sm);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.panel-title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .4px;
  text-transform: uppercase;
  color: var(--text2);
}

/* ── Health rows ─────────────────────────────────────────────────────── */

.health-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 0;
  border-bottom: 1px solid var(--border);
}

.health-item:last-child { border-bottom: none; }

.health-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text);
}

.health-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.health-dot.ok      { background: var(--green); box-shadow: 0 0 0 2px rgba(52,211,153,.15); }
.health-dot.stale   { background: var(--yellow); box-shadow: 0 0 0 2px rgba(251,191,36,.15); }
.health-dot.missing { background: var(--red); box-shadow: 0 0 0 2px rgba(248,113,113,.15); }

/* ── Badges ─────────────────────────────────────────────────────────── */

.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 9px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: .2px;
}

.badge-ok      { background: var(--green-dim);  color: var(--green);  }
.badge-stale   { background: var(--yellow-dim); color: var(--yellow); }
.badge-missing { background: var(--red-dim);    color: var(--red);    }
.badge-active  { background: var(--accent-dim); color: var(--accent); }
.badge-closed  { background: var(--surface2);   color: var(--text3);  }
.badge-num     { background: var(--surface2);   color: var(--text2);  }

/* ── Buttons ─────────────────────────────────────────────────────────── */

.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: var(--radius-sm);
  font-size: 12.5px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  transition: all .15s;
  white-space: nowrap;
}

.btn-primary {
  background: var(--accent);
  color: #fff;
  box-shadow: 0 1px 3px rgba(79,142,247,.4);
}
.btn-primary:hover { background: #6a9ef8; box-shadow: 0 2px 8px rgba(79,142,247,.5); }

.btn-ghost {
  background: transparent;
  color: var(--text2);
  border: 1px solid var(--border2);
}
.btn-ghost:hover { background: var(--surface2); color: var(--text); border-color: var(--border2); }

.btn-danger {
  background: rgba(248,113,113,.1);
  color: var(--red);
  border: 1px solid rgba(248,113,113,.2);
}
.btn-danger:hover { background: rgba(248,113,113,.18); }

.btn-icon {
  width: 28px;
  height: 28px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text2);
  cursor: pointer;
  transition: all .15s;
  font-size: 13px;
}
.btn-icon:hover { background: var(--surface3); color: var(--text); border-color: var(--border2); }
.btn-icon.del:hover { background: var(--red-dim); color: var(--red); border-color: rgba(248,113,113,.25); }

.btn-row {
  display: flex;
  gap: 8px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

/* ── Table ─────────────────────────────────────────────────────────── */

.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.search-wrap {
  position: relative;
  flex: 1;
  max-width: 280px;
}

.search-wrap svg {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text3);
  pointer-events: none;
}

.search-input {
  width: 100%;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 8px 10px 8px 32px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  outline: none;
  transition: border-color .15s;
  font-family: var(--font);
}

.search-input:focus { border-color: var(--accent); }
.search-input::placeholder { color: var(--text3); }

.data-table {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}

.table-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 80px 100px 70px;
  padding: 10px 16px;
  background: var(--surface2);
  border-bottom: 1px solid var(--border);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .5px;
  text-transform: uppercase;
  color: var(--text3);
  gap: 12px;
}

.table-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 80px 100px 70px;
  padding: 10px 16px;
  border-top: 1px solid var(--border);
  align-items: center;
  gap: 12px;
  transition: background .12s;
}

.table-row:hover { background: var(--surface2); }

.file-path {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chunk-count {
  font-size: 12px;
  color: var(--text2);
  font-family: var(--mono);
}

.row-actions { display: flex; gap: 5px; align-items: center; }

/* ── No data ─────────────────────────────────────────────────────────── */

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 20px;
  color: var(--text3);
  gap: 10px;
}

.empty svg { opacity: .35; }
.empty-title { font-size: 13.5px; font-weight: 600; color: var(--text2); }
.empty-sub   { font-size: 12px; }

/* ── Sessions ─────────────────────────────────────────────────────────── */

.session-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 10px;
  overflow: hidden;
  transition: border-color .15s;
}

.session-card:hover { border-color: var(--border2); }

.session-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  cursor: pointer;
  gap: 12px;
}

.session-header-left { min-width: 0; }

.session-name {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-meta {
  font-size: 11.5px;
  color: var(--text2);
  margin-top: 2px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.session-meta-dot { color: var(--text3); }

.session-body {
  display: none;
  border-top: 1px solid var(--border);
  padding: 14px 18px;
}

.session-body.open { display: block; }

.decision-label {
  font-size: 10.5px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .6px;
  color: var(--text3);
  margin-bottom: 8px;
}

.decision-item {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  font-size: 12.5px;
  color: var(--text);
  margin-bottom: 5px;
  line-height: 1.5;
}

/* ── Savings ─────────────────────────────────────────────────────────── */

.bar-group { margin-bottom: 6px; }

.bar-meta {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 5px;
}

.bar-label-text { font-size: 12px; color: var(--text2); }
.bar-value-text { font-size: 12px; font-weight: 600; font-family: var(--mono); }

.bar-track {
  height: 6px;
  background: var(--surface2);
  border-radius: 3px;
  overflow: hidden;
}

.bar-fill {
  height: 6px;
  border-radius: 3px;
  transition: width .5s ease;
}

.savings-total {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.savings-total-label { font-size: 12.5px; color: var(--text2); }

.savings-total-value {
  font-size: 18px;
  font-weight: 800;
  color: var(--green);
  letter-spacing: -.5px;
}

.savings-total-pct {
  font-size: 11.5px;
  color: var(--green);
  opacity: .7;
  margin-left: 4px;
}

/* Compression selector */
.comp-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  margin-top: 10px;
}

.comp-btn {
  padding: 9px 4px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 600;
  background: var(--surface2);
  border: 1px solid var(--border);
  color: var(--text2);
  cursor: pointer;
  text-align: center;
  transition: all .15s;
}

.comp-btn:hover { border-color: var(--border2); color: var(--text); }

.comp-btn.active {
  background: var(--accent-dim);
  border-color: rgba(79,142,247,.4);
  color: var(--accent);
}

/* ── Banner ─────────────────────────────────────────────────────────── */

.banner {
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(79,142,247,.08);
  border: 1px solid rgba(79,142,247,.2);
  border-radius: var(--radius);
  padding: 12px 16px;
  font-size: 13px;
  color: #7eb8ff;
  margin-bottom: 20px;
}

/* ── Toast ─────────────────────────────────────────────────────────── */

.toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  background: var(--surface2);
  border: 1px solid var(--border2);
  border-radius: var(--radius);
  padding: 11px 16px;
  font-size: 13px;
  color: var(--text);
  box-shadow: var(--shadow);
  opacity: 0;
  transform: translateY(8px);
  transition: opacity .2s, transform .2s;
  pointer-events: none;
  z-index: 100;
  max-width: 320px;
}

.toast.show { opacity: 1; transform: translateY(0); }

/* ── Spinner ─────────────────────────────────────────────────────────── */

.spinner {
  display: inline-block;
  width: 13px;
  height: 13px;
  border: 2px solid var(--border2);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin .65s linear infinite;
  vertical-align: middle;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Divider ─────────────────────────────────────────────────────────── */
.divider { height: 1px; background: var(--border); margin: 20px 0; }

/* ── Scrollbar ─────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text3); }
</style>
</head>
<body>

<!-- Sidebar -->
<aside class="sidebar">
  <div class="sidebar-logo">
    <div class="logo-mark">CCE</div>
    <span class="logo-text">Dashboard</span>
  </div>

  <div class="project-badge">
    <div class="project-dot"></div>
    <span class="project-name" id="nav-project">loading…</span>
  </div>

  <nav class="nav">
    <div class="nav-section">Menu</div>
    <button class="nav-item active" onclick="showPage('overview')">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
      Overview
    </button>
    <button class="nav-item" onclick="showPage('files')">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14,2 14,8 20,8"/></svg>
      Files
      <span class="badge-count" id="nav-files-count">—</span>
    </button>
    <button class="nav-item" onclick="showPage('sessions')">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
      Sessions
      <span class="badge-count" id="nav-sessions-count">—</span>
    </button>
    <button class="nav-item" onclick="showPage('savings')">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22,12 18,12 15,21 9,3 6,12 2,12"/></svg>
      Savings
    </button>
  </nav>

  <div class="sidebar-footer">
    <div class="poll-indicator">
      <div class="poll-dot"></div>
      Live — updates every 5s
    </div>
  </div>
</aside>

<!-- Main -->
<main class="main">

  <!-- Overview -->
  <div class="page active" id="page-overview">
    <div class="page-header">
      <div class="page-title">Overview</div>
      <div class="page-sub">Index health and recent activity</div>
    </div>

    <div id="uninit-banner" class="banner" style="display:none">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      Index not initialised — run <code style="font-family:var(--mono);background:rgba(79,142,247,.15);padding:1px 6px;border-radius:4px;font-size:12px">cce init</code> in your project first.
    </div>

    <div class="stat-row">
      <div class="stat-card">
        <div class="stat-icon blue">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#4f8ef7" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="16,3 21,3 21,8"/><line x1="4" y1="20" x2="21" y2="3"/><polyline points="21,16 21,21 16,21"/><line x1="15" y1="15" x2="21" y2="21"/></svg>
        </div>
        <div class="stat-num blue" id="stat-chunks">—</div>
        <div class="stat-label">Chunks indexed</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon green">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14,2 14,8 20,8"/></svg>
        </div>
        <div class="stat-num green" id="stat-files">—</div>
        <div class="stat-label">Files indexed</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon yellow">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#fbbf24" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        </div>
        <div class="stat-num yellow" id="stat-queries">—</div>
        <div class="stat-label">Queries run</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon purple">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23,6 13.5,15.5 8.5,10.5 1,18"/><polyline points="17,6 23,6 23,12"/></svg>
        </div>
        <div class="stat-num purple" id="stat-saved">—</div>
        <div class="stat-label">Tokens saved</div>
      </div>
    </div>

    <div class="panel-row">
      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">Index Health</span>
        </div>
        <div id="health-rows">
          <div class="empty"><div class="spinner"></div></div>
        </div>
        <div class="btn-row">
          <button class="btn btn-primary" onclick="doReindex(false)" id="btn-reindex-changed">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23,4 23,10 17,10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
            Reindex changed
          </button>
          <button class="btn btn-ghost" onclick="doReindex(true)" id="btn-reindex-full">Full reindex</button>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">Recent Sessions</span>
        </div>
        <div id="recent-sessions">
          <div class="empty"><div class="spinner"></div></div>
        </div>
      </div>
    </div>
  </div>

  <!-- Files -->
  <div class="page" id="page-files">
    <div class="page-header">
      <div class="page-title">Files</div>
      <div class="page-sub">All indexed files and their status</div>
    </div>
    <div class="toolbar">
      <div class="search-wrap">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input class="search-input" placeholder="Filter files…" oninput="filterFiles(this.value)" id="file-filter">
      </div>
      <button class="btn btn-ghost" onclick="doExport()">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7,10 12,15 17,10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        Export JSON
      </button>
      <button class="btn btn-danger" onclick="doClear()">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3,6 5,6 21,6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>
        Clear index
      </button>
    </div>
    <div class="data-table">
      <div class="table-head">
        <div>File path</div><div>Chunks</div><div>Status</div><div>Actions</div>
      </div>
      <div id="file-rows">
        <div class="empty"><div class="spinner"></div></div>
      </div>
    </div>
  </div>

  <!-- Sessions -->
  <div class="page" id="page-sessions">
    <div class="page-header">
      <div class="page-title">Sessions</div>
      <div class="page-sub">Past Claude coding sessions and captured decisions</div>
    </div>
    <div id="session-list">
      <div class="empty"><div class="spinner"></div></div>
    </div>
  </div>

  <!-- Savings -->
  <div class="page" id="page-savings">
    <div class="page-header">
      <div class="page-title">Savings</div>
      <div class="page-sub">Token usage and output compression settings</div>
    </div>
    <div class="panel-row">
      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">Token Usage</span>
        </div>
        <div id="savings-detail">
          <div class="empty"><div class="spinner"></div></div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">Output Compression</span>
        </div>
        <p style="font-size:12.5px;color:var(--text2);line-height:1.6;margin-bottom:12px;">Controls how Claude formats its responses. Higher compression reduces output tokens.</p>
        <div class="comp-grid" id="comp-buttons">
          <button class="comp-btn" onclick="setCompression('off')">off</button>
          <button class="comp-btn" onclick="setCompression('lite')">lite</button>
          <button class="comp-btn" onclick="setCompression('standard')">standard</button>
          <button class="comp-btn" onclick="setCompression('max')">max</button>
        </div>
      </div>
    </div>
  </div>

</main>

<div class="toast" id="toast"></div>

<script>
var API = '';
var allFiles = [];
var currentLevel = 'standard';
var PAGES = ['overview','files','sessions','savings'];

// ── Navigation ──────────────────────────────────────────────────────────

function showPage(name) {
  PAGES.forEach(function(p) {
    document.getElementById('page-' + p).classList.toggle('active', p === name);
  });
  document.querySelectorAll('.nav-item').forEach(function(el, i) {
    el.classList.toggle('active', PAGES[i] === name);
  });
  if (name === 'files') loadFiles();
  if (name === 'sessions') loadSessions();
  if (name === 'savings') loadSavings();
}

// ── Toast ────────────────────────────────────────────────────────────────

function toast(msg) {
  var el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(el._t);
  el._t = setTimeout(function() { el.classList.remove('show'); }, 2800);
}

// ── Helpers ──────────────────────────────────────────────────────────────

function reltime(ts) {
  var diff = Math.floor(Date.now() / 1000 - ts);
  if (diff < 60) return 'just now';
  if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
  if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
  return Math.floor(diff / 86400) + 'd ago';
}

function fmt(n) { return Number(n).toLocaleString(); }

function icon(name) {
  var icons = {
    refresh: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23,4 23,10 17,10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>',
    trash:   '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3,6 5,6 21,6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>',
  };
  return icons[name] || '';
}

// ── Status (polling) ─────────────────────────────────────────────────────

async function loadStatus() {
  try {
    var r = await fetch(API + '/api/status');
    var d = await r.json();
    document.getElementById('nav-project').textContent = d.project || '';
    document.getElementById('stat-chunks').textContent  = fmt(d.chunks);
    document.getElementById('stat-files').textContent   = fmt(d.files);
    document.getElementById('stat-queries').textContent = fmt(d.queries);
    document.getElementById('stat-saved').textContent   = d.tokens_saved_pct + '%';
    document.getElementById('uninit-banner').style.display = d.initialized ? 'none' : 'flex';
    currentLevel = d.output_level;
    refreshCompButtons(d.output_level);
    loadOverviewPanels();
  } catch(e) {}
}

async function loadOverviewPanels() {
  // Health
  try {
    var r = await fetch(API + '/api/files');
    var files = await r.json();
    var ok      = files.filter(function(f){ return f.status==='ok'; }).length;
    var stale   = files.filter(function(f){ return f.status==='stale'; }).length;
    var missing = files.filter(function(f){ return f.status==='missing'; }).length;
    document.getElementById('nav-files-count').textContent = files.length;

    var rows = [['Up to date', ok, 'ok'], ['Stale', stale, 'stale'], ['Missing', missing, 'missing']];
    document.getElementById('health-rows').innerHTML = rows.map(function(row) {
      return '<div class="health-item">' +
        '<div class="health-label"><span class="health-dot ' + row[2] + '"></span>' + row[0] + '</div>' +
        '<span class="badge badge-num">' + row[1] + ' files</span>' +
        '</div>';
    }).join('');
  } catch(e) {}

  // Recent sessions
  try {
    var r2 = await fetch(API + '/api/sessions');
    var sessions = await r2.json();
    document.getElementById('nav-sessions-count').textContent = sessions.length;
    var el = document.getElementById('recent-sessions');
    if (!sessions.length) {
      el.innerHTML = '<div class="empty"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg><span class="empty-title">No sessions yet</span></div>';
      return;
    }
    el.innerHTML = sessions.slice(0, 5).map(function(s) {
      var isActive = !s.ended_at;
      var decs = (s.decisions || []).length;
      var areas = (s.code_areas || []).length;
      return '<div class="health-item">' +
        '<div>' +
        '<div style="font-size:13px;font-weight:600;color:var(--text)">' + (s.project || s.id) + '</div>' +
        '<div style="font-size:11.5px;color:var(--text2);margin-top:2px">' +
          decs + ' decisions &middot; ' + areas + ' code areas' +
          (s.started_at ? ' &middot; ' + reltime(s.started_at) : '') +
        '</div></div>' +
        '<span class="badge ' + (isActive ? 'badge-active' : 'badge-closed') + '">' + (isActive ? 'active' : 'closed') + '</span>' +
        '</div>';
    }).join('');
  } catch(e) {}
}

// ── Files ────────────────────────────────────────────────────────────────

async function loadFiles() {
  var el = document.getElementById('file-rows');
  el.innerHTML = '<div class="empty"><div class="spinner"></div></div>';
  try {
    var r = await fetch(API + '/api/files');
    allFiles = await r.json();
    renderFiles(allFiles);
  } catch(e) {
    el.innerHTML = '<div class="empty"><span class="empty-title">Failed to load files</span></div>';
  }
}

function renderFiles(files) {
  var el = document.getElementById('file-rows');
  if (!files.length) {
    el.innerHTML = '<div class="empty">' +
      '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14,2 14,8 20,8"/></svg>' +
      '<span class="empty-title">No files indexed yet</span>' +
      '<span class="empty-sub">Run <code style="font-family:var(--mono);font-size:11px">cce index</code> to get started</span>' +
      '</div>';
    return;
  }
  el.innerHTML = files.map(function(f) {
    return '<div class="table-row">' +
      '<div class="file-path" title="' + f.path + '">' + f.path + '</div>' +
      '<div class="chunk-count">' + f.chunks + '</div>' +
      '<div><span class="badge badge-' + f.status + '">' + f.status + '</span></div>' +
      '<div class="row-actions">' +
        '<button class="btn-icon" title="Reindex" onclick="reindexFile(' + JSON.stringify(f.path) + ')">' + icon('refresh') + '</button>' +
        '<button class="btn-icon del" title="Remove" onclick="deleteFile(' + JSON.stringify(f.path) + ')">' + icon('trash') + '</button>' +
      '</div>' +
    '</div>';
  }).join('');
}

function filterFiles(q) {
  q = q.toLowerCase();
  renderFiles(q ? allFiles.filter(function(f){ return f.path.toLowerCase().includes(q); }) : allFiles);
}

// ── Sessions ─────────────────────────────────────────────────────────────

async function loadSessions() {
  var el = document.getElementById('session-list');
  el.innerHTML = '<div class="empty"><div class="spinner"></div></div>';
  try {
    var r = await fetch(API + '/api/sessions');
    var sessions = await r.json();
    if (!sessions.length) {
      el.innerHTML = '<div class="empty"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg><span class="empty-title">No sessions recorded</span><span class="empty-sub">Sessions are captured automatically during Claude coding sessions</span></div>';
      return;
    }
    el.innerHTML = sessions.map(function(s, i) {
      var isActive = !s.ended_at;
      var decs = s.decisions || [];
      var areas = s.code_areas || [];
      return '<div class="session-card">' +
        '<div class="session-header" onclick="toggleSession(' + i + ')">' +
          '<div class="session-header-left">' +
            '<div class="session-name">' + (s.project || s.id) + '</div>' +
            '<div class="session-meta">' +
              '<span>' + decs.length + ' decisions</span>' +
              '<span class="session-meta-dot">&middot;</span>' +
              '<span>' + areas.length + ' code areas</span>' +
              (s.started_at ? '<span class="session-meta-dot">&middot;</span><span>' + reltime(s.started_at) + '</span>' : '') +
            '</div>' +
          '</div>' +
          '<span class="badge ' + (isActive ? 'badge-active' : 'badge-closed') + '">' + (isActive ? 'active' : 'closed') + '</span>' +
        '</div>' +
        (decs.length ?
          '<div class="session-body" id="sb-' + i + '">' +
            '<div class="decision-label">Decisions</div>' +
            decs.map(function(d){ return '<div class="decision-item">' + d.decision + '</div>'; }).join('') +
          '</div>'
        : '') +
      '</div>';
    }).join('');
  } catch(e) {
    el.innerHTML = '<div class="empty"><span class="empty-title">Failed to load sessions</span></div>';
  }
}

function toggleSession(i) {
  var el = document.getElementById('sb-' + i);
  if (el) el.classList.toggle('open');
}

// ── Savings ──────────────────────────────────────────────────────────────

async function loadSavings() {
  try {
    var r = await fetch(API + '/api/savings');
    var d = await r.json();
    var el = document.getElementById('savings-detail');
    var usedPct = d.baseline_tokens > 0 ? Math.round(d.served_tokens / d.baseline_tokens * 100) : 0;
    var savedPct = d.savings_pct || 0;
    el.innerHTML =
      '<div class="bar-group">' +
        '<div class="bar-meta"><span class="bar-label-text">With CCE</span><span class="bar-value-text" style="color:var(--accent)">' + fmt(d.served_tokens || 0) + '</span></div>' +
        '<div class="bar-track"><div class="bar-fill" style="background:var(--accent);width:' + usedPct + '%"></div></div>' +
      '</div>' +
      '<div class="bar-group">' +
        '<div class="bar-meta"><span class="bar-label-text">Without CCE</span><span class="bar-value-text" style="color:var(--text2)">' + fmt(d.baseline_tokens || 0) + '</span></div>' +
        '<div class="bar-track"><div class="bar-fill" style="background:var(--surface3);width:100%"></div></div>' +
      '</div>' +
      '<div class="savings-total">' +
        '<div>' +
          '<div class="savings-total-label">Total saved</div>' +
          '<div style="font-size:11.5px;color:var(--text3);margin-top:1px">' + fmt(d.queries||0) + ' queries</div>' +
        '</div>' +
        '<div style="text-align:right">' +
          '<span class="savings-total-value">' + fmt(d.tokens_saved || 0) + '</span>' +
          '<span class="savings-total-pct">(' + savedPct + '%)</span>' +
        '</div>' +
      '</div>';
  } catch(e) {}
  refreshCompButtons(currentLevel);
}

function refreshCompButtons(level) {
  document.querySelectorAll('.comp-btn').forEach(function(btn) {
    btn.classList.toggle('active', btn.textContent.trim() === level);
  });
}

// ── Actions ──────────────────────────────────────────────────────────────

async function doReindex(full) {
  var id = full ? 'btn-reindex-full' : 'btn-reindex-changed';
  var btn = document.getElementById(id);
  var orig = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<div class="spinner"></div> Indexing…';
  try {
    var r = await fetch(API + '/api/reindex', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({full: full})
    });
    var d = await r.json();
    if (d.errors && d.errors.length) toast('Error: ' + d.errors[0]);
    else toast('Indexed ' + d.indexed_files.length + ' files (' + fmt(d.total_chunks) + ' chunks)');
    loadStatus();
  } catch(e) { toast('Reindex failed'); }
  finally { btn.disabled = false; btn.innerHTML = orig; }
}

async function reindexFile(path) {
  try {
    await fetch(API + '/api/reindex/' + encodeURIComponent(path), {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    toast('Reindexed ' + path);
    loadFiles(); loadStatus();
  } catch(e) { toast('Failed'); }
}

async function deleteFile(path) {
  if (!confirm('Remove "' + path + '" from the index?')) return;
  try {
    await fetch(API + '/api/files/' + encodeURIComponent(path), {method:'DELETE'});
    toast('Removed ' + path);
    loadFiles(); loadStatus();
  } catch(e) { toast('Failed'); }
}

async function doClear() {
  if (!confirm('Clear the entire index? This cannot be undone.')) return;
  try {
    await fetch(API + '/api/clear', {method:'POST'});
    toast('Index cleared');
    loadStatus(); loadFiles();
  } catch(e) { toast('Failed'); }
}

async function doExport() { window.location.href = API + '/api/export'; }

async function setCompression(level) {
  try {
    await fetch(API + '/api/compression', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({level: level})
    });
    currentLevel = level;
    refreshCompButtons(level);
    toast('Compression set to ' + level);
  } catch(e) { toast('Failed'); }
}

// ── Boot ─────────────────────────────────────────────────────────────────

loadStatus();
setInterval(loadStatus, 5000);
</script>
</body>
</html>"""
