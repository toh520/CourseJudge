/**
 * 文件名: store.js
 * 功能描述: 前端全局状态容器。保存当前登录用户、系统探针状态与视图清理函数，
 *          避免各视图之间通过 DOM 互相读取隐式状态。
 */

export const state = {
  user: null,
  status: null,
  cleanup: null,
  selectedClassId: null,
};

/**
 * 设置当前登录用户
 * @param {object|null} user 用户信息
 */
export function setUser(user) {
  state.user = user || null;
}

/**
 * 清除登录态与视图资源
 */
export function clearUser() {
  state.user = null;
  if (typeof state.cleanup === 'function') {
    try { state.cleanup(); } catch (err) { console.warn(err); }
  }
  state.cleanup = null;
}

/**
 * 设置系统探针状态
 * @param {object|null} status /api/v1/system/status 返回体
 */
export function setStatus(status) {
  state.status = status || null;
}