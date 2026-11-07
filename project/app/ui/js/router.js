/**
 * 文件名: router.js
 * 功能描述: 基于 hash 的轻量单页路由工具。
 */

/**
 * 跳转到指定 hash 路径
 * @param {string} path 以 / 开头的路径
 */
export function navigate(path) {
  const normalized = path.startsWith('/') ? path : `/${path}`;
  const target = `#${normalized}`;
  if (window.location.hash === target) {
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    return;
  }
  window.location.hash = normalized;
}

/**
 * 获取当前 hash 路径
 * @returns {string}
 */
export function currentPath() {
  const raw = (window.location.hash || '').replace(/^#/, '');
  return raw || '/';
}

/**
 * 用正则匹配路径并返回捕获组
 * @param {string} path 当前路径
 * @param {RegExp} pattern 路由正则
 * @returns {string[]|null}
 */
export function match(path, pattern) {
  const result = path.match(pattern);
  return result ? result.slice(1) : null;
}