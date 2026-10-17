# 🎓 CourseJudge - 智能代码判题与教学辅助系统

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Desktop-PyWebView-0078D7?style=for-the-badge&logo=windows&logoColor=white" alt="PyWebView" />
  <img src="https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Judge-C%2B%2B17-00599C?style=for-the-badge&logo=c%2B%2B&logoColor=white" alt="C++" />
  <img src="https://img.shields.io/badge/Database-SQLite%203-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite" />
  <img src="https://img.shields.io/badge/AI-OpenAI%20%2F%20DeepSeek-FF6F00?style=for-the-badge&logo=openai&logoColor=white" alt="LLM" />
</p>

---

## 📖 项目简介 (Overview)

**CourseJudge** 是一款以 **Python** 作为主开发语言、采用 **PyWebView 原生独立桌面窗口**形态呈现的**智能代码判题与教学辅助系统**。

针对传统程序设计与算法课程教学中出题繁琐、批改耗时、个性化指导缺失的痛点，CourseJudge 围绕**“班级教学体系”**，聚焦于教师的作业发布管理与学生的在线做题评测。系统深度结合 **大语言模型 (LLM) API**，打造了**“智能命题与用例验证 $\to$ 在线受限判题 $\to$ 考后短板提炼 $\to$ 专属阶梯强化 $\to$ 班级宏观学情大屏”**的完整教学闭环。

系统内置**“编译器智能双模探针”**与**“项目级 SQLite 单文件数据库”**，无需用户在本地复杂配置 C++ 构建环境或数据库服务，实现**真正的“开箱即用、随拷随走、答辩不翻车”**。

---

## 🌟 核心功能矩阵 (Features)

### 👨‍🏫 教师端功能 (Teacher Portal)
- **班级教学管理**：创建班级并自动生成 6 位唯一专属邀请码，轻松管理班级学生名册。
- **灵活作业编排（双模式）**：
  - **练习模式**：学生提交后实时查看每组测试点的状态（AC/WA/TLE/RE/CE）与得分，支持多次修改优化。
  - **考试模式**：仅限正式单次交卷，答题期间隐藏详细测试点数据，支持在正式交卷前通过“自测运行”验证代码逻辑。
- **LLM 辅助快速出题**：自然语言输入出题意图，AI 自动生成标准 Markdown 题面及标准 C++ 解答。
- **测试用例 100% 正确闭环生成**：LLM 动态分析边界场景生成测试输入，后端自动调用本地编译器执行标准参考代码并抓取真实标准输出，杜绝“脏用例”。
- **班级整体学情与薄弱知识点大屏**：
  - 基于 ECharts 的数字化看板，展示应交/实交人数、成绩分布直方图、题目正答率漏斗；
  - 自动聚合计算全班失分最多的核心知识点 Top 榜（如：“全班 64% 学生在【动态规划-状态转移】上丢分”），辅助针对性备课讲评。

### 👨‍🎓 学生端功能 (Student Portal)
- **班级与“我的作业”大厅**：输入邀请码加入班级，按班级查看待做、进行中及已截止的作业列表。
- **Monaco 沉浸式编程工作台**：集成微软 VS Code 核心编辑器（Monaco Editor），提供专业级 C++ 语法高亮、自动括号补全与代码缩进。
- **受限自测运行（不计分）**：支持自定义测试输入，在本地沙箱安全执行并实时返回标准输出与耗时，供正式交卷前排错自查。
- **考后 LLM 深度短板诊断**：作业/考试截止后一键生成诊断报告，精准指出代码逻辑漏洞并提炼薄弱知识点标签。
- **专属强化训练题本 (闭环补强)**：在短板诊断下方，点击即可让 AI 动态生成针对该弱点的专属强化题目与测试用例，永久归档于个人题本，支持重复刷题。
- **全局 AI 智能助教问答**：支持流式打字机交互，随时为学生解答 C++ 语法疑惑、编译报错分析与算法思路启发。

### ⚙️ 核心技术创新点 (Technical Highlights)
1. **编译器智能双模自适应探针 (Smart Compiler Probe)**：
   - 优先探测操作系统是否配置系统级 `g++`；
   - 若目标电脑未安装 C++ 环境，自动平滑切换至项目内置精简便携版编译器（约 40~50MB），确保跨电脑免安装即可运行。
2. **数据库极致克制设计与无缝升级**：
   - 采用 SQLite 3 单文件存储，配合 SQLAlchemy 2.0 ORM；
   - 字段极致精简，拒绝任何冗余信息，密码直接明文存储便于直观调试；
   - 后续若需升级为局域网/公网 MySQL 共享库，仅需修改一行配置字符串。

---

