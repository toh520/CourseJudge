/**
 * 文件名: assignments.js
 * 功能描述: 学生“我的作业”大厅。按班级展示练习/考试、时间状态、倒计时与个人最佳得分，
 *          选择题目后进入 Monaco 编程工作台。
 */

import { api } from '../../api/client.js';
import { navigate } from '../../router.js';
import { el, escapeHtml, fmtDate, countdown } from '../../components/base/dom.js';
import { openModal } from '../../components/base/modal.js';
import { typeBadge, timeStatusBadge, scoreText } from '../../components/base/badges.js';
import { toast } from '../../components/base/toast.js';

/**
 * 渲染学生作业大厅
 * @param {HTMLElement} root
 * @param {{classId?:string}} params
 */
export async function render(root, params = {}) {
  const filterClassId = Number(params.classId) || null;

  root.innerHTML = `
    <div class="page">
      <header class="page-header">
        <div class="page-heading">
          <div class="page-eyebrow">Student Console</div>
          <h1 class="page-title">我的作业</h1>
          <p class="page-desc">查看所属班级的练习与考试，进入编程工作台完成自测与交卷。</p>
        </div>
        <div class="page-actions">
          <button class="btn" type="button" id="go-classes">班级大厅</button>
          <button class="btn" type="button" id="go-training">强化训练题本</button>
        </div>
      </header>
      <div id="assignment-content">
        <div class="empty-state"><span class="spinner spinner-lg"></span><span>正在加载作业…</span></div>
      </div>
    </div>
  `;

  root.querySelector('#go-classes').addEventListener('click', () => navigate('/student/classes'));
  root.querySelector('#go-training').addEventListener('click', () => navigate('/student/training'));

  const content = root.querySelector('#assignment-content');

  let classes = [];
  try {
    classes = (await api.classes.my())?.classes || [];
  } catch (err) {
    content.innerHTML = `<div class="empty-state"><div class="empty-icon text-danger">!</div><h3>加载班级失败</h3><p class="muted small">${escapeHtml(err.message)}</p></div>`;
    return;
  }

  if (!classes.length) {
    content.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⌁</div>
        <h3>还没有加入班级</h3>
        <p class="muted small">请向教师索取 6 位邀请码，加入班级后即可看到作业。</p>
        <button class="btn btn-primary" type="button" id="join-now">去加入班级</button>
      </div>`;
    content.querySelector('#join-now').addEventListener('click', () => navigate('/student/classes'));
    return;
  }

  if (filterClassId) {
    classes = classes.filter((item) => item.id === filterClassId);
  }

  const sections = [];
  for (const clazz of classes) {
    try {
      const data = await api.assignments.byClass(clazz.id);
      sections.push({ clazz, assignments: data?.assignments || [] });
    } catch (err) {
      sections.push({ clazz, assignments: [], error: err.message });
    }
  }

  const total = sections.reduce((sum, section) => sum + section.assignments.length, 0);
  if (!total) {
    content.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">◫</div>
        <h3>暂时没有作业</h3>
        <p class="muted small">教师发布作业后会在这里显示。</p>
        <button class="btn" type="button" id="reload">刷新</button>
      </div>`;
    content.querySelector('#reload').addEventListener('click', () => render(root, params));
    return;
  }

  content.innerHTML = '';
  sections.forEach(({ clazz, assignments, error }) => {
    const section = el('section', { class: 'section', style: 'margin-top:0;margin-bottom:26px' },
      el('div', { class: 'section-title' },
        el('span', {}, clazz.name),
        el('span', { class: 'badge badge-muted' }, `${assignments.length} 项`),
      ),
    );

    if (error) {
      section.appendChild(el('div', { class: 'small text-danger' }, error));
      content.appendChild(section);
      return;
    }
    if (!assignments.length) {
      section.appendChild(el('div', { class: 'small dim' }, '该班级暂无作业'));
      content.appendChild(section);
      return;
    }

    const grid = el('div', { class: 'assignment-grid' });
    assignments
      .slice()
      .sort((a, b) => {
        const order = { ongoing: 0, upcoming: 1, ended: 2 };
        const diff = (order[a.time_status] ?? 3) - (order[b.time_status] ?? 3);
        if (diff !== 0) return diff;
        return new Date(b.start_time || 0) - new Date(a.start_time || 0);
      })
      .forEach((assignment) => grid.appendChild(assignmentCard(assignment)));
    section.appendChild(grid);
    content.appendChild(section);
  });

  function assignmentCard(assignment) {
    const remain = countdown(assignment.end_time);
    const submitted = Number(assignment.my_submission_count || 0) > 0;
    const examLocked = assignment.type === 'exam' && submitted;

    const card = el('article', { class: 'assignment-card' });
    card.innerHTML = `
      <div class="assignment-card-head">
        <div>
          <div class="flex items-center gap-8" style="margin-bottom:6px">
            ${typeBadge(assignment.type)}
            ${timeStatusBadge(assignment.time_status)}
            ${examLocked ? '<span class="badge badge-warning">已交卷</span>' : ''}
          </div>
          <div class="assignment-title">${escapeHtml(assignment.title)}</div>
        </div>
      </div>
      <div class="meta-row">
        <span>${assignment.problem_count} 道题</span>
        <span class="inline-dot"></span>
        <span>${fmtDate(assignment.start_time)} → ${fmtDate(assignment.end_time)}</span>
      </div>
      <div class="countdown ${remain.ended ? 'ended' : ''}">${remain.text}</div>
      <div class="assignment-foot">
        <div class="assignment-score">最佳得分 <strong>${scoreText(assignment.my_best_score ?? 0)}</strong></div>
        <button class="btn btn-primary btn-sm" type="button">${examLocked ? '查看结果' : '开始作答'}</button>
      </div>
    `;
    card.querySelector('button').addEventListener('click', () => openProblemPicker(assignment));
    return card;
  }

  async function openProblemPicker(assignment) {
    const modal = openModal({
      title: assignment.title,
      content: '<div class="loading-line"><span class="spinner"></span>正在加载题目…</div>',
      wide: true,
    });
    try {
      const data = await api.assignments.problems(assignment.id);
      const problems = data?.problems || [];
      if (!problems.length) {
        modal.body.innerHTML = '<div class="empty-state"><div class="empty-icon">◫</div><p>该作业暂未配置题目</p></div>';
        return;
      }
      modal.body.innerHTML = `
        <div class="flex items-center gap-8" style="flex-wrap:wrap;margin-bottom:14px">
          ${typeBadge(assignment.type)} ${timeStatusBadge(assignment.time_status)}
          <span class="small dim">${escapeHtml(remainText(assignment.end_time))}</span>
        </div>
        <div class="draft-list">
          ${problems.map((problem, index) => `
            <div class="draft-item">
              <div style="min-width:0">
                <strong>${index + 1}. ${escapeHtml(problem.title)}</strong>
                <div class="small dim">${escapeHtml(problem.knowledge_tag || '未标注知识点')} · ${problem.time_limit_ms}ms / ${problem.memory_limit_mb}MB</div>
              </div>
              <button class="btn btn-primary btn-sm" type="button" data-problem="${problem.id}">进入</button>
            </div>
          `).join('')}
        </div>
      `;
      modal.body.querySelectorAll('button[data-problem]').forEach((button) => {
        button.addEventListener('click', () => {
          modal.close();
          navigate(`/student/workbench/${assignment.id}/${button.dataset.problem}`);
        });
      });
    } catch (err) {
      modal.body.innerHTML = `<div class="text-danger small">${escapeHtml(err.message)}</div>`;
      toast(err.message, 'error');
    }
  }

  function remainText(endTime) {
    return countdown(endTime).text;
  }
}