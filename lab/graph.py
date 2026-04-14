"""
graph.py — Supervisor Orchestrator
Sprint 1: Implement AgentState, supervisor_node, route_decision và kết nối graph.

Kiến trúc:
    Input → Supervisor → [retrieval_worker | policy_tool_worker | human_review] → synthesis → Output

Chạy thử:
    python graph.py
"""

import json
import os
from datetime import datetime
from typing import TypedDict, Literal, Optional

# LangGraph & Pydantic imports
from langgraph.graph import StateGraph, END, START
from pydantic import BaseModel, Field

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from src.llm import OpenAIGenerator

# ─────────────────────────────────────────────
# 1. Shared State — dữ liệu đi xuyên toàn graph
# ─────────────────────────────────────────────

class AgentState(TypedDict):
    # Input
    task: str                           # Câu hỏi đầu vào từ user

    # Supervisor decisions
    route_reason: str                   # Lý do route sang worker nào
    risk_high: bool                     # True → cần HITL hoặc human_review
    needs_tool: bool                    # True → cần gọi external tool qua MCP
    hitl_triggered: bool                # True → đã pause cho human review

    # Worker outputs
    retrieved_chunks: list              # Output từ retrieval_worker
    retrieved_sources: list             # Danh sách nguồn tài liệu
    policy_result: dict                 # Output từ policy_tool_worker
    mcp_tools_used: list                # Danh sách MCP tools đã gọi

    # Final output
    final_answer: str                   # Câu trả lời tổng hợp
    sources: list                       # Sources được cite
    confidence: float                   # Mức độ tin cậy (0.0 - 1.0)

    # Trace & history
    history: list                       # Lịch sử các bước đã qua
    workers_called: list                # Danh sách workers đã được gọi
    supervisor_route: str               # Worker được chọn bởi supervisor
    latency_ms: Optional[int]           # Thời gian xử lý (ms)
    run_id: str                         # ID của run này


def make_initial_state(task: str) -> AgentState:
    """Khởi tạo state cho một run mới."""
    return {
        "task": task,
        "route_reason": "",
        "risk_high": False,
        "needs_tool": False,
        "hitl_triggered": False,
        "retrieved_chunks": [],
        "retrieved_sources": [],
        "policy_result": {},
        "mcp_tools_used": [],
        "final_answer": "",
        "sources": [],
        "confidence": 0.0,
        "history": [],
        "workers_called": [],
        "supervisor_route": "",
        "latency_ms": None,
        "run_id": f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    }


# ─────────────────────────────────────────────
# 2. Supervisor Node — quyết định route
# ─────────────────────────────────────────────

class RouterDecision(BaseModel):
    route: Literal["retrieval_worker", "policy_tool_worker", "human_review"] = Field(
        description="The target worker to handle the user task."
    )
    route_reason: str = Field(description="Explanation of why this route was chosen.")
    needs_tool: bool = Field(description="True if external tools/MCP are needed to answer properly.")
    risk_high: bool = Field(description="True if the task is an emergency, unknown error, or high-risk scenario requiring careful review.")

def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor phân tích task bằng LangChain LLM Router và quyết định:
    1. Route sang worker nào
    2. Có cần MCP tool không
    3. Có risk cao cần HITL không
    """
    task = state["task"]
    state["history"].append(f"[supervisor] received task: {task[:80]}")

    # Initialize LLM with structured output
    llm = OpenAIGenerator(model_name="gpt-4o-mini", temperature=0.1).llm
    structured_llm = llm.with_structured_output(RouterDecision)

    prompt = f"""You are an intelligent supervisor router for an IT Helpdesk RAG pipeline.
Your job is to analyze the user's task and route it to the correct worker.

Routing Policies:
1. "policy_tool_worker": Choose this if the task involves assessing refunds, licensing, flash sales, access level requests (e.g., Level 3 access), store credit, or specific complex rules.
2. "human_review": Choose this if the task contains unknown error codes (e.g., ERR-XXX), extremely vague descriptions missing context, or extremely critical unresolved issues outside normal scope.
3. "retrieval_worker": Choose this by default for standard queries, SLAs, standard troubleshooting guides, escalation paths, and general knowledge base search.

Risk & Tools Policies:
- Set needs_tool=True if you route to "policy_tool_worker" OR if the query directly implies looking up databases.
- Set risk_high=True if the task mentions an emergency, severe unknown error, or high-priority P1 issue that needs escalation review.

