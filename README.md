# CourseJudge 智能代码判题与教学辅助系统

> 🎓 **大学程序设计课程设计优秀项目**  
> 💻 **技术形态**：Python + FastAPI + PyWebView 原生桌面窗口 + Monaco Editor + ECharts  
> 🤖 **AI 赋能**：标准 OpenAI 兼容协议（DeepSeek 等大模型）驱动的智能出题、用例生成、短板诊断与强化题本推荐

---

## 📌 项目简介

**CourseJudge** 是一款面向高校程序设计教学场景的**现代化独立桌面端 C++ 智能代码判题与教学辅助系统**。系统融合了“本地桌面原生体验”、“智能双模编译器沙箱评测”与“大语言模型 (LLM) 助教”三大核心能力，全方位支撑教师教学管理与学生沉浸式编程实践：

- **👨‍🏫 教师端**：班级管理（6位邀请码）、练习/考试作业灵活发布、AI 结构化快速出题与标准代码自动校验、真实测试用例回填、ECharts 班级学情与薄弱知识点统计大屏。
- **👨‍🎓 学生端**：按班级查看练习与考试、Monaco Editor 语法高亮沉浸式编程工作台、在线编译与样例自测、考试单次防作弊交卷、考后 AI 深度复盘诊断与专属强化题本补弱。
- **🤖 全局 AI 助手**：右下角常驻悬浮抽屉，支持 SSE 流式打字机问答，随时随地答疑解惑。

---

## ✨ 核心特色与架构亮点

1. **🖥️ 独立桌面应用体验**：基于 **PyWebView** 打造现代独立窗口客户端，零浏览器标签杂乱干扰；内置自适应空闲端口探测与后端守护服务管理，一键启动即开即用。
2. **⚙️ 编译器智能双模自适应探针**：
   - 自动检测并优先复用系统环境变量中的 `g++`；
   - 若宿主机未安装任何 C++ 环境，自动平滑无感降级到项目内置便携绿色版 MinGW 编译器，**真正实现答辩演示在任何纯净 Windows 电脑上零配置评测**。
3. **🛡️ 纯文本 JSON 团队数据快照无损同步**：
   - 二进制 `.db` 文件不提交 Git，彻底消除代码合并冲突；
   - 提供 `storage/data_snapshot.json` 快照机制与 `--sync` / `--export` 工具，团队拉取代码后双击批处理脚本即可**秒级同步班级、作业与测试用例数据**。
4. **🔒 零硬编码与安全防泄露**：
   - 所有易变运行参数均由外部 `.env` 管理；
   - 私密 API Key 严格防泄露，测试与离线模式具备完全隔离的 Mock 兜底保证。

---

## 🚀 团队协同极简启动与操作指南

### 1. 克隆项目
```bash
git clone https://github.com/toh520/CourseJudge.git
cd CourseJudge
```

### 2. 日常启动与使用（根目录快捷批处理）

| 批处理脚本 | 作用说明 | 适用场景 |
| :--- | :--- | :--- |
| **`一键启动.bat`** | 自动创建虚拟环境、清华源同步依赖、初始化 `.env`、同步数据快照并拉起桌面客户端 | **日常开发与答辩演示首选用** |
| **`一键同步.bat`** | 仅同步 Python 依赖环境与最新的共享数据快照 | 每次 `git pull` 后需要快速对齐依赖和数据时使用 |
| **`一键导出数据.bat`** | 将本地录入的新题目、作业和测试用例导出为 `storage/data_snapshot.json` | 教师出题后，导出快照并提交 Git 与队友共享 |

> 💡 **提示**：如需体验 AI 智能出题、用例生成或考后短板诊断功能，请使用记事本打开 `project/.env`，填入您的大模型 `LLM_API_KEY` 即可。未配置 Key 时系统其他功能均 100% 正常运行。

---

## 👥 默认演示账号 (开箱即用)

为方便答辩与本地快速查验，系统密码采用明文极简存储，开箱即提供以下演示账号：

| 身份角色 | 登录学号/工号 | 登录密码 | 默认权限与场景 |
| :--- | :--- | :--- | :--- |
| **演示教师** | `teacher` | `123456` | 拥有默认班级 **CJ2026**，可发布作业、AI出题、查看大屏 |
| **演示学生** | `student` | `123456` | 已加入 **CJ2026** 班级，拥有待做练习作业与专属强化训练题本 |

---

## 📂 工程分层结构

所有业务源码与资产均严格收敛在 [`project/`](file:///d:/code/school/keshe/CourseJudge/project) 目录下，杜绝目录混乱堆砌：

```text
CourseJudge/
├── docs/                           # 完整工程文档体系
│   ├── 需求规格说明书.md
│   ├── 系统设计与架构方案.md
│   ├── 业务接口与流程规范.md
│   ├── 开发规范与代码准则.md
│   └── 开发计划与实施路线图.md
├── AGENTS.md                       # AI Agent 与开发者最高行为准则
├── 一键启动.bat                     # 根目录双击启动入口
├── 一键同步.bat                     # 根目录双击数据与依赖同步
├── 一键导出数据.bat                 # 根目录双击导出共享数据快照
└── project/                        # 业务工程收敛根目录
    ├── app/
    │   ├── api/                    # RESTful 控制层路由 (auth, classes, assignments, judge, ...)
    │   ├── core/                   # 核心基础 (config 配置、database 极简持久层、seed 同步器)
    │   ├── models/                 # SQLAlchemy 极简实体定义 (User, Class, Assignment, Problem, ...)
    │   ├── schemas/                # Pydantic 请求与响应结构校验
    │   ├── services/               # 核心业务服务
    │   │   ├── judge/              # 判题引擎 (探针 compiler_probe, 沙箱 runner, 比对器 comparator)
    │   │   ├── llm/                # AI 服务 (客户端 client, 生成器 generator, 提示词 prompts/)
    │   │   └── analytics/          # 学情大屏数据聚合分析
    │   └── ui/                     # 桌面端前端工程 (HTML, CSS, Monaco Editor, ECharts)
    ├── storage/                    # 数据持久与共享目录 (含 data_snapshot.json 共享快照)
    ├── compiler/                   # 内置便携版绿色 C++ 编译器 (无环境平滑降级)
    ├── tests/                      # 自动化测试用例集 (test_phase1 ~ test_phase6)
    ├── run.py                      # 桌面客户端启动总入口
    ├── start.bat                   # 核心启动脚本
    ├── sync.bat                    # 核心同步脚本
    ├── export_data.bat             # 核心导出脚本
    └── requirements.txt            # Python 依赖清单
```

---

## 🧪 自动化验收测试套件

系统在各个阶段均配备了高密度的自动化单元测试与集成验收测试用例，可进入 `project/` 目录运行验证：

```bash
cd project
.venv\Scripts\python tests/test_phase1.py   # Phase 1: 核心配置、数据库建表与 ORM 模型
.venv\Scripts\python tests/test_judge.py    # Phase 2: 双模探针、沙箱编译与五状态判定 (38/38)
.venv\Scripts\python tests/test_llm.py      # Phase 3: 大模型兼容协议、AI出题与诊断 (26/26)
.venv\Scripts\python tests/test_phase4.py   # Phase 4: 全部业务 RESTful API 与权限校验 (64/64)
.venv\Scripts\python tests/test_phase5.py   # Phase 5: 前端静态资产与无头浏览器真实渲染 (25/25)
.venv\Scripts\python tests/test_phase6.py   # Phase 6: 桌面入口、双模降级与快照同步 (4/4)
```

---

## 📄 开源许可证与声明

本项目仅供高校程序设计课程设计与教学研究使用。
