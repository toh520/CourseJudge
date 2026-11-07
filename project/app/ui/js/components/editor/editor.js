/**
 * 文件名: editor.js
 * 功能描述: Monaco 编辑器封装。优先加载本地 Monaco；若资源不可用则自动降级为
 *          等宽文本域，保证任何环境下都能正常编写代码。
 */

let monacoPromise = null;

/**
 * 加载 Monaco
 * @returns {Promise<object>}
 */
function loadMonaco() {
  if (window.monaco) return Promise.resolve(window.monaco);
  if (monacoPromise) return monacoPromise;
  if (!window.require) return Promise.reject(new Error('Monaco loader 未加载'));

  self.MonacoEnvironment = {
    getWorkerUrl() {
      return 'libs/monaco/vs/base/worker/workerMain.js';
    },
  };

  monacoPromise = new Promise((resolve, reject) => {
    try {
      window.require.config({ paths: { vs: 'libs/monaco/vs' } });
      window.require(['vs/editor/editor.main'], () => resolve(window.monaco), reject);
    } catch (err) {
      reject(err);
    }
  });
  return monacoPromise;
}

/**
 * 创建代码编辑器
 * @param {HTMLElement} container 容器
 * @param {object} options
 * @param {string} options.value 初始代码
 * @param {string} options.language 语言 (默认 cpp)
 * @param {boolean} options.readOnly 是否只读
 * @param {(value:string)=>void} options.onChange 内容变更回调
 * @returns {Promise<{getValue:Function,setValue:Function,setReadOnly:Function,dispose:Function,focus:Function,mode:string}>}
 */
export async function createEditor(container, { value = '', language = 'cpp', readOnly = false, onChange = null } = {}) {
  try {
    const monaco = await loadMonaco();
    if (!container.isConnected) {
      return emptyHandle();
    }

    monaco.editor.defineTheme('coursejudge-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [
        { token: 'comment', foreground: '6b7a90', fontStyle: 'italic' },
        { token: 'keyword', foreground: '7aa2ff' },
        { token: 'string', foreground: '9ece6a' },
        { token: 'number', foreground: 'e0af68' },
        { token: 'type', foreground: '7dcfff' },
      ],
      colors: {
        'editor.background': '#080b11',
        'editor.foreground': '#d7e3f4',
        'editorLineNumber.foreground': '#3b4a61',
        'editorLineNumber.activeForeground': '#8aa0bd',
        'editor.lineHighlightBackground': '#0e1420',
        'editor.selectionBackground': '#264f78',
        'editorCursor.foreground': '#4c8dff',
        'editorIndentGuide.background1': '#1b2433',
      },
    });

    container.innerHTML = '';
    const editor = monaco.editor.create(container, {
      value,
      language,
      theme: 'coursejudge-dark',
      automaticLayout: true,
      fontSize: 13.5,
      fontFamily: 'Cascadia Code, JetBrains Mono, Consolas, monospace',
      lineHeight: 22,
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      renderWhitespace: 'selection',
      tabSize: 4,
      insertSpaces: true,
      readOnly,
      padding: { top: 12, bottom: 12 },
      smoothScrolling: true,
      cursorBlinking: 'smooth',
    });

    if (onChange) editor.onDidChangeModelContent(() => onChange(editor.getValue()));

    return {
      getValue: () => editor.getValue(),
      setValue: (nextValue) => editor.setValue(nextValue || ''),
      setReadOnly: (nextReadOnly) => editor.updateOptions({ readOnly: Boolean(nextReadOnly) }),
      dispose: () => editor.dispose(),
      focus: () => editor.focus(),
      layout: () => editor.layout(),
      mode: 'monaco',
    };
  } catch (err) {
    console.warn('Monaco 加载失败，降级为文本域：', err);
    return createFallbackEditor(container, { value, readOnly, onChange });
  }
}

function createFallbackEditor(container, { value, readOnly, onChange }) {
  container.innerHTML = '';
  const textarea = document.createElement('textarea');
  textarea.className = 'code-fallback';
  textarea.spellcheck = false;
  textarea.value = value || '';
  textarea.readOnly = Boolean(readOnly);
  if (onChange) textarea.addEventListener('input', () => onChange(textarea.value));
  container.appendChild(textarea);

  return {
    getValue: () => textarea.value,
    setValue: (nextValue) => { textarea.value = nextValue || ''; },
    setReadOnly: (nextReadOnly) => { textarea.readOnly = Boolean(nextReadOnly); },
    dispose: () => {},
    focus: () => textarea.focus(),
    layout: () => {},
    mode: 'textarea',
  };
}

function emptyHandle() {
  return {
    getValue: () => '',
    setValue: () => {},
    setReadOnly: () => {},
    dispose: () => {},
    focus: () => {},
    layout: () => {},
    mode: 'empty',
  };
}

/**
 * 默认 C++ 起始模板
 * @param {string} title 题目标题
 * @returns {string}
 */
export function cppTemplate(title = '') {
  return `#include <iostream>\n#include <vector>\n#include <algorithm>\nusing namespace std;\n\nint main() {\n    // ${title || '在此编写你的代码'}\n\n    return 0;\n}\n`;
}