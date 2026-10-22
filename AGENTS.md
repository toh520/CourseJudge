# CourseJudge - AI Agent 开发规范与行为准则 (AGENTS.md)

> **重要声明 (面向所有参与开发的 AI Agent / 开发者)**：  
> 本文件是你在参与本项目开发、重构、修 Bug 或扩展功能时**必须首先阅读并无条件严格遵守的最高开发规范**。任何偏离本规范生成的代码、文件目录或配置均视为不合规。

---

## 1. 必读规范文档清单与阅读顺序

在执行任何代码编写前，AI Agent 必须按以下顺序完整阅读 [`docs/`](file:///d:/code/school/keshe/CourseJudge/docs) 目录下的全套工程文档：

1. [**`docs/开发规范与代码准则.md`**](file:///d:/code/school/keshe/CourseJudge/docs/%E5%BC%80%E5%8F%91%E8%A7%84%E8%8C%83%E4%B8%8E%E4%BB%A3%E7%A0%81%E5%87%86%E5%88%99.md)：**详细规范标准**。涵盖工程结构、分层职责、命名规范、中文注释、敏感信息与配置管理、数据库克制设计等。
2. [**`docs/系统设计与架构方案.md`**](file:///d:/code/school/keshe/CourseJudge/docs/%E7%B3%BB%E7%BB%9F%E8%AE%BE%E8%AE%A1%E4%B8%8E%E6%9E%B6%E6%9E%84%E6%96%B9%E6%A1%88.md)：**技术架构与模型**。掌握 PyWebView 桌面形态、编译器智能双模探针（系统 g++ / 内置便携版）、精简版 SQLite 实体结构设计。
3. [**`docs/需求规格说明书.md`**](file:///d:/code/school/keshe/CourseJudge/docs/%E9%9C%80%E6%B1%82%E8%A7%84%E6%A0%BC%E8%AF%B4%E6%98%8E%E4%B9%A6.md)：**业务需求**。理解教师端（班级/AI快速出题/测试用例生成/作业发布/大屏）、学生端（我的作业/自测与交卷/考后短板分析/专属强化训练题本/AI问答）。
4. [**`docs/业务接口与流程规范.md`**](file:///d:/code/school/keshe/CourseJudge/docs/%E4%B8%9A%E5%8A%A1%E6%8E%A5%E5%8F%A3%E4%B8%8E%E6%B5%81%E7%A8%8B%E8%A7%84%E8%8C%83.md)：**接口协议**。请求路径、入参、出参和流转时序。

---

## 2. Agent 核心开发规范与红线 (必背必遵)

### 🔴 规范 1：环境配置全局外部化（零硬编码原则）
- **核心思想**：绝不仅限于 API Key！**系统中所有易变的运行环境参数，严禁在代码中写死任何固定字符串或魔数**。
- **必须外部化配置的清单**：
  1. **LLM 配置**：`LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL_NAME` 等（必须统一在 `.env` 中维护，由 `config.py` 读取；调用必须严格使用标准 OpenAI 兼容协议格式 `openai.OpenAI(base_url=..., api_key=...)`）。
  2. **数据库配置**：`DATABASE_URL`（无论是本地 SQLite 还是后续切 MySQL，代码中一律读取配置变量，严禁写死路径）。
  3. **服务与系统配置**：服务端运行端口号、JWT 密钥、判题超时时间（`DEFAULT_TIME_LIMIT_MS`）、编译器探针工作模式等。
- **Git 提防泄露**：
  - 真实的私密配置仅在本地开发者私有的 `.env` 中维护；
  - 仓库仅提交 `.env.example` 占位模板；
  - 本地用于记录私密参数的临时数据文件（如 `llm.txt` 等）已被 `.gitignore` 严格忽略，**绝对禁止将包含真实密钥的内容写入文档或上传至 Git 仓库**！

---

### 🔴 规范 2：全局数据库设计“极致克制与精简”原则
- **核心思想**：系统所有数据表的设计，必须本着**“只满足核心功能闭环、绝不多加一个多余字段”**的极简原则。
- **设计范式**：
  - **用户表 (`users`)**：严禁添加手机号、邮箱、头像、微信号等与课设无关的冗余字段，仅保留 `id`, `username` (学号/工号), `real_name` (姓名), `password` (密码), `role` (身份: teacher/student), `created_at`。
  - **其他所有业务表**：班级表、作业表、题目表、用例表、提交表、强化训练题表等，同样严格保持精简实用，杜绝过度设计。
  - **密码明文存储**：为方便课设答辩演示、本地直接查验数据库与测试账号快速切换，**所有密码直接明文存储**，不引入复杂的加盐哈希或外部依赖。

---

### 🔴 规范 3：工程代码目录绝对隔离与纵深细分
- **根目录隔离**：根目录下仅保留 `docs/`、`AGENTS.md` 与配置说明，**所有业务源码、前端静态资产、测试用例与启动脚本必须统统收敛存放在 [`project/`](file:///d:/code/school/keshe/CourseJudge/project) 文件夹下**！
- **严禁代码“大乱炖”与扁平化堆砌**：
  1. `project/app/` 下必须保持工业级分层结构（`api/`, `services/`, `models/`, `schemas/`, `core/`, `ui/`）；
  2. **多级纵深细分要求（二级与三级目录动态演进）**：根据实际业务复杂度，各模块内部必须进一步细分，严禁在任何一个文件夹下平铺所有文件！例如：
     - `services/` 复杂时必须拆分二级目录：`services/judge/` (探针/沙箱/比对器)、`services/llm/` (客户端/生成器) 下设三级 `prompts/` 模板目录、`services/analytics/` (学情大屏聚合算法)；
     - `ui/` 前端资产必须拆分二级与三级目录：`ui/css/`、`ui/js/` (下设 `api/`, `components/`, `views/`)、`ui/libs/` (下设 `monaco/`, `echarts/` 独立子文件夹)；
  3. **“3-5 规则”自检红线**：任何子目录下若聚集超过 3~5 个同类或辅助文件，必须立即创建二级或三级子文件夹进行归类，坚决消除单层臃肿。

---

### 🔴 规范 4：命名规则与标准中文注释
- **命名标准 (PEP 8 增强)**：
  - Python 文件名与目录名：全小写蛇形（如 `judge_service.py`、`temp_judge/`）。
  - 类名：大驼峰（如 `JudgeService`、`CompilerProbe`）。
  - 函数与变量：全小写蛇形（如 `compile_and_run()`、`execution_time_ms`）。
  - 全局常量：全大写蛇形（如 `DEFAULT_TIMEOUT_SECONDS`）。
- **标准中文注释**：
  - 每个文件顶部与每个类必须有中文 Docstring 说明其职责；
  - 每个函数/方法必须有完整的中文 Docstring 说明其功能、入参及返回值类型；
  - 核心逻辑、算法边界及异常处理必须配有行内标准中文注释。

### 🔴 规范 5：团队协同开发与“一键启动脚本”持续同步维护
- **核心思想**：本项目为**多人团队协同开发**。团队成员拉取代码后必须能“零手动繁琐配置，双击一键启动”。
- **维护要求**：
  1. 根目录 [`一键启动.bat`](file:///d:/code/school/keshe/CourseJudge/%E4%B8%80%E9%94%AE%E5%90%AF%E5%8A%A8.bat) 与 [`project/start.bat`](file:///d:/code/school/keshe/CourseJudge/project/start.bat) 必须伴随开发流程**持续同步维护与测试**，确保始终可用；
  2. 启动脚本必须包含：自动检测 Python、自动创建 `.venv` 虚拟环境、国内镜像加速静默安装 `requirements.txt`、自动从 `.env.example` 复制初始化 `.env` 并在终端清晰打印中文指引；
  3. 当新增/修改依赖包、调整环境变量或变更启动入口时，必须使用项目内置 Skill (`maintain-startup-scripts`) 同步更新 `requirements.txt`、`.env.example` 和 `start.bat`。

---

## 3. Agent 开发自检清单 (Checklist)

AI Agent 在完成任何代码编写后，必须对照此清单自检：
- [ ] 检查代码是否全部位于 `project/` 目录下？（根目录无多余文件）
- [ ] 检查模块分层是否清晰合理？是否根据业务复杂度适时细分了二级/三级子目录（遵守“3-5规则”，拒绝单层平铺乱炖）？
- [ ] 检查代码中是否没有任何硬编码的 API Key、Base URL、数据库连接或魔数？
- [ ] 检查数据库表字段是否精简实用？没有冗余的邮箱、电话等无用字段？
- [ ] 检查密码是否直接作为明文字符串保存？
- [ ] 检查调用 LLM 是否严格采用 OpenAI 兼容格式？
- [ ] 检查所有新编写的类和函数是否都包含标准中文注释？
- [ ] 检查若有新增第三方库，是否已同步更新 `requirements.txt` 与启动脚本？
- [ ] 检查敏感数据文件（如 `llm.txt`, `.env`）是否已被排除在 git 跟踪外？
