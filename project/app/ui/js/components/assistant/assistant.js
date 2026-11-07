/**
 * 文件名: assistant.js
 * 功能描述: 全局 AI 助教浮窗。支持多轮历史、SSE 流式打字机输出与 Markdown 渲染。
 */

import { streamChat } from '../../api/client.js';
import { renderMarkdown } from '../media/markdown.js';
import { el, escapeHtml } from '../base/dom.js';
import { toast } from '../base/toast.js';

const SUGGESTIONS = [
  '解释一下 C++ 中指针和引用的区别',
  '动态规划的状态转移方程怎么推？',
  '帮我分析一个常见的段错误原因',
];

let controller = null;

/**
 * 挂载 AI 助手浮窗
 */
export function mountAssistant() {
  if (document.getElementById('assistant-fab')) return;

  const history = [];
  const fab = el('button', {
    id: 'assistant-fab',
    class: 'assistant-fab',
    type: 'button',
    title: 'AI 助教',
    'aria-label': '打开 AI 助教',
    html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15z"/></svg>',
  });

  const messages = el('div', { class: 'assistant-messages' });
  const input = el('textarea', {
    class: 'input',
    rows: '1',
    placeholder: '问 C++ 语法、算法思路或编译报错…',
    'aria-label': '向 AI 助教提问',
  });
  const sendBtn = el('button', { class: 'btn btn-primary btn-sm', type: 'button' }, '发送');

  const panel = el('section', { class: 'assistant-panel hidden', 'aria-label': 'AI 助教' },
    el('header', { class: 'assistant-head' },
      el('div', { class: 'assistant-avatar' }, '✦'),
      el('div', {},
        el('div', { class: 'assistant-title' }, 'AI 编程助教'),
        el('div', { class: 'assistant-sub' }, '基于课程知识库 · 流式回答'),
      ),
      el('div', { class: 'spacer' }),
      el('button', { class: 'btn btn-ghost btn-sm', type: 'button', onclick: clearHistory, title: '清空对话' }, '清空'),
      el('button', { class: 'close-btn', type: 'button', 'aria-label': '关闭', onclick: toggle }, '✕'),
    ),
    messages,
    el('div', { class: 'assistant-input' },
      input,
      sendBtn,
    ),
    el('div', { class: 'assistant-hint' }, 'Enter 发送 · Shift + Enter 换行'),
  );

  function toggle() {
    panel.classList.toggle('hidden');
    if (!panel.classList.contains('hidden')) {
      input.focus();
      scrollToBottom();
    }
  }

  function scrollToBottom() {
    messages.scrollTop = messages.scrollHeight;
  }

  function clearHistory() {
    history.length = 0;
    messages.innerHTML = '';
    addMessage('assistant', '你好，我是 CourseJudge 的 AI 编程助教。可以问我 C++ 语法、算法思路或编译报错。');
  }

  function addMessage(role, content, options = {}) {
    const bubble = el('div', { class: 'msg-bubble' });
    if (role === 'assistant') bubble.innerHTML = renderMarkdown(content);
    else bubble.textContent = content;

    const wrapper = el('div', { class: `msg ${role}` },
      el('div', { class: 'msg-avatar' }, role === 'user' ? '我' : '✦'),
      bubble,
    );
    messages.appendChild(wrapper);
    scrollToBottom();
    return { wrapper, bubble, ...options };
  }

  function addSuggestions() {
    const wrap = el('div', { class: 'assistant-suggestions' });
    SUGGESTIONS.forEach((text) => {
      wrap.appendChild(el('button', {
        class: 'suggestion-chip',
        type: 'button',
        onclick: () => {
          input.value = text;
          send();
        },
      }, text));
    });
    messages.appendChild(wrap);
  }

  async function send() {
    const message = input.value.trim();
    if (!message) return;
    if (controller) {
      controller.abort();
      controller = null;
    }

    input.value = '';
    input.style.height = 'auto';
    addMessage('user', message);
    // 历史只传本轮之前的消息，本轮提问由后端单独追加，避免重复注入
    const priorHistory = history.slice(-20);
    history.push({ role: 'user', content: message });

    const { bubble } = addMessage('assistant', '正在思考…');
    bubble.innerHTML = '<span class="loading-line"><span class="spinner"></span>正在组织回答…</span>';

    controller = new AbortController();
    let raw = '';
    let frame = 0;

    const paint = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(() => {
        frame = 0;
        bubble.innerHTML = `${renderMarkdown(raw)}<span class="typing-cursor">▍</span>`;
        scrollToBottom();
      });
    };

    try {
      const finalText = await streamChat(
        message,
        priorHistory,
        (delta) => {
          raw += delta;
          paint();
        },
        controller.signal,
      );
      raw = finalText || raw;
      bubble.innerHTML = renderMarkdown(raw);
      history.push({ role: 'assistant', content: raw });
    } catch (err) {
      if (err.name === 'AbortError') {
        bubble.innerHTML = '<span class="muted">已停止生成。</span>';
      } else {
        bubble.innerHTML = `<span class="text-danger">${escapeHtml(err.message || 'AI 服务暂不可用')}</span>`;
        toast(err.message || 'AI 服务暂不可用', 'error');
      }
    } finally {
      controller = null;
      scrollToBottom();
    }
  }

  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  });

  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
  });

  sendBtn.addEventListener('click', send);
  fab.addEventListener('click', toggle);

  document.body.appendChild(fab);
  document.body.appendChild(panel);

  clearHistory();
  addSuggestions();
}