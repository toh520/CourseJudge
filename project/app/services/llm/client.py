"""
文件名: client.py
功能描述: 大语言模型统一客户端封装。
遵循规范: 严格采用标准 OpenAI 兼容协议 (openai.OpenAI(base_url, api_key))，
          统一处理超时、指数退避重试、可重试错误识别与 SSE 流式增量输出。
"""

import time
from typing import Any, Dict, Iterator, List, Optional

from app.core.config import settings


class LLMServiceError(RuntimeError):
    """LLM 调用失败 (配置缺失、网络异常、服务端错误或空响应) 时抛出的统一异常"""


class LLMClient:
    """
    OpenAI 兼容协议统一客户端

    通过依赖注入支持测试替身：生产环境默认惰性创建 openai.OpenAI 实例；
    测试环境可直接传入具有相同 chat.completions.create 接口的假客户端。
    """

    # 可重试的 HTTP 状态码集合 (限流、超时与服务端临时故障)
    _RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}

    # 可重试的底层异常类型名称 (兼容不同版本 SDK 与网络库)
    _RETRYABLE_EXCEPTION_NAMES = {
        "APIConnectionError",
        "APITimeoutError",
        "RateLimitError",
        "InternalServerError",
        "TimeoutError",
        "ConnectionError",
    }

    def __init__(self, client: Any = None):
        """
        参数:
            client (Any): 可选的底层 OpenAI 兼容客户端实例；为空时惰性创建真实客户端
        """
        self._client = client

    @property
    def client(self) -> Any:
        """惰性获取底层 OpenAI 兼容客户端"""
        if self._client is None:
            if not settings.LLM_API_KEY:
                raise LLMServiceError("未配置 LLM_API_KEY，请在 .env 中填写大模型 API Key")
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise LLMServiceError(
                    "缺少 openai 依赖，请先执行 pip install -r requirements.txt"
                ) from exc

            self._client = OpenAI(
                base_url=settings.LLM_BASE_URL,
                api_key=settings.LLM_API_KEY,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
        return self._client

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        发起普通非流式对话请求

        参数:
            messages (List[Dict[str, str]]): OpenAI 格式消息列表
            temperature (Optional[float]): 采样温度，为空时使用全局默认值
            max_tokens (Optional[int]): 最大回复 token 数，为空时使用全局默认值
            response_format (Optional[Dict[str, Any]]): 可选的响应格式约束

        返回:
            str: 模型回复文本

        异常:
            LLMServiceError: 配置缺失、调用失败或返回内容为空
        """
        kwargs = self._build_kwargs(messages, temperature, max_tokens, response_format)
        response = self._with_retry(
            lambda: self.client.chat.completions.create(**kwargs)
        )
        return self._extract_content(response)

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Iterator[str]:
        """
        发起 SSE 流式对话请求，逐片产出文本增量

        参数:
            messages (List[Dict[str, str]]): OpenAI 格式消息列表
            temperature (Optional[float]): 采样温度，为空时使用全局默认值
            max_tokens (Optional[int]): 最大回复 token 数，为空时使用全局默认值

        返回:
            Iterator[str]: 文本增量迭代器

        异常:
            LLMServiceError: 建流失败或流式传输中途中断
        """
        kwargs = self._build_kwargs(messages, temperature, max_tokens, None)
        kwargs["stream"] = True

        # 建流阶段可安全重试；一旦开始产出增量则不再重试，避免重复输出
        stream = self._with_retry(
            lambda: self.client.chat.completions.create(**kwargs)
        )

        try:
            for chunk in stream:
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                content = getattr(delta, "content", None) if delta else None
                if content:
                    yield content
        except Exception as exc:
            raise LLMServiceError("流式输出中断: %s" % exc) from exc

    def _build_kwargs(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float],
        max_tokens: Optional[int],
        response_format: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        组装 OpenAI 兼容请求参数

        参数:
            messages (List[Dict[str, str]]): 消息列表
            temperature (Optional[float]): 采样温度
            max_tokens (Optional[int]): 最大回复 token 数
            response_format (Optional[Dict[str, Any]]): 响应格式约束

        返回:
            Dict[str, Any]: 可直接展开传给 SDK 的参数字典
        """
        if not messages:
            raise LLMServiceError("消息列表不能为空")

        kwargs: Dict[str, Any] = {
            "model": settings.LLM_MODEL_NAME,
            "messages": messages,
            "temperature": (
                settings.LLM_DEFAULT_TEMPERATURE if temperature is None else temperature
            ),
            "max_tokens": settings.LLM_MAX_TOKENS if max_tokens is None else max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format
        return kwargs

    def _with_retry(self, operation):
        """
        对可重试操作执行指数退避重试

        参数:
            operation: 无参可调用对象，执行一次底层 SDK 请求

        返回:
            Any: operation 的返回值

        异常:
            LLMServiceError: 重试耗尽或遇到不可重试错误
        """
        max_retries = max(0, int(settings.LLM_MAX_RETRIES))
        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                return operation()
            except Exception as exc:
                last_error = exc
                if attempt >= max_retries or not self._is_retryable(exc):
                    break

                # 指数退避: 1x, 2x, 4x ... 基准值由配置提供
                backoff = max(0.0, float(settings.LLM_RETRY_BACKOFF_SECONDS)) * (2 ** attempt)
                if backoff > 0:
                    time.sleep(backoff)

        raise LLMServiceError("LLM 调用失败: %s" % last_error) from last_error

    @classmethod
    def _is_retryable(cls, exc: Exception) -> bool:
        """
        判断异常是否属于可重试的临时性故障

        参数:
            exc (Exception): 底层捕获的异常

        返回:
            bool: 可重试返回 True
        """
        status_code = getattr(exc, "status_code", None)
        if status_code in cls._RETRYABLE_STATUS_CODES:
            return True
        return type(exc).__name__ in cls._RETRYABLE_EXCEPTION_NAMES

    @staticmethod
    def _extract_content(response: Any) -> str:
        """
        从 OpenAI 兼容响应中提取回复文本

        参数:
            response (Any): SDK 响应对象

        返回:
            str: 回复文本

        异常:
            LLMServiceError: 响应为空或内容为空
        """
        choices = getattr(response, "choices", None) or []
        if not choices:
            raise LLMServiceError("模型返回结果为空")

        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None) if message else None

        # 兼容少数服务商返回 content 分段数组的格式
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )

        if not content or not str(content).strip():
            raise LLMServiceError("模型返回内容为空")
        return str(content)