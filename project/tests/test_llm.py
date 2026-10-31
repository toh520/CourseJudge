"""
文件名: test_llm.py
功能描述: Phase 3 大语言模型 (LLM) 服务与智能闭环阶段自动化验收测试。
测试策略:
    1. 默认全部使用可控假响应，不发起任何真实网络请求、不消耗 token;
    2. 用例生成闭环中的标准代码编译运行仍使用真实 g++，确保 100% 正向回填可信;
    3. 仅当显式设置 RUN_REAL_LLM_TESTS=1 时，追加一次真实模型冒烟调用。
"""

import os
import sys
import io
import json
from pathlib import Path
from types import SimpleNamespace

# 在 Windows 终端下统一标准输出为 UTF-8，防止 GBK 编码异常
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 将 project 目录加入 Python 搜索路径，确保可以直接导入 app 包
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 使用临时独立的测试数据库，避免污染真实业务数据
TEST_DB_FILE = PROJECT_ROOT / "test_llm.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"

from app.core.config import settings
from app.core.database import SessionLocal, engine, init_db
from app.models import User
from app.services.llm.client import LLMClient, LLMServiceError
from app.services.llm.common.parsers import LLMResponseFormatError, extract_json_object
from app.services.llm.generator import ProblemGenerator
from app.services.llm.diagnostician import Diagnostician
from app.services.llm.trainer import TrainingProblemGenerator
from app.services.llm.assistant import AssistantService


# ------------------------- 假客户端与测试夹具 -------------------------

class FakeLLMClient:
    """测试用假 LLM 客户端: 按顺序返回预设回复，绝不发起网络请求"""

    def __init__(self, responses=None, stream_chunks=None):
        """
        参数:
            responses (list): chat() 依次返回的文本或异常
            stream_chunks (list): chat_stream() 依次返回的字符串分片列表或异常
        """
        self.responses = list(responses or [])
        self.stream_chunks = list(stream_chunks or [])
        self.chat_calls = []
        self.stream_calls = []

    def chat(self, messages, **kwargs):
        """返回预设的普通回复"""
        self.chat_calls.append((messages, kwargs))
        if not self.responses:
            raise AssertionError("假客户端的普通响应已耗尽")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def chat_stream(self, messages, **kwargs):
        """逐片返回预设的流式回复"""
        self.stream_calls.append((messages, kwargs))
        if not self.stream_chunks:
            raise AssertionError("假客户端的流式响应已耗尽")
        item = self.stream_chunks.pop(0)
        if isinstance(item, Exception):
            raise item
        yield from item


class RetryableError(Exception):
    """模拟可重试的服务端错误 (500)"""
    status_code = 500


class FatalError(Exception):
    """模拟不可重试的客户端错误 (400)"""
    status_code = 400


class _FakeOpenAICompatibleClient:
    """模拟底层 OpenAI 兼容 SDK 客户端，用于验证 LLMClient 的重试与解析"""

    def __init__(self, results):
        """
        参数:
            results (list): 每次 create() 依次返回的文本/异常/流式分片列表
        """
        self.results = list(results)
        self.call_count = 0
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs):
        """模拟 chat.completions.create 调用"""
        self.call_count += 1
        if not self.results:
            raise AssertionError("假 OpenAI 客户端的响应已耗尽")
        item = self.results.pop(0)
        if isinstance(item, Exception):
            raise item
        if kwargs.get("stream"):
            return iter(item)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=item))]
        )


def _stream_chunk(text):
    """构造一个 OpenAI 兼容的流式增量分片对象"""
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text))]
    )


# ------------------------- 假响应 JSON 夹具 -------------------------

PROBLEM_JSON = json.dumps({
    "title": "两数之和",
    "description": "给定两个整数 a 和 b，输出它们的和。",
    "input_format": "一行两个整数 a b",
    "output_format": "一个整数，表示 a + b",
    "sample_input": "1 2",
    "sample_output": "3",
    "time_limit_ms": 1000,
    "memory_limit_mb": 256,
    "knowledge_tag": "基础输入输出",
    "standard_code": (
        "#include <iostream>\n"
        "int main() { int a, b; std::cin >> a >> b; std::cout << a + b << std::endl; return 0; }"
    ),
}, ensure_ascii=False)

TEST_INPUTS_JSON = json.dumps({
    "test_inputs": ["1 2", "1000000000 1000000000", "-5 8"]
}, ensure_ascii=False)

DIAGNOSIS_JSON = json.dumps({
    "summary": "学生在动态规划的边界条件处理上存在明显不足。",
    "weak_points": [
        {
            "tag": "动态规划-状态转移",
            "evidence": "未考虑空数组与单元素边界，状态转移初值设置错误。",
            "suggestion": "先明确状态定义，再手推前三项验证转移方程。"
        }
    ],
    "learning_guidance": "建议从 0-1 背包与爬楼梯两个基础模型开始复习。"
}, ensure_ascii=False)

