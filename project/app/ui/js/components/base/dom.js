/**
 * 文件名: dom.js
 * 功能描述: 轻量 DOM 与格式化工具。所有动态文本在插入 HTML 前必须经过 escapeHtml。
 */

/**
 * 创建元素
 * @param {string} tag 标签名
 * @param {object} attrs 属性/事件
 * @param {...(Node|string)} children 子节点
 * @returns {HTMLElement}
 */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key.startsWith('on') && typeof value === 'function') {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key === 'html') node.innerHTML = value;
    else node.setAttribute(key, value === true ? '' : String(value));
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined) continue;
    node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
  }
  return node;
}

/**
 * HTML 转义，防止模型/用户输入注入
 * @param {*} value
 * @returns {string}
 */
export function escapeHtml(value) {
  return String(value === null || value === undefined ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * 清空节点
 * @param {HTMLElement} node
 */
export function clear(node) {
  if (node) node.innerHTML = '';
}

export function qs(selector, root = document) {
  return root.querySelector(selector);
}

export function qsa(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}

/**
 * 格式化日期时间
 * @param {string|Date} value
 * @returns {string}
 */
export function fmtDate(value) {
  if (!value) return '—';
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  });
}

/**
 * 根据截止时间生成人类可读倒计时
 * @param {string} endTime ISO 时间
 * @returns {{text:string, ended:boolean}}
 */
export function countdown(endTime) {
  if (!endTime) return { text: '无截止时间', ended: false };
  const end = new Date(endTime).getTime();
  if (Number.isNaN(end)) return { text: '时间未知', ended: false };
  const diff = end - Date.now();
  if (diff <= 0) return { text: '已截止', ended: true };
  const minutes = Math.floor(diff / 60000);
  const days = Math.floor(minutes / 1440);
  const hours = Math.floor((minutes % 1440) / 60);
  const mins = minutes % 60;
  if (days > 0) return { text: `剩余 ${days} 天 ${hours} 小时`, ended: false };
  if (hours > 0) return { text: `剩余 ${hours} 小时 ${mins} 分`, ended: false };
  return { text: `剩余 ${Math.max(1, mins)} 分钟`, ended: false };
}

/**
 * 取姓名首字作为头像文本
 * @param {string} name
 * @returns {string}
 */
export function initials(name) {
  const text = String(name || '?').trim();
  return text ? text.slice(0, 1).toUpperCase() : '?';
}

/**
 * 防抖
 * @param {Function} fn
 * @param {number} wait
 * @returns {Function}
 */
export function debounce(fn, wait = 200) {
  let timer = null;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), wait);
  };
}

/**
 * 数字安全格式化
 * @param {*} value
 * @param {string} fallback
 * @returns {string}
 */
export function num(value, fallback = '—') {
  return value === null || value === undefined || Number.isNaN(Number(value))
    ? fallback
    : String(value);
}