Analyze carefully.
Task: {task}
"""
    decision: RouterDecision = structured_llm.invoke([{"role": "system", "content": prompt}])

    # Lỡ LLM không parse được risk_high liên quan human error manually redirect nếu lọt
    if decision.risk_high and "err-" in task.lower() and decision.route != "human_review":
        decision.route = "human_review"
        decision.route_reason += " (Forced human review due to unknown error)"

    state["supervisor_route"] = decision.route
    state["route_reason"] = decision.route_reason
    state["needs_tool"] = decision.needs_tool
    state["risk_high"] = decision.risk_high
    state["history"].append(f"[supervisor] route={decision.route} reason={decision.route_reason}")

    return state


# ─────────────────────────────────────────────
# 3. Route Decision — conditional edge
# ─────────────────────────────────────────────

def route_decision(state: AgentState) -> Literal["retrieval_worker", "policy_tool_worker", "human_review"]:
    """
    Trả về tên worker tiếp theo dựa vào supervisor_route trong state.
    Đây là conditional edge của graph.
    """
    route = state.get("supervisor_route", "retrieval_worker")
    return route  # type: ignore


# ─────────────────────────────────────────────
# 4. Human Review Node — HITL placeholder
# ─────────────────────────────────────────────

def human_review_node(state: AgentState) -> AgentState:
    """
    HITL node: pause và chờ human approval.
    Trong lab này, implement dưới dạng placeholder (in ra warning).

    TODO Sprint 3 (optional): Implement actual HITL với interrupt_before hoặc
    breakpoint nếu dùng LangGraph.
    """
    state["hitl_triggered"] = True
    state["history"].append("[human_review] HITL triggered — awaiting human input")
    state["workers_called"].append("human_review")

    # Placeholder: tự động approve để pipeline tiếp tục
    print(f"\n⚠️  HITL TRIGGERED")
    print(f"   Task: {state['task']}")
    print(f"   Reason: {state['route_reason']}")
    print(f"   Action: Auto-approving in lab mode (set hitl_triggered=True)\n")

    # Sau khi human approve, route về retrieval để lấy evidence
    state["supervisor_route"] = "retrieval_worker"
    state["route_reason"] += " | human approved → retrieval"

    return state


# ─────────────────────────────────────────────
# 5. Import Workers
# ─────────────────────────────────────────────

# TODO Sprint 2: Uncomment sau khi implement workers
from workers.retrieval import run as retrieval_run
from workers.policy_tool import run as policy_tool_run
from workers.synthesis import run as synthesis_run


def retrieval_worker_node(state: AgentState) -> AgentState:
    """Wrapper gọi retrieval worker."""
    return retrieval_run(state)


def policy_tool_worker_node(state: AgentState) -> AgentState:
    """Wrapper gọi policy/tool worker."""
    return policy_tool_run(state)


def synthesis_worker_node(state: AgentState) -> AgentState:
    """Wrapper gọi synthesis worker."""
    return synthesis_run(state)


# ─────────────────────────────────────────────
# 6. Build Graph
# ─────────────────────────────────────────────

def build_graph():
    """
    Xây dựng graph với supervisor-worker pattern sử dụng LangGraph.
    """
    workflow = StateGraph(AgentState)

    # Đăng ký các Nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("retrieval_worker", retrieval_worker_node)
    workflow.add_node("policy_tool_worker", policy_tool_worker_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("synthesis_worker", synthesis_worker_node)

    # Thiết lập luồng bắt đầu
    workflow.add_edge(START, "supervisor")

    # Routing Edge ngay sau khi qua Supervisor
    workflow.add_conditional_edges(
        "supervisor",
        route_decision,
        {
            "retrieval_worker": "retrieval_worker",
            "policy_tool_worker": "policy_tool_worker",
            "human_review": "human_review"
        }
    )

    # Edge logic sau khi gọi policy_tool: Nếu chưa có source chunk thì quay lại retrieval
    def policy_edge(state: AgentState) -> str:
        if not state.get("retrieved_chunks"):
            return "retrieval_worker"
        return "synthesis_worker"

    workflow.add_conditional_edges(
        "policy_tool_worker",
        policy_edge,
        {
            "retrieval_worker": "retrieval_worker",
            "synthesis_worker": "synthesis_worker"
        }
    )

    # Kết nối cố định các worker còn lại về luồng đích (synthesis)
    workflow.add_edge("human_review", "retrieval_worker")
    workflow.add_edge("retrieval_worker", "synthesis_worker")
    workflow.add_edge("synthesis_worker", END)

    # Biên dịch app
    app = workflow.compile()

    # Wrapper để khớp với interface cũ
    def run(state: AgentState) -> AgentState:
        import time
        start = time.time()
        
        # Invoke LangGraph
        result_state = app.invoke(state)
        
        # Vì StateGraph định nghĩa bằng dict, nên nó sẽ return list dict state cuối
        final_state = dict(result_state)

        final_state["latency_ms"] = int((time.time() - start) * 1000)
        final_state["history"].append(f"[graph] completed in {final_state['latency_ms']}ms")
        return final_state

    return run


# ─────────────────────────────────────────────
# 7. Public API
# ─────────────────────────────────────────────

_graph = build_graph()


def run_graph(task: str) -> AgentState:
    """
    Entry point: nhận câu hỏi, trả về AgentState với full trace.

    Args:
        task: Câu hỏi từ user

    Returns:
        AgentState với final_answer, trace, routing info, v.v.
    """
    state = make_initial_state(task)
    result = _graph(state)
    return result


def save_trace(state: AgentState, output_dir: str = "./artifacts/traces") -> str:
    """Lưu trace ra file JSON."""
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{output_dir}/{state['run_id']}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return filename


# ─────────────────────────────────────────────
# 8. Manual Test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Day 09 Lab — Supervisor-Worker Graph")
    print("=" * 60)

    test_queries = [
        "SLA xử lý ticket P1 là bao lâu?",
        "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?",
        "Cần cấp quyền Level 3 để khắc phục P1 khẩn cấp. Quy trình là gì?",
    ]

    for query in test_queries:
        print(f"\n▶ Query: {query}")
        result = run_graph(query)
        print(f"  Route   : {result['supervisor_route']}")
        print(f"  Reason  : {result['route_reason']}")
        print(f"  Workers : {result['workers_called']}")
        print(f"  Answer  : {result['final_answer'][:100]}...")
        print(f"  Confidence: {result['confidence']}")
        print(f"  Latency : {result['latency_ms']}ms")

        # Lưu trace
        trace_file = save_trace(result)
        print(f"  Trace saved → {trace_file}")

    print("\n✅ graph.py test complete. Implement TODO sections in Sprint 1 & 2.")
