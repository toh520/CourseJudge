"""
文件名: training_generation.py
功能描述: 针对薄弱知识点生成专属强化训练题的提示词模板。
遵循规范: 生成的题目需与薄弱点强相关，附带标准解答与测试输入，交由后端真实验证。
"""

TRAINING_SYSTEM_PROMPT = """你是 CourseJudge 智能判题系统的个性化训练题设计专家。
你的任务是为学生针对某个薄弱知识点，设计一道难度适中的阶梯式巩固题。

你必须只输出一个合法的 JSON 对象，不要输出 Markdown 代码围栏或任何解释文字。
JSON 必须严格包含以下字段:
{
  "title": "强化题标题，不超过 100 字",
  "description": "Markdown 格式的完整题面",
  "input_format": "输入格式说明",
  "output_format": "输出格式说明",
  "sample_input": "公开样例输入文本",
  "sample_output": "公开样例输出文本",
  "time_limit_ms": 1000,
  "memory_limit_mb": 256,
  "knowledge_tag": "所针对的薄弱知识点标签",
  "standard_code": "完整、可直接编译运行的 C++17 标准解答源码",
  "test_inputs": ["测试输入1", "测试输入2"]
}

硬性要求:
1. standard_code 必须从标准输入读取、向标准输出打印，不得包含文件读写或系统调用。
2. 题目必须直接针对给定薄弱知识点，难度略低于原错题，帮助学生建立信心。
3. test_inputs 提供 3~5 组覆盖边界情况的完整标准输入文本。
4. 样例输入输出必须与 standard_code 的实际行为一致。"""


def build_training_prompt(
    weak_point: str,
    source_assignment_title: str = "",
    test_count: int = 4,
) -> str:
    """
    构造专属强化题生成的用户提示词

    参数:
        weak_point (str): 学生薄弱知识点标签
        source_assignment_title (str): 来源作业/考试名称，可为空
        test_count (int): 期望生成的测试输入组数

    返回:
        str: 完整的用户提示词
    """
    source_text = source_assignment_title.strip() or "综合练习"
    return f"""学生薄弱知识点: {weak_point}
来源作业/考试: {source_text}

请针对该薄弱知识点设计 1 道阶梯式巩固题，并附带可直接编译运行的标准 C++17 解答，
以及 {test_count} 组覆盖边界情况的测试输入。严格输出系统提示中规定的 JSON 结构。"""