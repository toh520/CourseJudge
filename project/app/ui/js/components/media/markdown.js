/**
 * 文件名: markdown.js
 * 功能描述: 安全的轻量 Markdown 渲染器。支持标题、列表、引用、代码块、行内代码、
 *          粗体、斜体、链接与分割线，所有文本先做 HTML 转义以防注入。
 */

import { escapeHtml } from '../base/dom.js';

/**
 * 渲染 Markdown 为 HTML
 * @param {string} source 原始文本
 * @returns {string}
 */
export function renderMarkdown(source) {
  if (!source) return '';

  const codeBlocks = [];
  let text = String(source).replace(/\r\n?/g, '\n');

  // 先提取围栏代码块，避免其中的 Markdown 符号被误解析
  text = text.replace(/```([\w-]*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const html = `<pre><code class="language-${escapeHtml(lang || 'text')}">${escapeHtml(code.replace(/\n$/, ''))}</code></pre>`;
    const index = codeBlocks.push(html) - 1;
    return `\u0000CB${index}\u0000`;
  });

  text = escapeHtml(text);
  const lines = text.split('\n');
  const out = [];
  let paragraph = [];
  let listType = null;
  let listItems = [];

  const inline = (value) => renderInline(value);

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const content = paragraph.join(' ').trim();
    if (content) {
      if (/^\u0000CB\d+\u0000$/.test(content)) out.push(content);
      else out.push(`<p>${inline(content)}</p>`);
    }
    paragraph = [];
  };

  const flushList = () => {
    if (!listType) return;
    const tag = listType === 'ol' ? 'ol' : 'ul';
    out.push(`<${tag}>${listItems.map((item) => `<li>${inline(item)}</li>`).join('')}</${tag}>`);
    listType = null;
    listItems = [];
  };

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      flushParagraph();
      flushList();
      continue;
    }

    if (/^\u0000CB\d+\u0000$/.test(trimmed)) {
      flushParagraph();
      flushList();
      out.push(trimmed);
      continue;
    }

    let matched;

    if ((matched = line.match(/^(#{1,4})\s+(.*)$/))) {
      flushParagraph();
      flushList();
      const level = matched[1].length;
      out.push(`<h${level}>${inline(matched[2])}</h${level}>`);
      continue;
    }

    if (/^\s*(---+|\*\*\*+)\s*$/.test(line)) {
      flushParagraph();
      flushList();
      out.push('<hr>');
      continue;
    }

    if ((matched = line.match(/^>\s?(.*)$/))) {
      flushParagraph();
      flushList();
      out.push(`<blockquote>${inline(matched[1])}</blockquote>`);
      continue;
    }

    if ((matched = line.match(/^\s*[-*+]\s+(.*)$/))) {
      flushParagraph();
      if (listType && listType !== 'ul') flushList();
      listType = 'ul';
      listItems.push(matched[1]);
      continue;
    }

    if ((matched = line.match(/^\s*\d+\.\s+(.*)$/))) {
      flushParagraph();
      if (listType && listType !== 'ol') flushList();
      listType = 'ol';
      listItems.push(matched[1]);
      continue;
    }

    flushList();
    paragraph.push(trimmed);
  }

  flushParagraph();
  flushList();

  return out.join('\n').replace(/\u0000CB(\d+)\u0000/g, (_, index) => codeBlocks[Number(index)] || '');
}

/**
 * 行内格式渲染
 * @param {string} text 已转义文本
 * @returns {string}
 */
function renderInline(text) {
  const inlineCodes = [];
  let value = text.replace(/`([^`]+)`/g, (_, code) => {
    const index = inlineCodes.push(`<code>${code}</code>`) - 1;
    return `\u0000IC${index}\u0000`;
  });

  value = value.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, label, url) => {
    const safeUrl = /^(https?:\/\/|#)/i.test(url) ? url : '#';
    return `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer">${label}</a>`;
  });

  value = value.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  value = value.replace(/\*([^*]+)\*/g, '<em>$1</em>');

  return value.replace(/\u0000IC(\d+)\u0000/g, (_, index) => inlineCodes[Number(index)] || '');
}