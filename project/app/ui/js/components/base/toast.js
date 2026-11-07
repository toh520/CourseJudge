/**
 * 文件名: toast.js
 * 功能描述: 非阻塞式轻提示。支持 success / error / warning / info 四种语义。
 */

import { el } from './dom.js';

/**
 * 显示提示
 * @param {string} message 文案
 * @param {'info'|'success'|'error'|'warning'} type 类型
 * @param {number} timeout 自动关闭毫秒数
 */
export function toast(message, type = 'info', timeout = 3200) {
  const root = document.getElementById('toast-root');
  if (!root) return;

  const node = el('div', { class: `toast toast-${type}` },
    el('span', { class: 'toast-dot' }),
    el('div', { class: 'toast-message' }, String(message || '')),
  );
  root.appendChild(node);

  const remove = () => {
    if (!node.isConnected) return;
    node.style.opacity = '0';
    node.style.transform = 'translateY(6px)';
    node.style.transition = 'opacity .16s ease, transform .16s ease';
    window.setTimeout(() => node.remove(), 180);
  };

  node.addEventListener('click', remove);
  if (timeout > 0) window.setTimeout(remove, timeout);
  return remove;
}