TRAINING_JSON = json.dumps({
    "title": "爬楼梯方案数",
    "description": "每次可以爬 1 阶或 2 阶，求爬到第 n 阶的方案数。",
    "input_format": "一个整数 n (1 <= n <= 45)",
    "output_format": "一个整数，表示方案数",
    "sample_input": "3",
    "sample_output": "3",
    "time_limit_ms": 1000,
    "memory_limit_mb": 256,
    "knowledge_tag": "动态规划-状态转移",
    "standard_code": (
        "#include <iostream>\n"
        "int main() { int n; std::cin >> n; long long a = 1, b = 1;"
        " for (int i = 2; i <= n; ++i) { long long c = a + b; a = b; b = c; }"
        " std::cout << b << std::endl; return 0; }"
    ),
    "test_inputs": ["1", "3", "5"]
}, ensure_ascii=False)


def run_phase3_verification():
    """执行 Phase 3 阶段自动化验收测试流程"""
    print("\n" + "=" * 70)
    print(">>> 开始执行 Phase 3: LLM 服务与智能闭环 自动化验收测试 <<<")
    print("=" * 70)
    passed = 0
    failed = 0

    def check(label, cond):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  [OK] {label}")
        else:
            failed += 1
            print(f"  [FAIL] {label}")

    # -----------------------------------------------------------------
    # 1. JSON 容错解析 (Step 3.1 支撑能力)
    # -----------------------------------------------------------------
    print("\n[测试项 1/7] 验证 LLM 输出 JSON 容错解析...")
    check("解析纯 JSON 对象", extract_json_object('{"a": 1}') == {"a": 1})
    check("解析 Markdown 围栏 JSON", extract_json_object('```json\n{"a": 2}\n```') == {"a": 2})
    mixed = extract_json_object('好的，结果如下:\n{"a": {"b": "}"}, "c": [1, 2]}\n请查收')
    check("解析夹杂说明文字与字符串花括号的 JSON", mixed["a"]["b"] == "}" and mixed["c"] == [1, 2])
    try:
        extract_json_object("这里完全没有 JSON")
        no_json_raised = False
    except LLMResponseFormatError:
        no_json_raised = True
    check("无 JSON 时抛出明确的格式异常", no_json_raised)

    # -----------------------------------------------------------------
    # 2. OpenAI 兼容客户端: 重试、异常封装与流式输出 (Step 3.1)
    # -----------------------------------------------------------------
    print("\n[测试项 2/7] 验证 OpenAI 兼容客户端重试与流式能力...")
    original_retries = settings.LLM_MAX_RETRIES
    original_backoff = settings.LLM_RETRY_BACKOFF_SECONDS
    try:
        settings.LLM_MAX_RETRIES = 3
        settings.LLM_RETRY_BACKOFF_SECONDS = 0  # 测试中关闭退避等待

        retry_fake = _FakeOpenAICompatibleClient([
            RetryableError("服务端 500"),
            RetryableError("服务端 500"),
            "恢复成功",
        ])
        retry_client = LLMClient(client=retry_fake)
        reply = retry_client.chat([{"role": "user", "content": "hi"}])
        check("可重试错误在重试后成功返回", reply == "恢复成功")
        check("重试次数符合配置 (1 次初始 + 2 次重试)", retry_fake.call_count == 3)

        fatal_fake = _FakeOpenAICompatibleClient([FatalError("请求参数错误")])
        fatal_raised = False
        try:
            LLMClient(client=fatal_fake).chat([{"role": "user", "content": "hi"}])
        except LLMServiceError:
            fatal_raised = True
        check("不可重试错误立即封装并抛出", fatal_raised and fatal_fake.call_count == 1)

        stream_fake = _FakeOpenAICompatibleClient([
            [_stream_chunk("你"), _stream_chunk("好")]
        ])
        chunks = list(LLMClient(client=stream_fake).chat_stream([{"role": "user", "content": "hi"}]))
        check("流式输出逐片返回且可拼接", chunks == ["你", "好"])
    finally:
        settings.LLM_MAX_RETRIES = original_retries
        settings.LLM_RETRY_BACKOFF_SECONDS = original_backoff

    # -----------------------------------------------------------------
    # 3. AI 快速出题与标准代码 (Step 3.2)
    # -----------------------------------------------------------------
    print("\n[测试项 3/7] 验证 AI 快速出题与结构化解析...")
    generator = ProblemGenerator(
        llm_client=FakeLLMClient([PROBLEM_JSON, TEST_INPUTS_JSON])
    )
    generated = generator.generate_problem("出 1 道两数之和入门题", "基础输入输出", test_count=3)
    check("生成题目标题正确", generated["problem"]["title"] == "两数之和")
    check("生成题目包含标准 C++ 解答", "std::cin" in generated["problem"]["standard_code"])
    check("生成题目标记为 AI 生成", generated["problem"]["is_ai_generated"] is True)

    # -----------------------------------------------------------------
    # 4. 测试用例 100% 正向验证闭环 (Step 3.3)
    # -----------------------------------------------------------------
    print("\n[测试项 4/7] 验证用例生成 + 标准代码运行回填闭环...")
    cases = generated["test_cases"]
    check("用例数量与请求一致", len(cases) == 3)
    check("用例期望输出由真实 g++ 运行标准代码回填",
          [c["output_data"] for c in cases] == ["3", "2000000000", "3"])
    check("用例权重总和为 100", sum(c["score_weight"] for c in cases) == 100)
    check("用例输入与 LLM 生成输入一致",
          [c["input_data"] for c in cases] == ["1 2", "1000000000 1000000000", "-5 8"])
    check("出题提示词携带教师意图",
          "两数之和" in generator.llm.chat_calls[0][0][-1]["content"])

    # -----------------------------------------------------------------
    # 5. 考后短板诊断 (Step 3.4)
    # -----------------------------------------------------------------
    print("\n[测试项 5/7] 验证考后学情短板诊断...")
    diagnostician = Diagnostician(llm_client=FakeLLMClient([DIAGNOSIS_JSON]))
    report = diagnostician.diagnose(
        "第三周动态规划练习",
        [{
            "problem_title": "爬楼梯",
            "knowledge_tag": "动态规划",
            "status": "WA",
            "score": 40,
            "code": "int main() { return 0; }",
            "error_msg": "答案错误",
        }],
    )
    check("诊断报告解析出薄弱点标签", report["weak_points"][0]["tag"] == "动态规划-状态转移")
    check("诊断报告包含学习指导", "背包" in report["learning_guidance"])
    check("诊断提示词携带学生源码",
          "int main" in diagnostician.llm.chat_calls[0][0][-1]["content"])

    # -----------------------------------------------------------------
    # 6. 专属强化题生成与落库 (Step 3.5)
    # -----------------------------------------------------------------
    print("\n[测试项 6/7] 验证专属强化题生成、用例验证与落库...")
    if TEST_DB_FILE.exists():
        TEST_DB_FILE.unlink()
    init_db()
    db = SessionLocal()
    try:
        student = User(username="S_PHASE3", real_name="测试学生", password="pwd", role="student")
        db.add(student)
        db.commit()
        db.refresh(student)

        trainer = TrainingProblemGenerator(llm_client=FakeLLMClient([TRAINING_JSON]))
        training = trainer.generate_and_save(
            db, student.id, "动态规划-状态转移", source_assignment_id=None
        )
        check("强化题成功落库并关联学生", training.id is not None and training.student_id == student.id)
        check("强化题知识点与短板一致", training.knowledge_tag == "动态规划-状态转移")
        stored_cases = json.loads(training.test_cases_json)
        check("强化题配套用例已完成正向验证",
              len(stored_cases) == 3 and stored_cases[1]["output_data"] == "3")
        check("强化题初始掌握状态为 Unsolved", training.best_status == "Unsolved")
    finally:
        db.close()
        engine.dispose()
        if TEST_DB_FILE.exists():
            try:
                TEST_DB_FILE.unlink()
            except Exception:
                pass
    check("Phase 3 测试数据库已清理", not TEST_DB_FILE.exists())

    # -----------------------------------------------------------------
    # 7. AI 助手多轮对话与流式输出 (Step 3.6)
    # -----------------------------------------------------------------
    print("\n[测试项 7/7] 验证 AI 助手多轮对话与流式输出...")
    assistant = AssistantService(llm_client=FakeLLMClient(stream_chunks=[["你", "好"]]))
    streamed = "".join(assistant.chat_stream("你好"))
    check("AI 助手流式输出可拼接", streamed == "你好")

    history_assistant = AssistantService(llm_client=FakeLLMClient(["上一答"]))
    history_assistant.chat(
        "继续",
        history=[
            {"role": "user", "content": "上一问"},
            {"role": "assistant", "content": "上一答"},
        ],
    )
    sent_messages = history_assistant.llm.chat_calls[0][0]
    check("多轮历史按 system/user/assistant/user 顺序注入",
          [m["role"] for m in sent_messages] == ["system", "user", "assistant", "user"])

    # -----------------------------------------------------------------
    # 可选: 真实模型冒烟 (仅显式开启时执行，避免日常测试消耗 token)
    # -----------------------------------------------------------------
    if os.getenv("RUN_REAL_LLM_TESTS") == "1":
        print("\n[真实模型冒烟] 使用 .env 配置发起一次最小调用...")
        try:
            real_reply = LLMClient().chat(
                [{"role": "user", "content": "只回复两个字: 你好"}],
                max_tokens=16,
            )
            check("真实模型冒烟调用成功", bool(real_reply.strip()))
        except Exception as exc:
            check(f"真实模型冒烟失败: {exc}", False)
    else:
        print("\n[真实模型冒烟] 已跳过 (设置 RUN_REAL_LLM_TESTS=1 可启用，会消耗 token)")

    # -----------------------------------------------------------------
    # 汇总
    # -----------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f">>> Phase 3 验收测试完成: 通过 {passed} 项, 失败 {failed} 项 <<<")
    print("=" * 70)
    if failed > 0:
        sys.exit(1)
    print("\n✅ 所有验收项全部通过，Phase 3 LLM 服务与智能闭环开发达标！")


if __name__ == "__main__":
    run_phase3_verification()