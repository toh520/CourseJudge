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
            <div class="auth-brand-sub">Intelligent Code Judge</div>
          </div>
        </div>

        <h1 class="auth-headline">让每一次提交，<br>都成为<em>可解释的成长</em>。</h1>
        <p class="auth-lead">
          面向高校程序设计与算法课程的智能判题与教学辅助系统。
          教师高效编排作业与洞察学情，学生获得即时评测、短板诊断与专属强化训练。
        </p>

        <div class="auth-features">
          <div class="auth-feature">
            <div class="auth-feature-icon">⌘</div>
            <div><strong>智能双模编译器</strong><span>优先系统 g++，缺失时平滑降级内置便携版</span></div>
          </div>
          <div class="auth-feature">
            <div class="auth-feature-icon">✦</div>
            <div><strong>AI 出题与用例闭环</strong><span>标准解答真实运行回填，测试用例 100% 一致</span></div>
          </div>
          <div class="auth-feature">
            <div class="auth-feature-icon">◎</div>
            <div><strong>考后短板诊断</strong><span>定位薄弱知识点，一键生成专属强化题</span></div>
          </div>
        </div>
      </section>

      <aside class="auth-side">
        <div class="auth-card">
          <h1>登录工作台</h1>
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
            <div class="form-error hidden" id="login-error"></div>
            <button class="btn btn-primary btn-block" type="submit" id="login-submit">进入 CourseJudge</button>
          </form>

          <div class="auth-hint">
            首次运行会自动创建演示账号：<br>
            教师 <code>teacher / 123456</code>　学生 <code>student / 123456</code><br>
            登录后可使用教师账号创建班级，再用学生账号通过邀请码加入。
          </div>
        </div>
      </aside>
    </div>
  `;

  const form = root.querySelector('#login-form');
  const errorBox = root.querySelector('#login-error');
  const submit = root.querySelector('#login-submit');

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