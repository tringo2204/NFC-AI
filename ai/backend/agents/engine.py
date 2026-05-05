"""
LangGraph Agent Engine — nhận ERPEvent, gọi tools, trả về DecisionOutput.

Flow:
  ERPEvent
    → Event Aggregator  (resolve semantic event_type)
    → Domain Router     (get scoped tool list)
    → LangGraph ReAct   (LLM chọn tool, gọi, interpret)
    → Synthesizer       (validate + format thành DecisionOutput)
"""
import json
import os
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from ..db.adapter import OdooQuery, SessionLocal
from ..events.aggregator import EventAggregator
from ..events.router import DomainRouter
from ..tools.registry import get_tools_for_scope
from ..schemas.decision import ERPEvent, DecisionOutput

# Ensure purchase tools are registered
import ai.backend.tools.purchase  # noqa: F401

SYSTEM_PROMPT = """Bạn là AI Assistant của NFC ERP — chuyên gia phân tích dữ liệu mua hàng.

Nhiệm vụ: Phân tích dữ liệu thực từ hệ thống, đưa ra nhận xét ngắn gọn và hành động gợi ý.

Quy tắc bắt buộc:
1. Luôn gọi tools để lấy data thực — không đoán, không dùng kiến thức chung.
2. Nếu data_points < 3 → trả level = "no_data", không đưa ra nhận xét.
3. message tối đa 120 ký tự, tiếng Việt, có số cụ thể (VD: "Giá cao hơn 23% so với TB 3 tháng: 450,000đ vs 366,000đ").
4. Luôn trả về JSON hợp lệ theo schema sau:
{{
  "level": "good|normal|high|critical|no_data",
  "deviation_pct": null hoặc số,
  "message": "...",
  "suggestion": null hoặc "...",
  "actions": [],
  "confidence": "high|medium|low",
  "data_points": số nguyên,
  "tools_used": ["tên tool"],
  "cached": false
}}

Thang đánh giá deviation_pct:
  < 5%  → good
  5–15% → normal
  15–30% → high
  > 30% → critical

{domain_hint}"""


def _get_llm(tools: list):
    provider = os.getenv("LLM_PROVIDER", "openai")
    model = os.getenv("LLM_MODEL", "gpt-4o")
    if provider == "anthropic":
        llm = ChatAnthropic(model=model, temperature=0)
    else:
        llm = ChatOpenAI(model=model, temperature=0)
    return llm.bind_tools(tools)


class AgentState(TypedDict):
    messages: Annotated[list, lambda x, y: x + y]
    event: ERPEvent
    tool_names: list[str]
    domain_hint: str


def _make_langchain_tool(tool_fn, db_session):
    """Wrap @tool function thành LangChain tool (inject db session)."""
    from langchain_core.tools import tool as lc_tool

    @lc_tool(tool_fn.__tool_name__)
    def wrapped(**kwargs):
        q = OdooQuery(db_session)
        return tool_fn(q, **kwargs)

    wrapped.__doc__ = tool_fn.__doc__
    return wrapped


class DecisionAgent:
    def __init__(self):
        self.aggregator = EventAggregator()
        self.router = DomainRouter()

    def run(self, event: ERPEvent) -> DecisionOutput:
        # 1. Resolve semantic event
        event = self.aggregator.resolve(event)
        if event.event_type == "unknown":
            return DecisionOutput(
                level="no_data",
                message="Sự kiện này chưa được cấu hình phân tích.",
                confidence="low",
                data_points=0,
            )

        # 2. Get scoped tools
        tool_names = self.router.get_tools(event.model, event.event_type)
        domain_hint = self.router.get_system_hint(event.model, event.event_type)
        if not tool_names:
            return DecisionOutput(
                level="no_data",
                message="Không có tools nào được cấu hình cho sự kiện này.",
                confidence="low",
                data_points=0,
            )

        # 3. Build LangChain tools với DB session
        db = SessionLocal()
        try:
            registry_tools = get_tools_for_scope(tool_names)
            lc_tools = [_make_langchain_tool(t, db) for t in registry_tools]

            # 4. Build + run LangGraph
            llm = _get_llm(lc_tools)
            tool_node = ToolNode(lc_tools)

            def call_llm(state: AgentState):
                system = SYSTEM_PROMPT.format(domain_hint=state["domain_hint"])
                response = llm.invoke(
                    [SystemMessage(content=system)] + state["messages"]
                )
                return {"messages": [response]}

            def should_continue(state: AgentState):
                last = state["messages"][-1]
                if hasattr(last, "tool_calls") and last.tool_calls:
                    return "tools"
                return END

            graph = StateGraph(AgentState)
            graph.add_node("llm", call_llm)
            graph.add_node("tools", tool_node)
            graph.set_entry_point("llm")
            graph.add_conditional_edges("llm", should_continue)
            graph.add_edge("tools", "llm")
            app = graph.compile()

            # 5. Invoke
            user_msg = HumanMessage(content=json.dumps({
                "event": event.model_dump(),
                "instruction": "Phân tích dữ liệu và trả về JSON theo schema đã yêu cầu.",
            }, ensure_ascii=False))

            result = app.invoke({
                "messages": [user_msg],
                "event": event,
                "tool_names": tool_names,
                "domain_hint": domain_hint,
            })

            # 6. Parse output
            last_msg = result["messages"][-1]
            content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

            # Extract JSON từ response
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group())
                data.setdefault("tools_used", tool_names)
                return DecisionOutput(**data)

        except Exception as e:
            return DecisionOutput(
                level="no_data",
                message=f"Lỗi phân tích: {str(e)[:80]}",
                confidence="low",
                data_points=0,
            )
        finally:
            db.close()

        return DecisionOutput(
            level="no_data",
            message="Không thể parse kết quả từ AI.",
            confidence="low",
            data_points=0,
        )