## 🏗️ 目录工程结构 (Architecture)

本项目严格遵循工业级清晰分层，业务代码与文档绝对隔离：

```text
CourseJudge/
├── AGENTS.md                           # AI Agent 开发规范与行为准则 (最高规范)
├── 一键启动.bat                        # 团队成员快捷一键启动引导入口
├── README.md                           # 本项目总览手册 (本文件)
├── docs/                               # 规范与设计全套工程文档
│   ├── 需求规格说明书.md               # 业务需求与角色权限规格
│   ├── 系统设计与架构方案.md           # 技术架构、数据模型与生命周期
│   ├── 业务接口与流程规范.md           # 业务时序图与 RESTful API 接口定义
│   └── 开发规范与代码准则.md           # 目录分层、命名、中文注释与零硬编码规范
├── .agents/                            # 团队专属开发技能库 (Skills)
│   └── skills/
│       ├── frontend-design/            # Anthropic 官方高级前端美学设计技能
│       ├── maintain-startup-scripts/   # 一键启动脚本与环境持续同步技能
│       └── find-skills/                # 开源技能检索技能
└── project/                            # 业务源码主工程目录 (遵循标准分层架构)
    ├── app/                            # 业务核心源码
    │   ├── api/                        # 控制器层 (路由接口，纯请求转发与校验)
    │   ├── core/                       # 基础设施层 (配置读取、安全、数据库会话)
    │   ├── models/                     # SQLAlchemy 数据库实体表映射
    │   ├── schemas/                    # Pydantic 请求与响应验证 DTO
    │   ├── services/                   # 业务服务层 (判题引擎、LLM适配器、学情大屏聚合)
    │   └── ui/                         # PyWebView 桌面端前端静态资源 (HTML/CSS/JS)
    ├── compiler/                       # [可选] 精简绿色便携式 g++ 编译器 (~40-50MB)
    ├── storage/                        # 本地临时工作存储 (用例与临时编译目录)
    ├── .env.example                    # 环境变量配置模板
    ├── .gitignore                      # Git 严格忽略规则 (严防密钥泄露)
    ├── requirements.txt                # 精简明确的 Python 依赖清单
    ├── start.bat                       # project 目录环境自检与启动主脚本
    └── run.py                          # 桌面客户端主启动入口
```

---

## 🚀 团队快速上手指南 (Quick Start)

针对团队多人协作开发场景，系统提供了**全自动化的一键启动脚本**：

### 方式一：双击一键极速启动（推荐新手与团队成员）

1. **拉取仓库源码**：
   ```bash
   git clone https://github.com/toh520/CourseJudge.git
   cd CourseJudge
   ```
2. **双击启动**：
   直接在项目根目录下双击 **[`一键启动.bat`](file:///d:/code/school/keshe/CourseJudge/%E4%B8%80%E9%94%AE%E5%90%AF%E5%8A%A8.bat)**。  
   *脚本将全自动完成：检测 Python 环境 $\to$ 自动创建 `.venv` 虚拟环境 $\to$ 国内清华源静默安装依赖 $\to$ 自动从模板初始化 `.env` $\to$ 拉起原生桌面软件窗口！*

---

### 方式二：命令行手动启动

1. **进入工程目录**：
   ```bash
   cd project
   ```
2. **创建并激活虚拟环境**：
   ```bash
   python -m venv .venv
   .venv\Scripts\activate       # Windows 环境
   ```
3. **安装依赖包（国内清华源加速）**：
   ```bash
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```
4. **配置环境变量**：
   复制配置模板生成本地私密 `.env` 文件：
   ```bash
   copy .env.example .env
   ```
   用文本编辑器打开 `.env`，填入你的大模型 API Key（支持 DeepSeek / 阿里通义千问 / OpenAI 等兼容协议）。
5. **拉起客户端**：
   ```bash
   python run.py
   ```

---

## 🛠️ 核心开发规范与 AI 协作准则

本项目引入了严格的工程规范标准。任何参与本项目的开发者与 AI Agent 必须首先阅读根目录下的 [**`AGENTS.md`**](file:///d:/code/school/keshe/CourseJudge/AGENTS.md)，严格执行以下准则：
- **零硬编码原则**：所有大模型地址、API Key、数据库连接串及端口参数统统抽离至外部配置文件；
- **数据库极致精简原则**：拒绝任何与课设无关的冗余字段，密码明文存储便于直观调试；
- **目录绝对隔离**：所有代码严格位于 `project/` 目录下；
- **标准中文注释**：所有类、函数必须附带标准的中文 Docstring 说明。

---

## 📄 开源许可证 (License)

本项目遵循 [MIT License](https://opensource.org/licenses/MIT) 开源许可证。
