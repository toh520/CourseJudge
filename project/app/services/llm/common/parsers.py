"""
文件名: parsers.py
功能描述: LLM 文本输出的 JSON 容错解析工具。
遵循规范: 兼容模型直接输出 JSON、Markdown 代码围栏包裹 JSON、以及 JSON 前后夹杂说明文字的场景。
"""

import json
from typing import Any, Dict, Optional


class LLMResponseFormatError(ValueError):
    """LLM 返回内容无法解析为预期 JSON 对象时抛出的异常"""


def strip_code_fence(text: str) -> str:
    """
    剥离模型输出外层的 Markdown 代码围栏 (```json ... ```)

    参数:
        text (str): 模型原始输出文本

    返回:
        str: 去除围栏后的正文
    """
    cleaned = (text or "").strip()
    if not cleaned.startswith("```"):
        return cleaned

    lines = cleaned.splitlines()
    # 去掉首行的 ``` 或 ```json 标记
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    # 去掉末行的 ``` 结束标记
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def extract_json_object(text: str) -> Dict[str, Any]:
    """
    从模型输出中提取第一个完整的 JSON 对象

    参数:
        text (str): 模型原始输出文本

    返回:
        dict: 解析成功的 JSON 对象

    异常:
        LLMResponseFormatError: 未找到 JSON 对象或对象无法解析
    """
    if not text or not text.strip():
        raise LLMResponseFormatError("模型返回内容为空")

    cleaned = text.strip()

    # 1. 先尝试直接解析（含代码围栏剥离后的内容）
    for candidate in (cleaned, strip_code_fence(cleaned)):
        parsed = _try_json_loads(candidate)
        if isinstance(parsed, dict):
            return parsed

    # 2. 再尝试扫描文本中第一个花括号平衡的 JSON 对象
    candidate = _find_balanced_object(cleaned)
    if candidate:
        parsed = _try_json_loads(candidate)
        if isinstance(parsed, dict):
            return parsed

    raise LLMResponseFormatError("未能在模型返回中找到合法的 JSON 对象")


def _try_json_loads(text: str) -> Optional[Any]:
    """
    安全执行 json.loads，失败时返回 None 而不抛出异常

    参数:
        text (str): 待解析文本

    返回:
        Optional[Any]: 解析结果，失败为 None
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def _find_balanced_object(text: str) -> Optional[str]:
    """
    扫描文本中第一个花括号平衡的 JSON 对象片段

    解析时会正确跳过字符串内部的花括号与转义字符，避免被题面文本误导。

    参数:
        text (str): 待扫描文本

    返回:
        Optional[str]: 平衡的 JSON 对象字符串，未找到为 None
    """
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False

        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]

        # 当前起点未找到平衡对象，继续尝试下一个花括号
        start = text.find("{", start + 1)

    return None