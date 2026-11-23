/**
 * 文件名: auth.js
 * 功能描述: 登录视图。用户名 + 明文密码换取 JWT，成功后广播认证事件。
 */

import { api, setToken } from '../../api/client.js';
import { toast } from '../../components/base/toast.js';

/**
 * 渲染登录页
 * @param {HTMLElement} root
 */
export function render(root) {
  root.innerHTML = `
    <div class="auth-screen">
      <section class="auth-visual">
        <div class="auth-brand">
          <div class="brand-mark">&lt;/&gt;</div>
          <div>
            <div class="auth-brand-title">CourseJudge</div>
            <div class="auth-brand-sub">C++ 教学与评测</div>
          </div>
        </div>

        <div class="auth-intro">
          <h1 class="auth-headline">程序设计课堂</h1>
          <p class="auth-lead">在同一个工作台布置作业、编写代码、查看评测反馈。</p>
        </div>
        <figure class="fib-figure">
          <div class="fib-tiles" aria-hidden="true">
            <span>8</span><span>5</span><span>3</span><span>2</span><span>1</span><span>1</span>
          </div>
          <figcaption><span>斐波那契数列</span><code>F(n) = F(n−1) + F(n−2)</code></figcaption>
        </figure>
      </section>

      <aside class="auth-side">
        <div class="auth-card">
          <div class="mobile-brand">CourseJudge</div>
          <h2>登录工作台</h2>
          <p class="auth-sub">使用学号 / 工号与密码进入系统</p>

          <form class="auth-form" id="login-form" autocomplete="on">
            <div class="field">
              <label for="login-username">学号 / 工号</label>
              <input class="input" id="login-username" name="username" autocomplete="username" placeholder="例如 teacher" required>
            </div>
            <div class="field">
              <label for="login-password">密码</label>
              <input class="input" id="login-password" name="password" type="password" autocomplete="current-password" placeholder="请输入密码" required>
            </div>
            <div class="form-error hidden" id="login-error" role="alert"></div>
            <button class="btn btn-primary btn-block" type="submit" id="login-submit">进入 CourseJudge</button>
          </form>

          <details class="auth-hint">
            <summary>使用默认演示账号</summary>
            <p>选择身份填入账号，默认密码为 <code>123456</code>。</p>
            <div class="demo-roles">
              <button class="btn" type="button" data-demo="teacher">演示教师</button>
              <button class="btn" type="button" data-demo="student">演示学生</button>
            </div>
          </details>
        </div>
      </aside>
    </div>
  `;

  const form = root.querySelector('#login-form');
  const errorBox = root.querySelector('#login-error');
  const submit = root.querySelector('#login-submit');

  root.querySelectorAll('[data-demo]').forEach((button) => {
    button.addEventListener('click', () => {
      form.username.value = button.dataset.demo;
      form.password.value = '';
      form.password.focus();
    });
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorBox.classList.add('hidden');
    submit.disabled = true;
    submit.textContent = '正在验证…';

    const username = form.username.value.trim();
    const password = form.password.value;

    try {
      const result = await api.auth.login(username, password);
      setToken(result.access_token);
      const user = result.user || await api.auth.me();
      window.dispatchEvent(new CustomEvent('cj:authenticated', { detail: user }));
      toast(`欢迎回来，${user.real_name || user.username}`, 'success');
    } catch (err) {
      errorBox.textContent = err.message || '登录失败';
      errorBox.classList.remove('hidden');
      submit.disabled = false;
      submit.textContent = '进入 CourseJudge';
    }
  });

  root.querySelector('#login-username').focus();
}