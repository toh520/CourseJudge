# CourseJudge 智能代码判题与教学辅助系统 (Project 源码目录)

本项目是一个以 Python 为主开发语言、采用 PyWebView 原生桌面独立窗口形态的智能 C++ 代码判题与教学辅助系统。

## 目录分层架构

```text
project/
├── app/                  # 核心业务源码 (遵循清晰分层架构)
│   ├── api/              # API 路由控制器 (Controller)
│   ├── core/             # 基础设施 (配置/数据库/安全)
│   ├── models/           # SQLAlchemy 数据库实体模型
│   ├── schemas/          # Pydantic 数据传输模型
│   ├── services/         # 核心业务服务 (判题引擎、LLM服务、大屏聚合)
│   └── ui/               # 桌面客户端界面资源 (HTML/CSS/JS, Monaco, ECharts)
├── compiler/             # [可选内置] 绿色便携式 g++ 编译器 (~40-50MB)
├── storage/              # 本地文件存储 (用例与临时编译目录)
├── .env.example          # 环境变量模板 (复制为 .env 填写私密密钥)
├── requirements.txt      # Python 依赖清单
└── run.py                # 桌面客户端启动入口
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

### 3. 一键启动桌面客户端
```bash
python run.py
```
系统将自动执行编译器自适应探针，启动内置服务并弹出原生桌面客户端窗口。
