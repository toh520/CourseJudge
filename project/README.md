# CourseJudge 智能代码判题与教学辅助系统 (Project 源码目录)

本项目是一个以 Python 为主开发语言、采用 PyWebView 原生桌面独立窗口形态的智能 C++ 代码判题与教学辅助系统。

## 目录分层架构

```text
project/
├── app/                  # 核心业务源码 (遵循清晰分层架构)
│   ├── api/              # RESTful API 路由控制器
│   ├── core/             # 配置 / 数据库 / 安全 / 演示账号初始化
│   ├── models/           # SQLAlchemy 数据库实体模型
│   ├── services/         # judge/ 判题引擎、llm/ AI 出题与诊断
│   └── ui/               # 桌面客户端界面资源
│       ├── css/          # 设计令牌、布局与组件样式
│       ├── js/api/       # 前端 API 客户端与 SSE 流式封装
│       ├── js/components/# 编辑器、图表、Markdown、弹窗、AI 助手
│       ├── js/views/     # 登录、教师、学生、班级、强化训练视图
│       └── libs/         # 本地 Monaco Editor 与 ECharts
├── compiler/             # [可选内置] 绿色便携式 g++ 编译器 (~40-50MB)
├── storage/              # 本地文件存储 (用例与临时编译目录)
├── tests/                # Phase 1~5 自动化验收脚本
├── .env.example          # 环境变量模板 (复制为 .env 填写私密密钥)
├── requirements.txt      # Python 依赖清单
└── run.py                # [Phase 6] PyWebView 桌面客户端启动入口
```

## 快速上手

### 1. 安装环境依赖
推荐使用 Python 3.10 及以上环境：
```bash
pip install -r requirements.txt
```

### 2. 配置环境变量
复制 `.env.example` 为 `.env`：
```bash
copy .env.example .env
```
用文本编辑器打开 `.env`，填入你的大模型 `LLM_API_KEY`（如 DeepSeek、通义千问等）。
未配置 Key 时，非 AI 功能（登录、班级、判题、学情大屏）仍可正常使用。

### 3. 开发调试启动 Web 工作台
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
浏览器访问：<http://127.0.0.1:8000/ui/>

首次启动且 `users` 表为空时，会自动创建演示账号：

| 角色 | 账号 | 密码 |
| :--- | :--- | :--- |
| 教师 | `teacher` | `123456` |
| 学生 | `student` | `123456` |

教师登录后可创建班级并获取 6 位邀请码；学生登录后凭邀请码加入班级。
可通过 `.env` 中的 `SEED_DEMO_ACCOUNTS=false` 关闭演示账号自动创建。

### 4. 桌面客户端启动 (Phase 6)
`project/run.py` 将在 Phase 6 完成 FastAPI 后台线程 + PyWebView 原生窗口整合。
在此之前，请使用上面的 uvicorn 开发调试方式；`start.bat` 也会在 Phase 6 同步更新。

## 开发阶段自动化验收

```bash
# Phase 1: 配置、数据库与数据模型
python tests/test_phase1.py

# Phase 2: C++ 判题引擎与编译器双模探针
python tests/test_judge.py

# Phase 3: LLM 服务与智能闭环 (默认使用假响应，不消耗 token)
python tests/test_llm.py

# Phase 4: RESTful API 全链路与安全/权限校验
python tests/test_phase4.py

# Phase 5: 前端静态资源、JS 语法与无头浏览器真实渲染
python tests/test_phase5.py

# 可选: 追加一次真实模型冒烟 (会消耗 token)
# PowerShell: $env:RUN_REAL_LLM_TESTS=1; python tests/test_llm.py
# CMD:        set RUN_REAL_LLM_TESTS=1 && python tests/test_llm.py
```