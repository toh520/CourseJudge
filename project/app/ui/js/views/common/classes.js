/**
 * 文件名: classes.js
 * 功能描述: 班级大厅视图。教师创建班级、查看邀请码与学生名册；学生通过邀请码加入班级。
 */

import { api } from '../../api/client.js';
import { state } from '../../store.js';
import { navigate } from '../../router.js';
import { el, escapeHtml, initials } from '../../components/base/dom.js';
import { openModal } from '../../components/base/modal.js';
import { toast } from '../../components/base/toast.js';

/**
 * 渲染班级大厅
 * @param {HTMLElement} root
 */
export async function render(root) {
  const isTeacher = state.user?.role === 'teacher';

  root.innerHTML = `
    <div class="page">
      <header class="page-header">
        <div class="page-heading">
          <h1 class="page-title">班级大厅</h1>
          <p class="page-desc">${isTeacher ? '创建班级、分发邀请码，并进入作业编排与学情分析。' : '通过教师提供的 6 位邀请码加入班级，开始完成作业。'}</p>
        </div>
        <div class="page-actions" id="class-actions"></div>
      </header>
      <div id="class-list"></div>
    </div>
  `;

  const actions = root.querySelector('#class-actions');
  const list = root.querySelector('#class-list');

  if (isTeacher) {
    actions.appendChild(el('button', { class: 'btn btn-primary', type: 'button', onclick: () => openCreateModal(load) }, '＋ 创建班级'));
  } else {
    actions.appendChild(el('button', { class: 'btn btn-primary', type: 'button', onclick: () => openJoinModal(load) }, '＋ 加入班级'));
  }

  async function load() {
    list.innerHTML = '<div class="empty-state"><span class="spinner spinner-lg"></span><span>正在加载班级…</span></div>';
    try {
      const data = await api.classes.my();
      const classes = data?.classes || [];
      if (!classes.length) {
        list.innerHTML = '';
        list.appendChild(el('div', { class: 'empty-state' },
          el('div', { class: 'empty-icon' }, isTeacher ? '◫' : '⌁'),
          el('h3', {}, isTeacher ? '还没有创建班级' : '还没有加入班级'),
          el('p', { class: 'muted small' }, isTeacher ? '创建第一个班级后，学生即可凭邀请码加入。' : '向教师索取 6 位邀请码，加入后即可看到作业。'),
          el('button', {
            class: 'btn btn-primary', type: 'button',
            onclick: () => (isTeacher ? openCreateModal(load) : openJoinModal(load)),
          }, isTeacher ? '创建班级' : '加入班级'),
        ));
        return;
      }
      renderClasses(list, classes, load);
    } catch (err) {
      list.innerHTML = '';
      list.appendChild(emptyError(err.message, load));
    }
  }

  await load();
}

function renderClasses(container, classes, reload) {
  container.innerHTML = '';
  const grid = el('div', { class: 'class-grid' });
  const isTeacher = state.user?.role === 'teacher';

  classes.forEach((clazz) => {
    const card = el('article', { class: 'class-card' },
      el('div', { class: 'class-card-top' },
        el('div', {},
          el('div', { class: 'class-name' }, clazz.name),
          el('div', { class: 'class-meta' },
            el('span', {}, `${clazz.student_count ?? 0} 名学生`),
            clazz.teacher_name ? el('span', {}, `授课教师 ${clazz.teacher_name}`) : null,
          ),
        ),
        el('span', { class: 'badge badge-accent' }, isTeacher ? '教师' : '已加入'),
      ),
      clazz.invite_code
        ? el('button', {
            class: 'invite-code', type: 'button', title: '点击复制邀请码',
            onclick: () => copyInvite(clazz.invite_code),
          }, '邀请码 ', clazz.invite_code)
        : el('div', { class: 'muted small' }, '已加入该班级'),
      el('div', { class: 'class-actions' },
        isTeacher ? el('button', { class: 'btn btn-sm', type: 'button', onclick: () => openRoster(clazz) }, '查看名册') : null,
        isTeacher ? el('button', { class: 'btn btn-primary btn-sm', type: 'button', onclick: () => navigate(`/teacher/workbench/${clazz.id}`) }, '作业工作台') : null,
        isTeacher ? el('button', { class: 'btn btn-sm', type: 'button', onclick: () => navigate(`/teacher/dashboard/${clazz.id}`) }, '学情大屏') : null,
        !isTeacher ? el('button', { class: 'btn btn-primary btn-sm', type: 'button', onclick: () => navigate(`/student/assignments/${clazz.id}`) }, '查看作业') : null,
      ),
    );
    grid.appendChild(card);
  });

  container.appendChild(grid);
  container.appendChild(el('div', { class: 'small dim', style: 'margin-top:12px' },
    isTeacher ? '提示：学生凭邀请码加入后，可在“学情大屏”查看班级整体表现。' : '提示：练习模式可多次提交，考试模式仅允许交卷一次。'));
}

