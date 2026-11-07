/**
 * 文件名: app.js
 * 功能描述: 桌面端单页应用入口。负责登录态恢复、应用骨架渲染、角色化路由、
 *          编译器探针状态展示与全局 AI 助教挂载。
 */

import { api, getToken, setToken } from './api/client.js';
import { state, setUser, clearUser, setStatus } from './store.js';
import { currentPath, navigate } from './router.js';
import { escapeHtml, initials } from './components/base/dom.js';
import { toast } from './components/base/toast.js';
import { mountAssistant } from './components/assistant/assistant.js';

import { render as renderAuth } from './views/auth/auth.js';
import { render as renderClasses } from './views/common/classes.js';
import { render as renderTeacherWorkbench } from './views/teacher/workbench.js';
import { render as renderTeacherDashboard } from './views/teacher/dashboard.js';
import { render as renderStudentAssignments } from './views/student/assignments.js';
import { render as renderStudentWorkbench } from './views/student/workbench.js';
import { render as renderStudentTraining } from './views/student/training.js';

const app = document.getElementById('app');

const ICONS = {
  grid: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.4"/><rect x="14" y="3" width="7" height="7" rx="1.4"/><rect x="3" y="14" width="7" height="7" rx="1.4"/><rect x="14" y="14" width="7" height="7" rx="1.4"/></svg>',
  code: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M8 9l-3 3 3 3"/><path d="M16 9l3 3-3 3"/><path d="M13 6l-2 12"/></svg>',
  chart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20V10"/><path d="M10 20V4"/><path d="M16 20v-7"/><path d="M22 20H2"/></svg>',
  book: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21.5z"/><path d="M4 5.5v16"/></svg>',
  spark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z"/></svg>',
};

let routeSeq = 0;
let shellReady = false;

const NAV = {
  teacher: [
    { path: '/teacher/classes', label: '班级大厅', icon: ICONS.grid },
    { path: '/teacher/workbench', label: '作业工作台', icon: ICONS.code },
    { path: '/teacher/dashboard', label: '学情大屏', icon: ICONS.chart },
  ],
  student: [
    { path: '/student/assignments', label: '我的作业', icon: ICONS.book },
    { path: '/student/training', label: '强化训练', icon: ICONS.spark },
    { path: '/student/classes', label: '班级大厅', icon: ICONS.grid },
  ],
};

function homePath() {
  return state.user?.role === 'teacher' ? '/teacher/classes' : '/student/assignments';
}

function renderShell() {
  if (shellReady && document.getElementById('app-shell')) return;
  const user = state.user;

  app.innerHTML = `
    <div class="app-shell" id="app-shell">
      <header class="topbar">
        <button class="btn btn-ghost btn-icon menu-toggle" type="button" id="menu-toggle" aria-label="切换导航">☰</button>
        <div class="brand">
          <div class="brand-mark">&lt;/&gt;</div>
          <div>
            <div class="brand-name">CourseJudge</div>
            <span class="brand-sub">Intelligent Code Judge</span>
          </div>
        </div>
        <div class="topbar-spacer"></div>
        <div class="compiler-pill" id="compiler-pill" title="编译器智能双模探针状态">
          <span class="status-dot" id="compiler-dot"></span>
          <span class="compiler-label" id="compiler-label">探针检测中…</span>
        </div>
        <div class="user-chip">
          <div class="avatar">${escapeHtml(initials(user?.real_name || user?.username))}</div>
          <div class="user-meta">
            <span class="user-name">${escapeHtml(user?.real_name || user?.username || '')}</span>
            <span class="user-role">${user?.role === 'teacher' ? '教师' : '学生'}</span>
          </div>
        </div>
        <button class="btn btn-ghost btn-sm" type="button" id="logout">退出</button>
      </header>

      <aside class="sidebar" id="sidebar">
        <div class="sidebar-label">工作区</div>
        <nav id="nav-list"></nav>
        <div class="sidebar-footer">
          <div>CourseJudge v1.0.0</div>
          <div style="margin-top:4px">AI 判题 · 学情诊断 · 强化训练</div>
        </div>
      </aside>

      <main class="main"><div id="view-root"></div></main>

      <footer class="statusbar">
        <span class="status-item"><span class="status-dot" id="status-dot"></span><strong id="status-compiler">编译器检测中</strong></span>
        <span class="status-item" id="status-path"></span>
        <span class="spacer"></span>
        <span class="status-item">FastAPI · SQLite</span>
        <span class="status-item" id="status-version">v1.0.0</span>
      </footer>
    </div>
  `;

  const navList = document.getElementById('nav-list');
  (NAV[user?.role] || NAV.student).forEach((item) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'nav-item';
    button.dataset.path = item.path;
    button.innerHTML = `<span class="nav-icon">${item.icon}</span><span>${item.label}</span>`;
    button.addEventListener('click', () => {
      navigate(item.path);
      document.getElementById('app-shell')?.classList.remove('sidebar-open');
    });
    navList.appendChild(button);
  });

  document.getElementById('menu-toggle').addEventListener('click', () => {
    document.getElementById('app-shell')?.classList.toggle('sidebar-open');
  });
  document.getElementById('logout').addEventListener('click', logout);

  mountAssistant();
  shellReady = true;
  updateCompilerStatus();
  updateActiveNav(currentPath());
}

