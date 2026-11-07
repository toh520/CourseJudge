/**
 * 文件名: modal.js
 * 功能描述: 模态框与确认对话框。支持 HTML 内容、操作按钮与 ESC 关闭。
 */

import { el } from './dom.js';

/**
 * 打开模态框
 * @param {object} options
 * @param {string} options.title 标题
 * @param {string|Node} options.content 内容
 * @param {Array<{label:string,kind?:string,onClick?:Function,close?:boolean}>} options.actions 操作按钮
 * @param {boolean} options.wide 是否宽版
 * @returns {{close:Function, body:HTMLElement}}
 */
export function openModal({ title = '', content = '', actions = [], wide = false } = {}) {
  const root = document.getElementById('overlay-root');
  const backdrop = el('div', { class: 'modal-backdrop' });
  const body = el('div', { class: 'modal-body' });

  if (content instanceof Node) body.appendChild(content);
  else body.innerHTML = String(content || '');

  const footer = el('div', { class: 'modal-footer' });

  const close = () => {
    backdrop.remove();
    document.removeEventListener('keydown', onKey);
  };

  const onKey = (event) => {
    if (event.key === 'Escape') close();
  };

  actions.forEach((action) => {
    const button = el('button', {
      class: `btn ${action.kind === 'primary' ? 'btn-primary' : action.kind === 'danger' ? 'btn-danger' : ''}`,
      type: 'button',
      onclick: async () => {
        if (typeof action.onClick === 'function') {
          const result = await action.onClick();
          if (result === false) return;
        }
        if (action.close !== false) close();
      },
    }, action.label || '确定');
    footer.appendChild(button);
  });

  const dialog = el('div', { class: `modal ${wide ? 'modal-wide' : ''}`, role: 'dialog', 'aria-modal': 'true' },
    el('div', { class: 'modal-header' },
      el('div', { class: 'modal-title' }, title),
      el('button', { class: 'close-btn', type: 'button', 'aria-label': '关闭', onclick: close }, '✕'),
    ),
    body,
    actions.length ? footer : null,
  );

  backdrop.appendChild(dialog);
  backdrop.addEventListener('click', (event) => {
    if (event.target === backdrop) close();
  });
  root.appendChild(backdrop);
  document.addEventListener('keydown', onKey);

  return { close, body };
}

/**
 * 确认对话框
 * @param {object} options
 * @returns {Promise<boolean>}
 */
export function confirmDialog({ title = '请确认', message = '', confirmText = '确认', cancelText = '取消', danger = false } = {}) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };

    const modal = openModal({
      title,
      content: `<div class="muted" style="font-size:13px;line-height:1.7">${message}</div>`,
      actions: [
        { label: cancelText, onClick: () => finish(false) },
        { label: confirmText, kind: danger ? 'danger' : 'primary', onClick: () => finish(true) },
      ],
    });

    // 监听 ESC / 点击遮罩关闭时按取消处理
    const observer = new MutationObserver(() => {
      if (!document.getElementById('overlay-root').contains(modal.body.closest('.modal-backdrop'))) {
        observer.disconnect();
        finish(false);
      }
    });
    observer.observe(document.getElementById('overlay-root'), { childList: true });
  });
}