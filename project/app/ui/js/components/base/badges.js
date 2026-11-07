/**
 * 文件名: badges.js
 * 功能描述: 状态、模式、时间与分数徽章的 HTML 片段。
 */

import { escapeHtml } from './dom.js';

const STATUS_META = {
  AC: { label: '通过', cls: 'ac' },
  WA: { label: '答案错误', cls: 'wa' },
  TLE: { label: '超时', cls: 'tle' },
  RE: { label: '运行错误', cls: 're' },
  CE: { label: '编译错误', cls: 'ce' },
  Pending: { label: '评测中', cls: 'muted' },
  Unsolved: { label: '未完成', cls: 'muted' },
};

export function statusBadge(status) {
  const meta = STATUS_META[status] || { label: status || '未知', cls: 'muted' };
  return `<span class="badge badge-${meta.cls}">${escapeHtml(meta.label)}</span>`;
}

export function typeBadge(type) {
  return type === 'exam'
    ? '<span class="badge badge-warning">考试</span>'
    : '<span class="badge badge-accent">练习</span>';
}

export function timeStatusBadge(status) {
  const map = {
    upcoming: ['未开始', 'muted'],
    ongoing: ['进行中', 'ac'],
    ended: ['已截止', 'muted'],
  };
  const [label, cls] = map[status] || ['未知', 'muted'];
  return `<span class="badge badge-${cls}">${label}</span>`;
}

export function bestStatusBadge(status) {
  if (status === 'AC') return '<span class="badge badge-ac">已掌握</span>';
  if (status && status !== 'Unsolved') return statusBadge(status);
  return '<span class="badge badge-muted">未挑战</span>';
}

export function scoreText(score) {
  const value = Number(score);
  if (!Number.isFinite(value)) return '—';
  return `${Math.round(value * 10) / 10}`;
}