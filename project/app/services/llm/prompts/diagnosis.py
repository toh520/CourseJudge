"""
文件名: diagnosis.py
功能描述: 考后学情短板诊断提示词模板。
遵循规范: 引导模型输出结构化薄弱知识点、代码证据与学习指导，禁止泛泛而谈。
"""

import json
from typing import Any, Dict, List

DIAGNOSIS_SYSTEM_PROMPT = """你是 CourseJudge 智能判题系统的 C++ 教学诊断专家。
你的任务是根据学生未拿满分的题目、提交源码与评测错误信息，诊断其真实的知识薄弱点。

你必须只输出一个合法的 JSON 对象，不要输出 Markdown 代码围栏或任何解释文字。
JSON 必须严格包含以下字段:
{
  "summary": "整体诊断摘要",
  "weak_points": [
    {
      "tag": "薄弱知识点标签，例如 动态规划-状态转移",
      "evidence": "来自代码或评测结果的具体证据",
      "suggestion": "针对该薄弱点的具体改进建议"
    }
  ],
  "learning_guidance": "后续学习路径与复习指导"
}

硬性要求:
1. weak_points 至少包含 1 项（若确实没有明显薄弱点，可给出一个最需要巩固的方向）。
2. tag 必须具体到可教学的知识点，避免“编程能力不足”这类空泛表述。
3. evidence 必须引用学生代码或评测状态中的具体现象。
4. 诊断语言面向学生，清晰、具体、可执行。"""


def build_diagnosis_prompt(assignment_title: str, submissions: List[Dict[str, Any]]) -> str:
    """
    构造考后短板诊断的用户提示词

    参数:
        assignment_title (str): 作业/考试名称
        submissions (List[Dict[str, Any]]): 已裁剪的学生提交摘要列表

    返回:
        str: 完整的用户提示词
    """
    submissions_text = json.dumps(submissions, ensure_ascii=False, indent=2)
    return f"""作业/考试名称: {assignment_title}

以下为学生未拿满分的题目记录（包含题目标题、知识点、评测状态、得分、源码与错误信息）:
{submissions_text}

请综合这些信息，诊断学生的逻辑缺陷与核心薄弱知识点，并给出可执行的改进建议。"""