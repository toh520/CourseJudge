"""
文件名: assistant.py
功能描述: 首页 AI 智能助教多轮对话与流式输出服务。
遵循规范: 统一注入教学系统提示词，限制历史消息条数，支持普通回复与 SSE 打字机流式输出。
"""

from typing import Dict, Iterator, List, Optional

from app.core.config import settings
from app.services.llm.client import LLMClient
from app.services.llm.prompts.assistant import ASSISTANT_SYSTEM_PROMPT


class AssistantService:
    """
    AI 助教对话服务

    对外提供:
        - chat(): 一次性返回完整回复;
        - chat_stream(): 逐片产出回复增量，供 FastAPI SSE 接口使用。
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        参数:
            llm_client (Optional[LLMClient]): 可注入的 LLM 客户端
        """
        self.llm = llm_client or LLMClient()

    def chat(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        发起一轮 AI 助教问答并返回完整回复

        参数:
            message (str): 学生/教师本次提问
            history (Optional[List[Dict[str, str]]]): 历史多轮消息

        返回:
            str: 模型完整回复
        """
        messages = self._build_messages(message, history)
        return self.llm.chat(messages)

    def chat_stream(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Iterator[str]:
        """
        发起一轮 AI 助教问答并逐片产出回复

        参数:
            message (str): 学生/教师本次提问
            history (Optional[List[Dict[str, str]]]): 历史多轮消息

        返回:
            Iterator[str]: 文本增量迭代器
        """
        messages = self._build_messages(message, history)
        yield from self.llm.chat_stream(messages)

    def _build_messages(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]],
    ) -> List[Dict[str, str]]:
        """
        组装系统提示词、历史消息与本次提问

        参数:
            message (str): 本次提问
            history (Optional[List[Dict[str, str]]]): 历史消息

        返回:
            List[Dict[str, str]]: OpenAI 格式消息列表

        异常:
            ValueError: 提问为空
        """
        if not message or not message.strip():
            raise ValueError("提问内容不能为空")

        max_history = max(0, int(settings.LLM_MAX_HISTORY_MESSAGES))
        recent_history = (history or [])[-max_history:] if max_history else []

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": ASSISTANT_SYSTEM_PROMPT}
        ]
        for item in recent_history:
            role = item.get("role")
            content = item.get("content")
            # 仅接受合法的用户/助手消息，过滤异常历史数据
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": str(content)})

        messages.append({"role": "user", "content": message})
        return messages