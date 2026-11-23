/**
 * 文件名: training.js
 * 功能描述: 学生专属强化训练题本。展示 AI 生成的个性化题目，支持在线编码、
 *          提交判分与历史最佳状态回写。
 */

import { state } from '../../store.js';
import { api } from '../../api/client.js';
import { navigate } from '../../router.js';
import { escapeHtml, fmtDate } from '../../components/base/dom.js';
import { toast } from '../../components/base/toast.js';
import { statusBadge, bestStatusBadge } from '../../components/base/badges.js';
import { renderMarkdown } from '../../components/media/markdown.js';
import { createEditor, cppTemplate } from '../../components/editor/editor.js';

/**
 * 渲染强化训练题本
 * @param {HTMLElement} root
 */
export async function render(root) {
  root.innerHTML = `
    <div class="page">
      <header class="page-header">
        <div class="page-heading">
          <h1 class="page-title">强化训练题本</h1>
          <p class="page-desc">针对考后诊断出的薄弱知识点，AI 为你生成的专属巩固题。</p>
        </div>
        <div class="page-actions">
          <button class="btn" type="button" id="go-assignments">返回我的作业</button>
        </div>
      </header>
      <div id="training-content">
        <div class="empty-state"><span class="spinner spinner-lg"></span><span>正在加载训练题…</span></div>
      </div>
    </div>
  `;

  root.querySelector('#go-assignments').addEventListener('click', () => navigate('/student/assignments'));
  const content = root.querySelector('#training-content');

  let selectedId = null;
  let editor = null;

  async function loadList() {
    try {
      const data = await api.training.my();
      const items = data?.training_list || [];
      if (!items.length) {
        content.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">✦</div>
            <h3>题本还是空的</h3>
            <p class="muted small">完成作业后点击“AI 诊断”，再对薄弱点点击“一键补弱”，专属题目会出现在这里。</p>
            <button class="btn btn-primary" type="button" id="to-assignments">去做作业</button>
          </div>`;
        content.querySelector('#to-assignments').addEventListener('click', () => navigate('/student/assignments'));
        return;
      }

      content.innerHTML = `
        <div class="training-layout">
          <aside class="card card-pad">
            <div class="side-card-title">我的训练题 <span class="badge badge-muted">${items.length}</span></div>
            <div class="training-list" id="training-list"></div>
          </aside>
          <section class="training-detail" id="training-detail"></section>
        </div>
      `;

      const list = content.querySelector('#training-list');
      items.forEach((item) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'training-item';
        button.innerHTML = `
          <strong>${escapeHtml(item.title)}</strong>
          <span>${escapeHtml(item.knowledge_tag)} · ${fmtDate(item.created_at)}</span>
          <span>${bestStatusBadge(item.best_status)}</span>
        `;
        button.addEventListener('click', () => {
          list.querySelectorAll('.training-item').forEach((node) => node.classList.toggle('active', node === button));
          openDetail(item.id);
        });
        list.appendChild(button);
      });

      const firstId = selectedId || items[0].id;
      const firstButton = list.querySelector('.training-item');
      if (firstButton) firstButton.classList.add('active');
      await openDetail(firstId);
    } catch (err) {
      content.innerHTML = `<div class="empty-state"><div class="empty-icon text-danger">!</div><h3>加载失败</h3><p class="muted small">${escapeHtml(err.message)}</p></div>`;
      toast(err.message, 'error');
    }
  }

  async function openDetail(trainingId) {
    selectedId = trainingId;
    if (editor) {
      editor.dispose();
      editor = null;
    }
    const detail = content.querySelector('#training-detail');
    detail.innerHTML = '<div class="empty-state"><span class="spinner"></span><span>加载题目…</span></div>';

    let problem;
    try {
      problem = await api.training.detail(trainingId);
    } catch (err) {
      detail.innerHTML = `<div class="empty-state"><div class="text-danger small">${escapeHtml(err.message)}</div></div>`;
      return;
    }

    detail.innerHTML = `
      <div class="training-detail-body">
        <div class="flex items-center gap-8" style="flex-wrap:wrap;margin-bottom:8px">
          <span class="badge badge-accent"># ${escapeHtml(problem.knowledge_tag)}</span>
          ${bestStatusBadge(problem.best_status)}
        </div>
        <h2 style="font-size:18px;margin-bottom:10px">${escapeHtml(problem.title)}</h2>
        <div class="markdown" id="training-desc"></div>
        <div class="sample-grid">
          <div class="sample-card"><div class="sample-label">样例输入</div><pre>${escapeHtml(problem.sample_input || '（无）')}</pre></div>
          <div class="sample-card"><div class="sample-label">样例输出</div><pre>${escapeHtml(problem.sample_output || '（无）')}</pre></div>
        </div>
      </div>
      <div class="training-editor-wrap">
        <div class="editor-toolbar">
          <span class="editor-lang">C++17 · UTF-8</span>
          <span class="spacer"></span>
          <button class="btn btn-primary btn-sm" type="button" id="training-submit">提交判题</button>
        </div>
        <div class="editor-frame" id="training-editor" style="min-height:300px"></div>
        <div class="result-panel hidden" id="training-result"></div>
      </div>
    `;

    detail.querySelector('#training-desc').innerHTML = renderMarkdown(problem.description || '');

    const codeKey = `cj_training_code_${state.user.id}_${problem.id}`;
    let saved = '';
    try { saved = window.localStorage.getItem(codeKey) || ''; } catch (err) { saved = ''; }

    editor = await createEditor(detail.querySelector('#training-editor'), {
      value: saved || cppTemplate(problem.title),
      language: 'cpp',
      onChange: (value) => {
        try { window.localStorage.setItem(codeKey, value); } catch (err) { /* ignore */ }
      },
    });
    window.setTimeout(() => editor?.layout(), 30);

    const submit = detail.querySelector('#training-submit');
    const resultBox = detail.querySelector('#training-result');

    submit.addEventListener('click', async () => {
      submit.disabled = true;
      submit.textContent = '评测中…';
      resultBox.classList.remove('hidden');
      resultBox.innerHTML = '<div class="loading-line"><span class="spinner"></span>正在评测…</div>';
      try {
        const result = await api.training.submit(problem.id, editor.getValue());
        resultBox.innerHTML = `
          <div class="result-head">
            ${statusBadge(result.status)}
            <span class="badge badge-muted">得分 ${result.score}</span>
            <span class="small muted">通过 ${result.passed_cases}/${result.total_cases} · ${result.max_time_ms} ms</span>
            <span class="spacer"></span>
            <span class="small muted">历史最佳：${bestStatusBadge(result.best_status)}</span>
          </div>
        `;
        toast(result.status === 'AC' ? '恭喜，已掌握该知识点！' : `评测完成：${result.status}`, result.status === 'AC' ? 'success' : 'warning');
        await loadList();
      } catch (err) {
        resultBox.innerHTML = `<div class="text-danger small">${escapeHtml(err.message)}</div>`;
        toast(err.message, 'error');
        submit.disabled = false;
        submit.textContent = '提交判题';
      }
    });
  }

  await loadList();

  return () => {
    if (editor) editor.dispose();
  };
}