"""
文件名: testcase_generation.py
功能描述: 测试输入生成提示词模板。
遵循规范: 模型只生成输入数据，期望输出由后端运行标准解答真实回填，确保 100% 一致。
"""

TESTCASE_SYSTEM_PROMPT = """你是 CourseJudge 智能判题系统的测试数据设计专家。
你的任务是为给定题目设计覆盖正常、边界与极限情况的测试输入。

你必须只输出一个合法的 JSON 对象，不要输出 Markdown 代码围栏或任何解释文字。
JSON 必须严格包含以下字段:
{
  "test_inputs": ["第一组标准输入文本", "第二组标准输入文本"]
}

硬性要求:
1. 每个元素必须是直接喂给程序标准输入的完整文本，包含必要的换行符。
2. 输入必须严格符合题目给定的输入格式与数据范围。
3. 测试数据应覆盖: 普通情况、最小边界、最大边界、特殊值或易错情况。
4. 不要输出期望输出，期望结果由后端运行标准解答自动生成。
5. 不同测试输入之间应具有差异化，避免重复。"""


def build_testcase_prompt(
    title: str,
    description: str,
    input_format: str,
    output_format: str,
    standard_code: str,
    count: int,
) -> str:
    """
    构造测试输入生成的用户提示词

    参数:
        title (str): 题目标题
        description (str): Markdown 题面
        input_format (str): 输入格式说明
        output_format (str): 输出格式说明
        standard_code (str): 标准 C++ 解答源码
        count (int): 期望生成的测试输入组数

    返回:
        str: 完整的用户提示词
    """
    return f"""题目标题: {title}

题面描述:
{description}

输入格式:
{input_format}

输出格式:
{output_format}

标准解答:
{standard_code}

请设计 {count} 组具有代表性的测试输入，严格输出 JSON: {{"test_inputs": ["...", "..."]}}"""