function openCreateModal(onDone) {
  const modal = openModal({
    title: '创建班级',
    content: `
      <div class="field">
        <label for="class-name">班级名称</label>
        <input class="input" id="class-name" placeholder="例如：2024级计算机1班程序设计" maxlength="100">
      </div>
      <p class="small muted" style="margin-top:10px">创建后将自动生成 6 位唯一邀请码，学生可凭邀请码加入。</p>
    `,
    actions: [
      { label: '取消' },
      {
        label: '创建班级',
        kind: 'primary',
        onClick: async () => {
          const input = modal.body.querySelector('#class-name');
          const name = input.value.trim();
          if (!name) {
            input.focus();
            toast('请输入班级名称', 'warning');
            return false;
          }
          try {
            const created = await api.classes.create(name);
            toast(`班级已创建，邀请码：${created.invite_code}`, 'success', 5000);
            await onDone();
            return true;
          } catch (err) {
            toast(err.message, 'error');
            return false;
          }
        },
      },
    ],
  });
  window.setTimeout(() => modal.body.querySelector('#class-name')?.focus(), 50);
}

function openJoinModal(onDone) {
  const modal = openModal({
    title: '加入班级',
    content: `
      <div class="field">
        <label for="invite-code">6 位班级邀请码</label>
        <input class="input mono" id="invite-code" placeholder="例如：A7K9Q2" maxlength="10" style="letter-spacing:.28em;text-transform:uppercase">
      </div>
      <p class="small muted" style="margin-top:10px">邀请码由任课教师提供，不区分大小写。</p>
    `,
    actions: [
      { label: '取消' },
      {
        label: '加入班级',
        kind: 'primary',
        onClick: async () => {
          const input = modal.body.querySelector('#invite-code');
          const code = input.value.trim().toUpperCase();
          if (code.length < 6) {
            input.focus();
            toast('请输入 6 位邀请码', 'warning');
            return false;
          }
          try {
            const result = await api.classes.join(code);
            toast(`已加入「${result.class_name}」`, 'success');
            await onDone();
            return true;
          } catch (err) {
            toast(err.message, 'error');
            return false;
          }
        },
      },
    ],
  });
  window.setTimeout(() => modal.body.querySelector('#invite-code')?.focus(), 50);
}

async function openRoster(clazz) {
  const modal = openModal({
    title: `${clazz.name} · 学生名册`,
    content: '<div class="loading-line"><span class="spinner"></span>正在加载名册…</div>',
    wide: true,
  });
  try {
    const data = await api.classes.students(clazz.id);
    const students = data?.students || [];
    if (!students.length) {
      modal.body.innerHTML = '<div class="empty-state"><div class="empty-icon">⌁</div><p>暂无学生加入该班级</p></div>';
      return;
    }
    modal.body.innerHTML = `
      <div class="small muted" style="margin-bottom:12px">共 ${students.length} 名学生</div>
      <div class="roster-list">
        ${students.map((student) => `
          <div class="roster-item">
            <div class="avatar">${escapeHtml(initials(student.real_name))}</div>
            <div style="flex:1;min-width:0">
              <div style="font-size:13px;font-weight:600">${escapeHtml(student.real_name)}</div>
              <div class="tiny dim mono">${escapeHtml(student.username)}</div>
            </div>
            <div class="tiny dim">${escapeHtml(student.joined_at ? new Date(student.joined_at).toLocaleDateString('zh-CN') : '')}</div>
          </div>
        `).join('')}
      </div>
    `;
  } catch (err) {
    modal.body.innerHTML = `<div class="text-danger small">${escapeHtml(err.message)}</div>`;
  }
}

async function copyInvite(code) {
  try {
    await navigator.clipboard.writeText(code);
    toast(`邀请码 ${code} 已复制`, 'success');
  } catch (err) {
    toast(`邀请码：${code}`, 'info', 5000);
  }
}

function emptyError(message, retry) {
  return el('div', { class: 'empty-state' },
    el('div', { class: 'empty-icon text-danger' }, '!'),
    el('h3', {}, '加载失败'),
    el('p', { class: 'muted small' }, message || '请稍后重试'),
    el('button', { class: 'btn btn-sm', type: 'button', onclick: retry }, '重新加载'),
  );
}