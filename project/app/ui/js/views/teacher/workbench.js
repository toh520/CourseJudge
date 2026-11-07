/**
 * 文件名: workbench.js
 * 功能描述: 教师作业编排工作台。支持手动录入题目、AI 快速出题、标准代码验证用例、
 *          作业清单暂存与一键发布至班级。
 */

import { api } from '../../api/client.js';
import { state } from '../../store.js';
import { navigate } from '../../router.js';
import { el, escapeHtml, fmtDate } from '../../components/base/dom.js';
import { openModal } from '../../components/base/modal.js';
import { toast } from '../../components/base/toast.js';
import { typeBadge, timeStatusBadge } from '../../components/base/badges.js';
import { renderMarkdown } from '../../components/media/markdown.js';

/**
 * 渲染教师作业工作台
 * @param {HTMLElement} root
 * @param {{classId?:string}} params
 */
export async function render(root, params = {}) {
  let classes = [];
  try {
    const data = await api.classes.my();
    classes = data?.classes || [];
  } catch (err) {
    root.innerHTML = `<div class="page"><div class="empty-state"><div class="empty-icon text-danger">!</div><h3>无法加载班级</h3><p class="muted small">${escapeHtml(err.message)}</p></div></div>`;
    return;
  }

  if (!classes.length) {
    root.innerHTML = `
      <div class="page">
        <div class="empty-state">
          <div class="empty-icon">◫</div>
          <h3>还没有班级</h3>
          <p class="muted small">请先在班级大厅创建一个班级，再回来发布作业。</p>
          <button class="btn btn-primary" type="button" id="go-classes">前往班级大厅</button>
        </div>
      </div>`;
    root.querySelector('#go-classes').addEventListener('click', () => navigate('/teacher/classes'));
    return;
  }

  const requestedId = Number(params.classId);
  const activeClass = classes.find((item) => item.id === requestedId) || classes[0];
  state.selectedClassId = activeClass.id;

  root.innerHTML = `
    <div class="page">
      <header class="page-header">
        <div class="page-heading">
          <div class="page-eyebrow">Teacher Workbench</div>
          <h1 class="page-title">作业编排</h1>
          <p class="page-desc">手动录入或让 AI 生成题目与用例，确认后一次性发布到班级。</p>
        </div>
        <div class="page-actions">
          <select class="select" id="class-select" style="width:230px">
            ${classes.map((item) => `<option value="${item.id}" ${item.id === activeClass.id ? 'selected' : ''}>${escapeHtml(item.name)}</option>`).join('')}
          </select>
          <button class="btn" type="button" id="refresh-assignments">刷新</button>
        </div>
      </header>

      <div class="workbench-grid">
        <aside class="workbench-side">
          <div class="side-card">
            <div class="side-card-title">已发布作业</div>
            <div class="assignment-list" id="assignment-list">
              <div class="loading-line"><span class="spinner"></span>加载中…</div>
            </div>
          </div>
          <div class="side-card">
            <div class="side-card-title">当前班级</div>
            <div style="font-size:14px;font-weight:650">${escapeHtml(activeClass.name)}</div>
            <div class="meta-row" style="margin-top:8px">
              <span>${activeClass.student_count ?? 0} 名学生</span>
              ${activeClass.invite_code ? `<span class="inline-dot"></span><span class="mono text-accent">${escapeHtml(activeClass.invite_code)}</span>` : ''}
            </div>
          </div>
        </aside>

        <section class="builder-card" id="builder"></section>
      </div>
    </div>
  `;

  const classSelect = root.querySelector('#class-select');
  classSelect.addEventListener('change', () => navigate(`/teacher/workbench/${classSelect.value}`));
  root.querySelector('#refresh-assignments').addEventListener('click', () => loadAssignments());

  const assignmentList = root.querySelector('#assignment-list');
  const builder = root.querySelector('#builder');

  const draft = {
    title: '',
    type: 'practice',
    start: toLocalInput(new Date()),
    end: toLocalInput(new Date(Date.now() + 7 * 86400000)),
    problems: [],
  };

  let aiGenerated = false;

  function renderBuilder() {
    builder.innerHTML = `
      <div class="builder-head">
        <div>
          <div class="builder-title">编排新作业</div>
          <div class="builder-sub">支持练习 / 考试双模式；考试模式学生仅可交卷一次。</div>
        </div>
        <div class="tabs" id="mode-tabs">
          <button class="tab active" type="button" data-mode="ai">✦ AI 出题</button>
          <button class="tab" type="button" data-mode="manual">手动录入</button>
        </div>
      </div>

      <div class="form-row">
        <div class="field">
          <label for="a-title">作业名称</label>
          <input class="input" id="a-title" maxlength="100" placeholder="例如：第三周动态规划专项练习">
        </div>
        <div class="field">
          <label for="a-type">模式</label>
          <select class="select" id="a-type">
            <option value="practice">练习模式（可多次提交）</option>
            <option value="exam">考试模式（仅一次交卷）</option>
          </select>
        </div>
      </div>
      <div class="form-row" style="margin-top:12px">
        <div class="field"><label for="a-start">开始时间</label><input class="input" id="a-start" type="datetime-local"></div>
        <div class="field"><label for="a-end">截止时间</label><input class="input" id="a-end" type="datetime-local"></div>
      </div>

      <div class="builder-section">
        <div class="ai-panel" id="ai-panel">
          <div class="ai-hint">
            输入教学意图，AI 将生成 Markdown 题面、标准 C++ 17 解答，并由后端真实编译运行标准解答，
            自动回填 100% 一致的测试用例输出。
          </div>
          <div class="form-row">
            <div class="field">
              <label for="ai-intent">出题意图</label>
              <input class="input" id="ai-intent" placeholder="例如：出 1 道贪心算法区间覆盖问题，适合大一，中等难度">
            </div>
            <div class="field">
              <label for="ai-tag">知识点标签</label>
              <input class="input" id="ai-tag" maxlength="50" placeholder="例如：贪心算法">
            </div>
          </div>
          <div class="form-row">
            <div class="field">
              <label for="ai-difficulty">难度</label>
              <select class="select" id="ai-difficulty">
                <option>简单</option><option selected>中等</option><option>困难</option>
              </select>
            </div>
            <div class="field">
              <label for="ai-count">测试用例数量</label>
              <input class="input" id="ai-count" type="number" min="1" max="10" value="5">
            </div>
          </div>
          <div class="flex items-center gap-10">
            <button class="btn btn-primary" type="button" id="ai-generate">✦ AI 生成题目与用例</button>
            <span class="small dim" id="ai-status"></span>
          </div>
          <div id="ai-result"></div>
        </div>

        <div class="form-row" style="margin-top:16px">
          <div class="field">
            <label for="p-title">题目标题</label>
            <input class="input" id="p-title" maxlength="100" placeholder="题目标题">
          </div>
          <div class="field">
            <label for="p-tag">知识点</label>
            <input class="input" id="p-tag" maxlength="50" placeholder="例如：动态规划-状态转移">
          </div>
        </div>
        <div class="form-row" style="margin-top:12px">
          <div class="field"><label for="p-time">时间限制（ms）</label><input class="input" id="p-time" type="number" min="100" max="10000" value="1000"></div>
          <div class="field"><label for="p-memory">内存限制（MB）</label><input class="input" id="p-memory" type="number" min="16" max="1024" value="256"></div>
        </div>
        <div class="field" style="margin-top:12px">
          <label for="p-desc">题面描述（Markdown）</label>
          <textarea class="textarea" id="p-desc" rows="8" placeholder="输入完整题面，支持 Markdown 标题、列表、代码块…"></textarea>
        </div>
        <div class="form-row" style="margin-top:12px">
          <div class="field"><label for="p-in">输入格式</label><textarea class="textarea" id="p-in" rows="2"></textarea></div>
          <div class="field"><label for="p-out">输出格式</label><textarea class="textarea" id="p-out" rows="2"></textarea></div>
        </div>
        <div class="form-row" style="margin-top:12px">
          <div class="field"><label for="p-sample-in">样例输入</label><textarea class="textarea" id="p-sample-in" rows="3"></textarea></div>
          <div class="field"><label for="p-sample-out">样例输出</label><textarea class="textarea" id="p-sample-out" rows="3"></textarea></div>
        </div>
        <div class="field" style="margin-top:12px">
          <label>题面预览</label>
          <div class="preview-box markdown" id="p-preview"><span class="dim small">输入题面后在此预览</span></div>
        </div>
      </div>

      <div class="builder-section">
        <div class="builder-section-title">
          <span>测试用例</span>
          <span class="small dim">AI 生成后会自动填充并标记已验证</span>
        </div>
        <div class="case-editor" id="case-editor"></div>
        <button class="btn btn-sm" type="button" id="add-case" style="margin-top:8px">＋ 添加用例</button>
      </div>

      <div class="builder-section">
        <div class="builder-section-title">
          <span>作业题目清单 <span class="small dim" id="draft-count">0 题</span></span>
        </div>
        <div class="draft-list" id="draft-list">
          <div class="small dim">尚未加入题目</div>
        </div>
      </div>

      <div class="flex items-center gap-10" style="margin-top:18px;flex-wrap:wrap">
        <button class="btn" type="button" id="add-to-draft">加入作业清单</button>
        <button class="btn btn-primary" type="button" id="publish">发布作业至班级</button>
        <span class="spacer"></span>
        <span class="small dim" id="publish-hint">发布后学生即可在“我的作业”中看到。</span>
      </div>
    `;

    // 初始化时间与默认用例
    builder.querySelector('#a-start').value = draft.start;
    builder.querySelector('#a-end').value = draft.end;
    addCaseRow({ input_data: '', output_data: '', score_weight: 100 });
    bindBuilderEvents();
    renderDraftList();
    updatePreview();
  }

  function addCaseRow(data = {}) {
    const editor = builder.querySelector('#case-editor');
    const row = el('div', { class: 'case-row' },
      el('textarea', { class: 'textarea', placeholder: '测试输入', rows: '2' }),
      el('textarea', { class: 'textarea', placeholder: '期望输出', rows: '2' }),
      el('input', { class: 'input', type: 'number', min: '0', value: String(data.score_weight ?? 10), title: '分值权重' }),
      el('button', { class: 'btn btn-ghost btn-icon', type: 'button', title: '删除用例', onclick: () => row.remove() }, '✕'),
    );
    row.querySelectorAll('textarea')[0].value = data.input_data || '';
    row.querySelectorAll('textarea')[1].value = data.output_data || '';
    row.querySelectorAll('input')[0].value = String(data.score_weight ?? 10);
    editor.appendChild(row);
  }

  function collectCases() {
    return Array.from(builder.querySelectorAll('#case-editor .case-row')).map((row) => {
      const areas = row.querySelectorAll('textarea');
      return {
        input_data: areas[0].value,
        output_data: areas[1].value,
        score_weight: Number(row.querySelector('input').value || 10),
      };
    }).filter((item) => item.input_data !== '' || item.output_data !== '');
  }

  function setCases(cases) {
    const editor = builder.querySelector('#case-editor');
    editor.innerHTML = '';
    (cases || []).forEach((item) => addCaseRow(item));
    if (!(cases || []).length) addCaseRow();
  }

  function bindBuilderEvents() {
    const tabs = builder.querySelector('#mode-tabs');
    tabs.addEventListener('click', (event) => {
      const button = event.target.closest('.tab');
      if (!button) return;
      tabs.querySelectorAll('.tab').forEach((tab) => tab.classList.toggle('active', tab === button));
      builder.querySelector('#ai-panel').classList.toggle('hidden', button.dataset.mode !== 'ai');
    });

    const desc = builder.querySelector('#p-desc');
    desc.addEventListener('input', updatePreview);

    builder.querySelector('#add-case').addEventListener('click', () => addCaseRow());
    builder.querySelector('#ai-generate').addEventListener('click', generateWithAI);
    builder.querySelector('#add-to-draft').addEventListener('click', addProblemToDraft);
    builder.querySelector('#publish').addEventListener('click', publishAssignment);
  }

  function updatePreview() {
    const desc = builder.querySelector('#p-desc')?.value || '';
    const preview = builder.querySelector('#p-preview');
    if (!preview) return;
    preview.innerHTML = desc.trim()
      ? renderMarkdown(desc)
      : '<span class="dim small">输入题面后在此预览</span>';
  }

  async function generateWithAI() {
    const intent = builder.querySelector('#ai-intent').value.trim();
    const knowledgeTag = builder.querySelector('#ai-tag').value.trim();
    const difficulty = builder.querySelector('#ai-difficulty').value;
    const count = Number(builder.querySelector('#ai-count').value || 5);
    if (!intent) {
      toast('请先填写出题意图', 'warning');
      return;
    }

    const button = builder.querySelector('#ai-generate');
    const status = builder.querySelector('#ai-status');
    button.disabled = true;
    status.innerHTML = '<span class="loading-line"><span class="spinner"></span>AI 正在生成并验证用例…</span>';

    try {
      const result = await api.llm.generateProblem({
        intent,
        knowledge_tag: knowledgeTag,
        difficulty,
        test_count: count,
      });
      const problem = result.problem;
      aiGenerated = true;

      builder.querySelector('#p-title').value = problem.title || '';
      builder.querySelector('#p-tag').value = problem.knowledge_tag || knowledgeTag || '';
      builder.querySelector('#p-time').value = problem.time_limit_ms || 1000;
      builder.querySelector('#p-memory').value = problem.memory_limit_mb || 256;
      builder.querySelector('#p-desc').value = problem.description || '';
      builder.querySelector('#p-in').value = problem.input_format || '';
      builder.querySelector('#p-out').value = problem.output_format || '';
      builder.querySelector('#p-sample-in').value = problem.sample_input || '';
      builder.querySelector('#p-sample-out').value = problem.sample_output || '';
      setCases(result.test_cases || []);
      updatePreview();

      const cases = result.test_cases || [];
      builder.querySelector('#ai-result').innerHTML = `
        <div class="ai-result">
          <div class="flex items-center gap-8">
            <span class="badge badge-ac">✓ 已通过标准代码验证</span>
            <span class="small muted">${cases.length} 组用例的期望输出均由真实编译运行回填</span>
          </div>
          <div class="verified-cases">
            ${cases.map((item, index) => `
              <div class="verified-case">
                <span class="case-index">#${index + 1}</span>
                <span class="case-io">IN: ${escapeHtml(item.input_data || '(空)')}</span>
                <span class="case-io">OUT: ${escapeHtml(item.output_data || '(空)')}</span>
              </div>`).join('')}
          </div>
          <details>
            <summary class="small muted" style="cursor:pointer">查看标准 C++ 解答</summary>
            <pre class="code-block">${escapeHtml(problem.standard_code || '')}</pre>
          </details>
        </div>
      `;
      status.textContent = '';
      toast('AI 题目与用例生成完成', 'success');
    } catch (err) {
      status.textContent = '';
      toast(err.message || 'AI 出题失败', 'error', 5000);
    } finally {
      button.disabled = false;
    }
  }

  function addProblemToDraft() {
    const title = builder.querySelector('#p-title').value.trim();
    const description = builder.querySelector('#p-desc').value.trim();
    const cases = collectCases();

    if (!title) return toast('请填写题目标题', 'warning');
    if (!description) return toast('请填写题面描述', 'warning');
    if (!cases.length) return toast('请至少添加一组测试用例', 'warning');

    draft.problems.push({
      title,
      description,
      input_format: builder.querySelector('#p-in').value,
      output_format: builder.querySelector('#p-out').value,
      sample_input: builder.querySelector('#p-sample-in').value,
      sample_output: builder.querySelector('#p-sample-out').value,
      time_limit_ms: Number(builder.querySelector('#p-time').value || 1000),
      memory_limit_mb: Number(builder.querySelector('#p-memory').value || 256),
      knowledge_tag: builder.querySelector('#p-tag').value.trim(),
      is_ai_generated: aiGenerated,
      test_cases: cases,
    });

    renderDraftList();
    resetProblemForm();
    toast(`题目「${title}」已加入作业清单`, 'success');
  }

  function resetProblemForm() {
    ['p-title', 'p-tag', 'p-desc', 'p-in', 'p-out', 'p-sample-in', 'p-sample-out'].forEach((id) => {
      const node = builder.querySelector(`#${id}`);
      if (node) node.value = '';
    });
    aiGenerated = false;
    setCases([]);
    updatePreview();
    builder.querySelector('#ai-result').innerHTML = '';
  }

  function renderDraftList() {
    const list = builder.querySelector('#draft-list');
    const count = builder.querySelector('#draft-count');
    count.textContent = `${draft.problems.length} 题`;
    if (!draft.problems.length) {
      list.innerHTML = '<div class="small dim">尚未加入题目</div>';
      return;
    }
    list.innerHTML = draft.problems.map((problem, index) => `
      <div class="draft-item">
        <div style="min-width:0">
          <strong>${escapeHtml(problem.title)}</strong>
          <div><span>${problem.test_cases.length} 组用例 · ${problem.time_limit_ms}ms / ${problem.memory_limit_mb}MB</span></div>
        </div>
        <button class="btn btn-ghost btn-sm" type="button" data-index="${index}">移除</button>
      </div>
    `).join('');
    list.querySelectorAll('button[data-index]').forEach((button) => {
      button.addEventListener('click', () => {
        draft.problems.splice(Number(button.dataset.index), 1);
        renderDraftList();
      });
    });
  }

  async function publishAssignment() {
    const title = builder.querySelector('#a-title').value.trim();
    const type = builder.querySelector('#a-type').value;
    const start = builder.querySelector('#a-start').value;
    const end = builder.querySelector('#a-end').value;

    if (!title) return toast('请填写作业名称', 'warning');
    if (!draft.problems.length) return toast('请至少加入一道题目', 'warning');
    if (!start || !end) return toast('请设置开始与截止时间', 'warning');
    if (new Date(end) <= new Date(start)) return toast('截止时间必须晚于开始时间', 'warning');

    const button = builder.querySelector('#publish');
    button.disabled = true;
    button.textContent = '正在发布…';

    try {
      await api.assignments.create({
        class_id: activeClass.id,
        title,
        type,
        start_time: new Date(start).toISOString(),
        end_time: new Date(end).toISOString(),
        problems: draft.problems,
      });
      toast('作业已发布至班级', 'success');
      draft.problems = [];
      draft.title = '';
      renderBuilder();
      await loadAssignments();
    } catch (err) {
      toast(err.message || '发布失败', 'error', 5000);
      button.disabled = false;
      button.textContent = '发布作业至班级';
    }
  }

  async function loadAssignments() {
    assignmentList.innerHTML = '<div class="loading-line"><span class="spinner"></span>加载中…</div>';
    try {
      const data = await api.assignments.byClass(activeClass.id);
      const assignments = data?.assignments || [];
      if (!assignments.length) {
        assignmentList.innerHTML = '<div class="small dim" style="padding:8px 2px">该班级还没有作业</div>';
        return;
      }
      assignmentList.innerHTML = '';
      assignments.forEach((assignment) => {
        const button = el('button', { class: 'assignment-row', type: 'button' },
          el('strong', {}, assignment.title),
          el('span', {}, `${assignment.problem_count} 题 · ${fmtDate(assignment.end_time)} 截止`),
        );
        button.addEventListener('click', () => openAssignmentDetail(assignment));
        assignmentList.appendChild(button);
      });
    } catch (err) {
      assignmentList.innerHTML = `<div class="text-danger small" style="padding:8px 2px">${escapeHtml(err.message)}</div>`;
    }
  }

  async function openAssignmentDetail(assignment) {
    const modal = openModal({
      title: assignment.title,
      content: '<div class="loading-line"><span class="spinner"></span>加载题目…</div>',
      wide: true,
    });
    try {
      const data = await api.assignments.problems(assignment.id);
      const problems = data?.problems || [];
      modal.body.innerHTML = `
        <div class="flex items-center gap-8" style="flex-wrap:wrap;margin-bottom:14px">
          ${typeBadge(assignment.type)} ${timeStatusBadge(assignment.time_status)}
          <span class="badge badge-muted">${problems.length} 题</span>
          <span class="small dim">${fmtDate(assignment.start_time)} → ${fmtDate(assignment.end_time)}</span>
        </div>
        <div class="draft-list">
          ${problems.map((problem, index) => `
            <div class="draft-item">
              <div style="min-width:0">
                <strong>${index + 1}. ${escapeHtml(problem.title)}</strong>
                <div class="small dim">${escapeHtml(problem.knowledge_tag || '未标注知识点')} · ${problem.test_case_count} 组用例 · ${problem.time_limit_ms}ms / ${problem.memory_limit_mb}MB</div>
              </div>
              <span class="badge badge-muted">${problem.is_ai_generated ? 'AI 生成' : '手动录入'}</span>
            </div>
          `).join('') || '<div class="small dim">暂无题目</div>'}
        </div>
      `;
    } catch (err) {
      modal.body.innerHTML = `<div class="text-danger small">${escapeHtml(err.message)}</div>`;
    }
  }

  function toLocalInput(date) {
    const pad = (value) => String(value).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  renderBuilder();
  await loadAssignments();
}