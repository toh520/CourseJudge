/**
 * 文件名: workbench.js
 * 功能描述: 学生沉浸式编程工作台。左侧题面、右侧 Monaco 编辑器与自测控制台；
 *          支持练习多次提交、考试单次交卷锁定、AI 短板诊断与一键补弱。
 */

import { api } from '../../api/client.js';
import { navigate } from '../../router.js';
import { escapeHtml, fmtDate } from '../../components/base/dom.js';
import { confirmDialog } from '../../components/base/modal.js';
import { toast } from '../../components/base/toast.js';
import { statusBadge, typeBadge } from '../../components/base/badges.js';
import { renderMarkdown } from '../../components/media/markdown.js';
import { createEditor, cppTemplate } from '../../components/editor/editor.js';

/**
 * 渲染学生做题工作台
 * @param {HTMLElement} root
 * @param {{assignmentId?:string, problemId?:string}} params
 */
export async function render(root, params = {}) {
  const assignmentId = Number(params.assignmentId);
  const problemId = Number(params.problemId);

  if (!assignmentId || !problemId) {
    root.innerHTML = '<div class="page"><div class="empty-state"><h3>缺少作业或题目参数</h3></div></div>';
    return;
  }

  root.innerHTML = '<div class="empty-state" style="height:100vh"><span class="spinner spinner-lg"></span><span>正在加载题目…</span></div>';

  let assignment;
  let problem;
  try {
    const [detail, problemData] = await Promise.all([
      api.assignments.detail(assignmentId),
      api.assignments.problems(assignmentId),
    ]);
    assignment = detail;
    problem = (problemData?.problems || []).find((item) => item.id === problemId);
  } catch (err) {
    root.innerHTML = `<div class="page"><div class="empty-state"><div class="empty-icon text-danger">!</div><h3>加载失败</h3><p class="muted small">${escapeHtml(err.message)}</p><button class="btn" type="button" id="back">返回我的作业</button></div></div>`;
    root.querySelector('#back').addEventListener('click', () => navigate('/student/assignments'));
    return;
  }

  if (!problem) {
    root.innerHTML = `<div class="page"><div class="empty-state"><div class="empty-icon">◫</div><h3>题目不存在</h3><button class="btn" type="button" id="back">返回我的作业</button></div></div>`;
    root.querySelector('#back').addEventListener('click', () => navigate('/student/assignments'));
    return;
  }

  const isExam = assignment.type === 'exam';
  const lockKey = `cj_exam_submitted_${assignmentId}_${problemId}`;
  let examLocked = isExam && window.localStorage.getItem(lockKey) === '1';

  root.innerHTML = `
    <div class="lab-grid">
      <section class="problem-pane">
        <div class="problem-head">
          <div>
            <div class="page-eyebrow" style="margin-bottom:4px">${escapeHtml(assignment.title)}</div>
            <h2 class="problem-title">${escapeHtml(problem.title)}</h2>
          </div>
          ${typeBadge(assignment.type)}
        </div>
        <div class="problem-limits">
          <span class="limit-chip">⏱ ${problem.time_limit_ms} ms</span>
          <span class="limit-chip">▣ ${problem.memory_limit_mb} MB</span>
          ${problem.knowledge_tag ? `<span class="limit-chip"># ${escapeHtml(problem.knowledge_tag)}</span>` : ''}
          <span class="limit-chip">截止 ${fmtDate(assignment.end_time)}</span>
        </div>
        ${isExam ? `<div class="exam-banner"><strong>考试模式</strong>：正式交卷仅限一次，提交后本题将锁定；答题期间可多次自测运行。</div>` : ''}
        <div class="markdown" id="problem-desc"></div>
        <div class="sample-grid">
          <div class="sample-card">
            <div class="sample-label">样例输入</div>
            <pre>${escapeHtml(problem.sample_input || '（无）')}</pre>
          </div>
          <div class="sample-card">
            <div class="sample-label">样例输出</div>
            <pre>${escapeHtml(problem.sample_output || '（无）')}</pre>
          </div>
        </div>
      </section>

      <section class="coding-pane">
        <div class="coding-head">
          <span class="editor-lang">C++17 · UTF-8</span>
          <span class="spacer"></span>
          <div class="coding-actions">
            <button class="btn btn-sm" type="button" id="btn-run">▷ 自测运行</button>
            <button class="btn btn-primary btn-sm" type="button" id="btn-submit">${examLocked ? '已交卷' : '提交判题'}</button>
            <button class="btn btn-sm hidden" type="button" id="btn-diagnose">✦ AI 诊断</button>
          </div>
        </div>
        <div class="coding-main">
          <div class="editor-frame" id="editor-host"></div>
        </div>
        <div class="console-panel">
          <div class="console-head">
            <span class="console-title">自测输入 / 输出</span>
            <span class="spacer"></span>
            <button class="btn btn-ghost btn-sm" type="button" id="btn-clear">清空输出</button>
          </div>
          <div class="console-body">
            <textarea class="textarea" id="stdin" rows="3" placeholder="输入自定义测试数据，然后点击“自测运行”"></textarea>
            <div class="console-output empty" id="console-output" style="margin-top:8px">运行结果将显示在这里</div>
          </div>
        </div>
        <div class="result-panel hidden" id="result-area"></div>
      </section>
    </div>
  `;

  root.querySelector('#problem-desc').innerHTML = renderMarkdown(problem.description || '');
  const resultArea = root.querySelector('#result-area');
  const output = root.querySelector('#console-output');
  const submitButton = root.querySelector('#btn-submit');
  const diagnoseButton = root.querySelector('#btn-diagnose');

  const codeKey = `cj_code_${problem.id}`;
  let savedCode = '';
  try {
    savedCode = window.localStorage.getItem(codeKey) || '';
  } catch (err) {
    savedCode = '';
  }

  const editor = await createEditor(root.querySelector('#editor-host'), {
    value: savedCode || cppTemplate(problem.title),
    language: 'cpp',
    readOnly: examLocked,
    onChange: (value) => {
      try { window.localStorage.setItem(codeKey, value); } catch (err) { /* 忽略存储失败 */ }
    },
  });

  if (examLocked) {
    submitButton.disabled = true;
    submitButton.textContent = '已交卷';
    diagnoseButton.classList.remove('hidden');
    resultArea.classList.remove('hidden');
    resultArea.innerHTML = '<div class="exam-banner"><strong>本题已交卷</strong>：可继续自测查看运行结果，但无法再次正式提交。</div>';
  }

  window.setTimeout(() => editor.layout(), 30);

  function setOutput(text, isError = false) {
    output.textContent = text || '（无输出）';
    output.classList.toggle('empty', !text);
    output.classList.toggle('error', Boolean(isError));
  }

  root.querySelector('#btn-clear').addEventListener('click', () => setOutput(''));

  root.querySelector('#btn-run').addEventListener('click', async () => {
    const button = root.querySelector('#btn-run');
    button.disabled = true;
    button.textContent = '运行中…';
    setOutput('正在编译并运行…');
    try {
      const result = await api.judge.runTest({
        problem_id: problem.id,
        code: editor.getValue(),
        input_data: root.querySelector('#stdin').value,
      });
      const lines = [];
      if (result.execution_status === 'CE') {
        setOutput(result.compiler_output || result.error_msg || '编译失败', true);
      } else {
        lines.push(`状态：${result.execution_status}　耗时：${result.time_ms} ms`);
        if (result.stdout) lines.push('', result.stdout);
        if (result.error_msg) lines.push('', result.error_msg);
        setOutput(lines.join('\n'), result.execution_status !== 'AC');
      }
    } catch (err) {
      setOutput(err.message, true);
      toast(err.message, 'error');
    } finally {
      button.disabled = false;
      button.textContent = '▷ 自测运行';
    }
  });

  submitButton.addEventListener('click', async () => {
    if (examLocked) {
      toast('本题已交卷，无法重复提交', 'warning');
      return;
    }
    if (isExam) {
      const confirmed = await confirmDialog({
        title: '确认交卷？',
        message: '考试模式仅允许正式提交一次，提交后本题将立即锁定，无法再次修改交卷。',
        confirmText: '确认交卷',
        danger: true,
      });
      if (!confirmed) return;
    }

    submitButton.disabled = true;
    submitButton.textContent = '评测中…';
    resultArea.classList.remove('hidden');
    resultArea.innerHTML = '<div class="loading-line"><span class="spinner"></span>正在编译并评测全部隐藏用例…</div>';

    try {
      const result = await api.judge.submit({ problem_id: problem.id, code: editor.getValue() });
      renderSubmitResult(result, isExam);
      diagnoseButton.classList.remove('hidden');
      toast(result.status === 'AC' ? '恭喜，全部用例通过！' : `评测完成：${result.status}`, result.status === 'AC' ? 'success' : 'warning');
      if (isExam) {
        examLocked = true;
        try { window.localStorage.setItem(lockKey, '1'); } catch (err) { /* ignore */ }
        editor.setReadOnly(true);
        submitButton.textContent = '已交卷';
      } else {
        submitButton.disabled = false;
        submitButton.textContent = '提交判题';
      }
    } catch (err) {
      resultArea.innerHTML = `<div class="text-danger small">${escapeHtml(err.message)}</div>`;
      toast(err.message, 'error');
      submitButton.disabled = false;
      submitButton.textContent = '提交判题';
    }
  });

  diagnoseButton.addEventListener('click', async () => {
    diagnoseButton.disabled = true;
    diagnoseButton.textContent = '诊断中…';
    resultArea.classList.remove('hidden');
    resultArea.innerHTML = '<div class="loading-line"><span class="spinner"></span>AI 正在分析本次作业的失分点…</div>';
    try {
      const report = await api.llm.diagnose(assignmentId);
      renderDiagnosis(report);
    } catch (err) {
      resultArea.innerHTML = `<div class="text-danger small">${escapeHtml(err.message)}</div>`;
      toast(err.message, 'error');
    } finally {
      diagnoseButton.disabled = false;
      diagnoseButton.textContent = '✦ AI 诊断';
    }
  });

  function renderSubmitResult(result, hideDetails) {
    const caseRows = hideDetails ? '' : (result.case_results || []).map((item, index) => `
      <tr>
        <td>#${index + 1}</td>
        <td>${statusBadge(item.case_status)}</td>
        <td class="mono">${item.time_ms ?? 0} ms</td>
        <td class="mono">${escapeHtml((item.stdout || '').slice(0, 120))}</td>
        <td class="mono">${escapeHtml((item.error_msg || '').slice(0, 120))}</td>
      </tr>
    `).join('');

    resultArea.innerHTML = `
      <div class="result-head">
        ${statusBadge(result.status)}
        <span class="badge badge-muted">得分 ${result.score}</span>
        <span class="small muted">通过 ${result.passed_cases}/${result.total_cases} · 最大耗时 ${result.max_time_ms} ms</span>
      </div>
      ${hideDetails
        ? '<div class="exam-banner"><strong>考试模式</strong>：详细测试点数据已隐藏，仅展示最终得分与状态。</div>'
        : `<div class="table-wrap" style="margin-top:10px">
            <table class="table">
              <thead><tr><th>用例</th><th>状态</th><th>耗时</th><th>输出</th><th>错误</th></tr></thead>
              <tbody>${caseRows || '<tr><td colspan="5" class="dim">无用例明细</td></tr>'}</tbody>
            </table>
          </div>`}
      ${result.compiler_output ? `<details style="margin-top:10px"><summary class="small muted" style="cursor:pointer">查看编译器输出</summary><pre class="code-block">${escapeHtml(result.compiler_output)}</pre></details>` : ''}
    `;
  }

  function renderDiagnosis(report) {
    const weakPoints = report.weak_points || [];
    resultArea.innerHTML = `
      <div class="diagnosis-panel">
        <div class="flex items-center gap-8" style="flex-wrap:wrap">
          <span class="badge badge-accent">✦ AI 短板诊断</span>
          <span class="small muted">${escapeHtml(report.summary || '')}</span>
        </div>
        <div class="diagnosis-list">
          ${weakPoints.map((point) => `
            <div class="diagnosis-card">
              <div class="diagnosis-card-head">
                <span class="diagnosis-tag">${escapeHtml(point.tag)}</span>
                <button class="btn btn-sm" type="button" data-tag="${escapeHtml(point.tag)}">一键补弱</button>
              </div>
              <div class="diagnosis-evidence">${escapeHtml(point.evidence || '')}</div>
              <div class="diagnosis-suggestion">${escapeHtml(point.suggestion || '')}</div>
            </div>
          `).join('') || '<div class="small dim">本次作业没有发现明显薄弱点。</div>'}
        </div>
        ${report.learning_guidance ? `<div class="small muted"><strong class="text-accent">学习建议：</strong>${escapeHtml(report.learning_guidance)}</div>` : ''}
        <div id="training-result"></div>
      </div>
    `;

    resultArea.querySelectorAll('button[data-tag]').forEach((button) => {
      button.addEventListener('click', () => generateTraining(button.dataset.tag, button));
    });
  }

  async function generateTraining(tag, button) {
    button.disabled = true;
    button.textContent = '生成中…';
    const box = resultArea.querySelector('#training-result');
    box.innerHTML = '<div class="loading-line" style="margin-top:10px"><span class="spinner"></span>正在生成专属强化题并验证用例…</div>';
    try {
      const training = await api.llm.generateTraining({
        weak_point: tag,
        source_assignment_id: assignmentId,
        test_count: 4,
      });
      box.innerHTML = `
        <div class="ai-result" style="margin-top:10px">
          <div class="flex items-center gap-8" style="flex-wrap:wrap">
            <span class="badge badge-ac">✓ 强化题已生成并保存</span>
            <strong style="font-size:13px">${escapeHtml(training.title)}</strong>
          </div>
          <div class="small muted">知识点：${escapeHtml(training.knowledge_tag)} · 初始状态：${escapeHtml(training.best_status)}</div>
          <button class="btn btn-primary btn-sm" type="button" id="go-training" style="width:fit-content">前往强化训练题本</button>
        </div>
      `;
      box.querySelector('#go-training').addEventListener('click', () => navigate('/student/training'));
      toast('专属强化题已加入题本', 'success');
    } catch (err) {
      box.innerHTML = `<div class="text-danger small" style="margin-top:10px">${escapeHtml(err.message)}</div>`;
      toast(err.message, 'error');
    } finally {
      button.disabled = false;
      button.textContent = '一键补弱';
    }
  }

  return () => {
    editor.dispose();
  };
}