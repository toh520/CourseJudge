"""
文件名: output_comparator.py
功能描述: 智能文本输出比对器模块，负责比对学生程序输出与标准答案是否一致，规避平台差异导致的误判。
遵循规范: 自动归一化 Windows/Linux 换行符差异、忽略行末空白与文件末尾多余空行后，判定 AC 或 WA。
"""

import re
from typing import Tuple


class OutputComparator:
    """
    智能文本输出比对器类
    用于判定学生程序的运行输出与题面标准答案在语义上是否一致。
    归一化策略 (按顺序执行):
        1. 统一换行符为 \n，消除 \r\n 与 \n 跨平台差异;
        2. 剔除行末与行首的空白符;
        3. 丢弃末尾多余的空行，保证仅凭有效内容定罪。
    """

    def compare(self, student_output: str, expected_output: str) -> Tuple[bool, str]:
        """
        比对学生输出与标准答案

        参数:
            student_output (str): 学生程序运行产生的实际标准输出文本
            expected_output (str): 题面提供的标准期望输出文本

        返回:
            tuple: (is_accepted, message)
                - is_accepted (bool): True 表示输出匹配 (AC)，False 表示不匹配 (WA)
                - message (str): 简洁的比对结果说明
        """
        normalized_student = self._normalize(student_output)
        normalized_expected = self._normalize(expected_output)

        if normalized_student == normalized_expected:
            return True, "答案正确 (Accepted)"
        return False, "答案错误 (Wrong Answer): 程序输出与标准答案不一致"

    def _normalize(self, text: str) -> str:
        """
        对输出文本执行跨平台归一化清洗

        参数:
            text (str): 原始输出文本 (可能为 None)

        返回:
            str: 归一化后的判定关键内容
        """
        if text is None:
            return ""
        # 1. 统一换行符，消除 Windows(\r\n) 与 Unix(\n) 差异
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # 2. 逐行剥离行首行尾空白，并过滤空行 (忽略末尾多余空行与行末空格)
        lines = [line.strip() for line in text.split("\n")]
        return "\n".join(lines).strip()