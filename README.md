# CourseJudge 智能代码判题与教学辅助系统

> ⚠️ **项目状态**：🚧 **积极开发中 (In Active Development)**  
> 本项目为大学程序设计课程设计项目，目前已完成全套系统需求规格设计、系统架构方案设计与团队开发规范制定，核心业务功能正在逐步开发与迭代中。

---

## 📌 项目定位

CourseJudge 是一个以 **Python** 作为主开发语言、采用 **PyWebView 独立桌面窗口**形态呈现的智能 C++ 代码判题与教学辅助软件。旨在围绕班级教学体系，通过大语言模型 (LLM) 赋能教师出题与学生考后短板巩固。

---

## 📚 项目工程与设计文档

在开始开发或查阅详细设计前，请先查阅以下文档：

- 🤖 [**`AGENTS.md`**](file:///d:/code/school/keshe/CourseJudge/AGENTS.md)：AI Agent 与团队开发者必须严格遵守的行为规范与开发准则
- 📋 [**`docs/需求规格说明书.md`**](file:///d:/code/school/keshe/CourseJudge/docs/%E9%9C%80%E6%B1%82%E8%A7%84%E6%A0%BC%E8%AF%B4%E6%98%8E%E4%B9%A6.md)：系统业务需求与角色功能范围
- 🏛️ [**`docs/系统设计与架构方案.md`**](file:///d:/code/school/keshe/CourseJudge/docs/%E7%B3%BB%E7%BB%9F%E8%AE%BE%E8%AE%A1%E4%B8%8E%E6%9E%B6%E6%9E%84%E6%96%B9%E6%A1%88.md)：技术选型、数据库模型设计与编译器探针机制
- 🔌 [**`docs/业务接口与流程规范.md`**](file:///d:/code/school/keshe/CourseJudge/docs/%E4%B8%9A%E5%8A%A1%E6%8E%A5%E5%8F%A3%E4%B8%8E%E6%B5%81%E7%A8%8B%E8%A7%84%E8%8C%83.md)：业务时序流转与 API 接口定义
- 📏 [**`docs/开发规范与代码准则.md`**](file:///d:/code/school/keshe/CourseJudge/docs/%E5%BC%80%E5%8F%91%E8%A7%84%E8%8C%83%E4%B8%8E%E4%BB%A3%E7%A0%81%E5%87%86%E5%88%99.md)：分层架构、中文注释、零硬编码与 Git 防泄露规范

---

## 🚀 团队协同本地运行

团队成员拉取代码后，在项目根目录下双击批处理脚本即可自动安装依赖并初始化：

1. **拉取代码**：
   ```bash
   git clone https://github.com/toh520/CourseJudge.git
   cd CourseJudge
   ```
2. **一键启动**：
   双击根目录下的 **[`一键启动.bat`](file:///d:/code/school/keshe/CourseJudge/%E4%B8%80%E9%94%AE%E5%90%AF%E5%8A%A8.bat)**。  
   *脚本将自动检查 Python 环境、自动创建 `.venv` 虚拟环境、国内镜像静默安装依赖并初始化配置。*

---

> 📝 **说明**：详细的功能展示、使用截图与操作手册将在各模块开发完成并通过全面测试后统一补充完善。
