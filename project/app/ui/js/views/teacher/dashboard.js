/**
 * 文件名: dashboard.js
 * 功能描述: 教师端班级学情大屏。展示应交/实交、平均分、及格率、分数段分布、
 *          各题通过率与班级薄弱知识点 Top。
 */

import { api } from '../../api/client.js';
import { navigate } from '../../router.js';
import { escapeHtml, num } from '../../components/base/dom.js';
import { toast } from '../../components/base/toast.js';
import {
  disposeCharts,
  renderProblemRates,
  renderScoreBands,
  renderWeakTags,
  resizeCharts,
} from '../../components/media/charts.js';

/**
 * 渲染学情大屏
 * @param {HTMLElement} root
 * @param {{classId?:string}} params
 */
export async function render(root, params = {}) {
  let classes = [];
  try {
    classes = (await api.classes.my())?.classes || [];
  } catch (err) {
    root.innerHTML = `<div class="page"><div class="empty-state"><div class="empty-icon text-danger">!</div><h3>加载失败</h3><p class="muted small">${escapeHtml(err.message)}</p></div></div>`;
    return;
  }

  if (!classes.length) {
    root.innerHTML = `
      <div class="page"><div class="empty-state">
        <div class="empty-icon">◎</div><h3>暂无可分析的班级</h3>
        <p class="muted small">请先创建班级并发布作业。</p>
        <button class="btn btn-primary" type="button" id="go-classes">前往班级大厅</button>
      </div></div>`;
    root.querySelector('#go-classes').addEventListener('click', () => navigate('/teacher/classes'));
    return;
  }

  const requestedId = Number(params.classId);
  const activeClass = classes.find((item) => item.id === requestedId) || classes[0];

  root.innerHTML = `
    <div class="page">
      <header class="page-header">
        <div class="page-heading">
          <h1 class="page-title">班级学情大屏</h1>
          <p class="page-desc">聚合应交/实交、成绩分布、题目通过率与薄弱知识点，辅助针对性讲评。</p>
        </div>
        <div class="page-actions">
          <select class="select" id="dash-class" style="width:210px">
            ${classes.map((item) => `<option value="${item.id}" ${item.id === activeClass.id ? 'selected' : ''}>${escapeHtml(item.name)}</option>`).join('')}
          </select>
          <select class="select" id="dash-assignment" style="width:230px">
            <option value="">加载作业中…</option>
          </select>
          <button class="btn" type="button" id="dash-refresh">刷新</button>
        </div>
      </header>

      <div id="dash-content">
        <div class="empty-state"><span class="spinner spinner-lg"></span><span>正在加载学情数据…</span></div>
      </div>
    </div>
  `;

  const classSelect = root.querySelector('#dash-class');
  const assignmentSelect = root.querySelector('#dash-assignment');
  const content = root.querySelector('#dash-content');

  classSelect.addEventListener('change', () => navigate(`/teacher/dashboard/${classSelect.value}`));
  assignmentSelect.addEventListener('change', () => loadDashboard(Number(assignmentSelect.value)));
  root.querySelector('#dash-refresh').addEventListener('click', () => loadDashboard(Number(assignmentSelect.value)));

  let assignments = [];

  async function loadAssignments() {
    try {
      const data = await api.assignments.byClass(activeClass.id);
      assignments = data?.assignments || [];
      if (!assignments.length) {
        assignmentSelect.innerHTML = '<option value="">暂无作业</option>';
        content.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">◎</div>
            <h3>该班级还没有作业</h3>
            <p class="muted small">发布作业并等待学生提交后，这里会呈现完整学情。</p>
            <button class="btn btn-primary" type="button" id="go-workbench">去发布作业</button>
          </div>`;
        content.querySelector('#go-workbench').addEventListener('click', () => navigate(`/teacher/workbench/${activeClass.id}`));
        return;
      }
      assignmentSelect.innerHTML = assignments.map((item) => `
        <option value="${item.id}">${escapeHtml(item.title)} · ${item.type === 'exam' ? '考试' : '练习'}</option>
      `).join('');
      await loadDashboard(assignments[0].id);
    } catch (err) {
      content.innerHTML = `<div class="empty-state"><div class="empty-icon text-danger">!</div><h3>加载作业失败</h3><p class="muted small">${escapeHtml(err.message)}</p></div>`;
    }
  }

  async function loadDashboard(assignmentId) {
    if (!assignmentId) return;
    disposeCharts(content);
    content.innerHTML = '<div class="empty-state"><span class="spinner spinner-lg"></span><span>正在聚合学情数据…</span></div>';
    try {
      const dash = await api.assignments.dashboard(assignmentId);
      renderDashboard(dash);
    } catch (err) {
      content.innerHTML = `<div class="empty-state"><div class="empty-icon text-danger">!</div><h3>加载学情失败</h3><p class="muted small">${escapeHtml(err.message)}</p></div>`;
      toast(err.message, 'error');
    }
  }

  function renderDashboard(dash) {
    const bands = dash.score_bands || [];
    const problems = dash.problem_stats || [];
    const weakTags = dash.weak_knowledge_top || [];
    const maxBand = Math.max(1, ...bands.map((item) => item.count));

    content.innerHTML = `
      <div class="stat-grid">
        <div class="stat-tile">
          <div class="stat-label">应交人数</div>
          <div class="stat-value">${num(dash.expected_student_count)}<small> 人</small></div>
          <div class="stat-hint">班级名册成员</div>
        </div>
        <div class="stat-tile">
          <div class="stat-label">实交人数</div>
          <div class="stat-value">${num(dash.submitted_student_count)}<small> 人</small></div>
          <div class="stat-hint">${dash.expected_student_count ? Math.round((dash.submitted_student_count / dash.expected_student_count) * 100) : 0}% 交卷率</div>
        </div>
        <div class="stat-tile">
          <div class="stat-label">平均分</div>
          <div class="stat-value">${num(dash.average_score)}<small> 分</small></div>
          <div class="stat-hint">按每生每题最佳得分计算</div>
        </div>
        <div class="stat-tile">
          <div class="stat-label">及格率</div>
          <div class="stat-value">${num(dash.pass_rate)}<small> %</small></div>
          <div class="stat-hint">及格线 ${dash.pass_threshold ?? 60} 分</div>
        </div>
      </div>

      <div class="dashboard-grid" style="margin-top:16px">
        <div style="display:grid;gap:16px">
          <div class="chart-card">
            <div class="chart-card-head">
              <div class="chart-card-title">分数段分布</div>
              <span class="small dim">最高 ${maxBand} 人</span>
            </div>
            <div class="chart-box" id="chart-bands"></div>
          </div>
          <div class="chart-card">
            <div class="chart-card-head">
              <div class="chart-card-title">各题通过率</div>
              <span class="small dim">按学生去重</span>
            </div>
            <div class="chart-box" id="chart-problems"></div>
          </div>
        </div>
        <div style="display:grid;gap:16px">
          <div class="chart-card">
            <div class="chart-card-head">
              <div class="chart-card-title">薄弱知识点 Top</div>
              <span class="small dim">失分率</span>
            </div>
            <div class="chart-box" id="chart-weak"></div>
          </div>
          <div class="chart-card">
            <div class="chart-card-head">
              <div class="chart-card-title">薄弱点明细</div>
              <span class="small dim">${weakTags.length} 项</span>
            </div>
            <div class="weak-list" id="weak-list"></div>
          </div>
        </div>
      </div>

      <div class="small dim" style="margin-top:14px">
        ${escapeHtml(dash.assignment_title || '')} · ${dash.assignment_type === 'exam' ? '考试' : '练习'} ·
        数据更新时间 ${new Date().toLocaleTimeString('zh-CN')}
      </div>
    `;

    renderScoreBands(content.querySelector('#chart-bands'), bands);
    renderProblemRates(content.querySelector('#chart-problems'), problems);
    renderWeakTags(content.querySelector('#chart-weak'), weakTags);

    const weakList = content.querySelector('#weak-list');
    if (!weakTags.length) {
      weakList.innerHTML = '<div class="small dim">暂无可统计的薄弱知识点</div>';
    } else {
      weakList.innerHTML = weakTags.map((item) => `
        <div class="weak-item">
          <div class="weak-item-head">
            <span class="weak-tag">${escapeHtml(item.tag)}</span>
            <span class="weak-rate">${item.fail_rate}%</span>
          </div>
          <div class="progress danger"><span style="width:${Math.min(100, item.fail_rate)}%"></span></div>
          <div class="weak-meta" style="margin-top:6px">
            <span>${item.failed_students}/${item.total_students} 名学生失分</span>
            <span>Top ${weakTags.indexOf(item) + 1}</span>
          </div>
        </div>
      `).join('');
    }
  }

  const onResize = () => resizeCharts(content);
  window.addEventListener('resize', onResize);

  await loadAssignments();

  return () => {
    window.removeEventListener('resize', onResize);
    disposeCharts(content);
  };
}