function updateActiveNav(path) {
  document.querySelectorAll('.nav-item').forEach((item) => {
    const base = item.dataset.path;
    item.classList.toggle('active', path === base || path.startsWith(`${base}/`));
  });
}

function showAuth() {
  shellReady = false;
  document.getElementById('assistant-fab')?.remove();
  document.querySelector('.assistant-panel')?.remove();
  app.innerHTML = '';
  renderAuth(app);
}

function logout() {
  setToken('');
  clearUser();
  showAuth();
  navigate('/login');
  toast('已退出登录', 'info');
}

async function fetchStatus() {
  try {
    const status = await api.system.status();
    setStatus(status);
    updateCompilerStatus();
  } catch (err) {
    setStatus(null);
    updateCompilerStatus(true);
  }
}

function updateCompilerStatus(failed = false) {
  const probe = state.status?.compiler_probe;
  const ready = Boolean(probe?.ready) && !failed;
  const dot = document.getElementById('compiler-dot');
  const label = document.getElementById('compiler-label');
  const statusDot = document.getElementById('status-dot');
  const statusCompiler = document.getElementById('status-compiler');
  const statusPath = document.getElementById('status-path');
  const version = document.getElementById('status-version');

  if (version) version.textContent = state.status?.version || 'v1.0.0';

  if (!dot) return;
  dot.className = `status-dot ${ready ? 'ok' : 'bad'}`;
  if (statusDot) statusDot.className = `status-dot ${ready ? 'ok' : 'bad'}`;

  const mode = probe?.mode || 'unknown';
  const compilerPath = probe?.resolved_compiler || '';
  const modeLabel = mode === 'builtin' ? '内置便携编译器' : mode === 'system' ? '系统 g++' : '自动探针';

  if (label) label.textContent = ready ? `${modeLabel} 已就绪` : '编译器未就绪';
  if (statusCompiler) statusCompiler.textContent = ready ? `${modeLabel} 已就绪` : '编译器未就绪';
  if (statusPath) statusPath.textContent = compilerPath || '未检测到可用 g++';
}

function notFoundView(root) {
  root.innerHTML = `
    <div class="page"><div class="empty-state">
      <div class="empty-icon">?</div>
      <h3>页面不存在</h3>
      <p class="muted small">请从左侧导航进入工作区。</p>
      <button class="btn btn-primary" type="button" id="go-home">返回首页</button>
    </div></div>`;
  root.querySelector('#go-home').addEventListener('click', () => navigate(homePath()));
}

