/**
 * 文件名: client.js
 * 功能描述: 前端 API 客户端。统一封装 JWT 注入、错误解析、401 登出广播与 SSE 流式读取。
 */

const TOKEN_KEY = 'coursejudge_token';
let token = '';

try {
  token = window.localStorage.getItem(TOKEN_KEY) || '';
} catch (err) {
  token = '';
}

/**
 * 设置/清除本地 JWT
 * @param {string} value
 */
export function setToken(value) {
  token = value || '';
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch (err) {
    console.warn('无法写入 localStorage', err);
  }
}

/**
 * 获取当前 JWT
 * @returns {string}
 */
export function getToken() {
  return token;
}

async function parseBody(response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch (err) {
    return text;
  }
}

function errorMessage(data, status) {
  if (data && typeof data === 'object') {
    if (typeof data.detail === 'string') return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map((item) => item.msg || JSON.stringify(item)).join('；');
    }
    if (typeof data.message === 'string') return data.message;
  }
  if (typeof data === 'string' && data.trim()) return data;
  return `请求失败（HTTP ${status}）`;
}

/**
 * 发起 API 请求
 * @param {string} path /api/v1 之后的路径
 * @param {{method?:string, body?:any, headers?:object}} options
 * @returns {Promise<any>}
 */
async function request(path, options = {}) {
  const { method = 'GET', body, headers = {} } = options;
  const response = await fetch(`/api/v1${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  const data = await parseBody(response);

  if (!response.ok) {
    if (response.status === 401) {
      setToken('');
      window.dispatchEvent(new CustomEvent('cj:unauthorized'));
    }
    const error = new Error(errorMessage(data, response.status));
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

const get = (path) => request(path);
const post = (path, body) => request(path, { method: 'POST', body });

export const api = {
  system: {
    status: () => get('/system/status'),
  },
  auth: {
    login: (username, password) => post('/auth/login', { username, password }),
    me: () => get('/auth/me'),
  },
  classes: {
    my: () => get('/classes/my'),
    create: (name) => post('/classes', { name }),
    join: (inviteCode) => post('/classes/join', { invite_code: inviteCode }),
    students: (classId) => get(`/classes/${classId}/students`),
  },
  assignments: {
    create: (payload) => post('/assignments', payload),
    byClass: (classId) => get(`/assignments/class/${classId}`),
    detail: (assignmentId) => get(`/assignments/${assignmentId}`),
    problems: (assignmentId) => get(`/assignments/${assignmentId}/problems`),
    dashboard: (assignmentId) => get(`/assignments/${assignmentId}/dashboard`),
  },
  judge: {
    runTest: (payload) => post('/judge/run-test', payload),
    submit: (payload) => post('/judge/submit', payload),
  },
  training: {
    my: () => get('/training/my'),
    detail: (trainingId) => get(`/training/${trainingId}`),
    submit: (trainingId, code) => post(`/training/${trainingId}/submit`, { code }),
  },
  llm: {
    generateProblem: (payload) => post('/llm/generate-problem', payload),
    generateTestcases: (payload) => post('/llm/generate-testcases', payload),
    diagnose: (assignmentId) => post('/llm/diagnose-assignment', { assignment_id: assignmentId }),
    generateTraining: (payload) => post('/llm/generate-training-problem', payload),
  },
};

/**
 * 发起 SSE 流式对话
 * @param {string} message 本次提问
 * @param {Array<{role:string,content:string}>} history 历史消息
 * @param {(delta:string)=>void} onDelta 增量回调
 * @param {AbortSignal} signal 取消信号
 * @returns {Promise<string>} 完整回复
 */
export async function streamChat(message, history, onDelta, signal) {
  const response = await fetch('/api/v1/llm/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, history }),
    signal,
  });

  if (!response.ok) {
    const data = await parseBody(response);
    if (response.status === 401) {
      setToken('');
      window.dispatchEvent(new CustomEvent('cj:unauthorized'));
    }
    throw new Error(errorMessage(data, response.status));
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let fullText = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split('\n\n');
    buffer = events.pop() || '';

    for (const event of events) {
      const line = event.split('\n').find((item) => item.startsWith('data:'));
      if (!line) continue;
      const payload = line.slice(5).trim();
      if (!payload || payload === '[DONE]') continue;

      let parsed;
      try {
        parsed = JSON.parse(payload);
      } catch (err) {
        continue;
      }
      if (parsed.error) throw new Error(parsed.error);
      if (parsed.delta) {
        fullText += parsed.delta;
        onDelta(parsed.delta);
      }
    }
  }

  return fullText;
}