function resolveRoute(path) {
  let matched;

  if (path === '/' || path === '/login') {
    return { redirect: homePath() };
  }

  if ((matched = path.match(/^\/teacher\/classes$/))) {
    return { render: renderClasses, role: 'teacher', nav: '/teacher/classes' };
  }
  if ((matched = path.match(/^\/student\/classes$/))) {
    return { render: renderClasses, role: 'student', nav: '/student/classes' };
  }
  if ((matched = path.match(/^\/teacher\/workbench(?:\/(\d+))?$/))) {
    return { render: renderTeacherWorkbench, role: 'teacher', nav: '/teacher/workbench', params: { classId: matched[1] } };
  }
  if ((matched = path.match(/^\/teacher\/dashboard(?:\/(\d+))?$/))) {
    return { render: renderTeacherDashboard, role: 'teacher', nav: '/teacher/dashboard', params: { classId: matched[1] } };
  }
  if ((matched = path.match(/^\/student\/assignments(?:\/(\d+))?$/))) {
    return { render: renderStudentAssignments, role: 'student', nav: '/student/assignments', params: { classId: matched[1] } };
  }
  if ((matched = path.match(/^\/student\/workbench\/(\d+)\/(\d+)$/))) {
    return { render: renderStudentWorkbench, role: 'student', nav: '/student/assignments', params: { assignmentId: matched[1], problemId: matched[2] } };
  }
  if ((matched = path.match(/^\/student\/training$/))) {
    return { render: renderStudentTraining, role: 'student', nav: '/student/training' };
  }

  return { notFound: true };
}

async function handleRoute() {
  if (!state.user) {
    if (currentPath() !== '/login') navigate('/login');
    showAuth();
    return;
  }

  const path = currentPath();
  const route = resolveRoute(path);

  if (route.redirect) {
    navigate(route.redirect);
    return;
  }

  if (route.role && route.role !== state.user.role) {
    navigate(homePath());
    return;
  }

  renderShell();
  updateActiveNav(route.nav || path);

  const viewRoot = document.getElementById('view-root');
  if (!viewRoot) return;

  if (typeof state.cleanup === 'function') {
    try { state.cleanup(); } catch (err) { console.warn(err); }
    state.cleanup = null;
  }

  const seq = ++routeSeq;
  viewRoot.innerHTML = '<div class="empty-state" style="min-height:60vh"><span class="spinner spinner-lg"></span><span>加载中…</span></div>';

  try {
    if (route.notFound) {
      notFoundView(viewRoot);
      return;
    }
    const cleanup = await route.render(viewRoot, route.params || {});
    if (seq !== routeSeq) {
      if (typeof cleanup === 'function') cleanup();
      return;
    }
    state.cleanup = typeof cleanup === 'function' ? cleanup : null;
  } catch (err) {
    console.error(err);
    if (seq === routeSeq) {
      viewRoot.innerHTML = `<div class="page"><div class="empty-state"><div class="empty-icon text-danger">!</div><h3>页面加载失败</h3><p class="muted small">${escapeHtml(err.message || '未知错误')}</p></div></div>`;
      toast(err.message || '页面加载失败', 'error');
    }
  }
}

window.addEventListener('cj:authenticated', (event) => {
  setUser(event.detail);
  shellReady = false;
  renderShell();
  fetchStatus();
  navigate(homePath());
  handleRoute();
});

window.addEventListener('cj:unauthorized', () => {
  setToken('');
  clearUser();
  showAuth();
  navigate('/login');
  toast('登录已过期，请重新登录', 'warning');
});

window.addEventListener('hashchange', handleRoute);
window.addEventListener('resize', () => {
  // Monaco 使用 automaticLayout；这里只负责关闭移动端侧栏
  if (window.innerWidth > 980) {
    document.getElementById('app-shell')?.classList.remove('sidebar-open');
  }
});

async function boot() {
  if (getToken()) {
    try {
      const user = await api.auth.me();
      setUser(user);
    } catch (err) {
      setToken('');
      clearUser();
    }
  }

  if (!state.user) {
    showAuth();
    if (currentPath() !== '/login') navigate('/login');
    return;
  }

  renderShell();
  fetchStatus();
  await handleRoute();
}

boot();