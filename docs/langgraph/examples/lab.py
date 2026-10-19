"""Deterministic LangGraph labs; no model, key, network, or business service."""
from __future__ import annotations
import json
import operator
import platform
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import InvalidUpdateError, GraphRecursionError
from langgraph.types import Command, Send, RetryPolicy, interrupt
from langgraph.graph.message import add_messages


def minimal():
    class State(TypedDict):
        text: str
        result: str
    def normalize(state):
        return {"result": state["text"].strip().upper()}
    builder = StateGraph(State)
    builder.add_node("normalize", normalize)
    builder.add_edge(START, "normalize")
    builder.add_edge("normalize", END)
    graph = builder.compile()
    result = graph.invoke({"text": " hello "})
    assert result == {"text": " hello ", "result": "HELLO"}
    return result


def parallel():
    class State(TypedDict):
        items: Annotated[list[str], operator.add]
        total: int
    def make_graph(schema):
        b = StateGraph(schema)
        b.add_node("a", lambda s: {"items": ["A"]})
        b.add_node("b", lambda s: {"items": ["B"]})
        b.add_node("join", lambda s: {"total": len(s["items"])})
        b.add_edge(START, "a")
        b.add_edge(START, "b")
        b.add_edge(["a", "b"], "join")
        b.add_edge("join", END)
        return b.compile()
    result = make_graph(State).invoke({"items": []})
    assert sorted(result["items"]) == ["A", "B"] and result["total"] == 2
    class BadState(TypedDict):
        items: list[str]
        total: int
    try:
        make_graph(BadState).invoke({"items": []})
    except InvalidUpdateError:
        conflict = "InvalidUpdateError"
    else:
        raise AssertionError("parallel writes must conflict without reducer")
    return {"merged": sorted(result["items"]), "join_total": result["total"], "without_reducer": conflict}


def messages():
    first = add_messages([], [{"role": "user", "content": "old", "id": "m1"}])
    second = add_messages(first, [{"role": "user", "content": "corrected", "id": "m1"}])
    assert len(second) == 1 and second[0].content == "corrected"
    return {"count": len(second), "same_id_content": second[0].content}


def dispatch():
    class State(TypedDict):
        numbers: list[int]
        squares: Annotated[list[int], operator.add]
    class Job(TypedDict):
        number: int
    def route(state):
        return [Send("square", {"number": n}) for n in state["numbers"]]
    def square(state: Job):
        return {"squares": [state["number"] ** 2]}
    b = StateGraph(State)
    b.add_node("square", square)
    b.add_conditional_edges(START, route, ["square"])
    b.add_edge("square", END)
    result = b.compile().invoke({"numbers": [2, 3, 4], "squares": []})
    assert sorted(result["squares"]) == [4, 9, 16]
    return {"squares": sorted(result["squares"])}


def approval():
    class State(TypedDict):
        request_id: str
        text: str
        candidate: dict
        status: str
        receipt: str
    audit = {"review_entries": 0, "writes": 0}
    # Simulated extraction with fixed rules; this does not evaluate any LLM.
    def extract(state):
        return {"candidate": {"action": "add", "person": state["text"].strip()}, "status": "extracted"}
    def validate(state):
        person = state["candidate"]["person"]
        return {"status": "valid" if person else "invalid"}
    def route(state):
        return "review" if state["status"] == "valid" else "reject"
    def review(state):
        audit["review_entries"] += 1  # Demonstrate node re-entry; not a business write.
        answer = interrupt({"request_id": state["request_id"], "candidate": state["candidate"]})
        # Backend must separately authorize caller and validate the review payload.
        approved = isinstance(answer, dict) and answer.get("approved") is True
        return Command(update={"status": "approved" if approved else "rejected"},
                       goto="submit" if approved else "reject")
    def submit(state):
        assert state["status"] == "approved"
        audit["writes"] += 1
        return {"receipt": "DEMO-" + state["request_id"], "status": "submitted"}
    def reject(state):
        return {"status": "rejected"}
    b = StateGraph(State)
    for name, fn in [("extract", extract), ("validate", validate), ("review", review), ("submit", submit), ("reject", reject)]:
        b.add_node(name, fn)
    b.add_edge(START, "extract")
    b.add_edge("extract", "validate")
    b.add_conditional_edges("validate", route, {"review": "review", "reject": "reject"})
    # No static outgoing edge from review: its Command owns the route.
    b.add_edge("submit", END)
    b.add_edge("reject", END)
    graph = b.compile(checkpointer=InMemorySaver())
    cfg = {"configurable": {"thread_id": "approval-1"}}
    paused = graph.invoke({"request_id": "r1", "text": " Alice "}, cfg)
    assert paused["__interrupt__"] and audit["writes"] == 0
    snapshot = graph.get_state(cfg)
    assert snapshot.next == ("review",)
    final = graph.invoke(Command(resume={"approved": True}), cfg)
    assert final["status"] == "submitted" and audit == {"review_entries": 2, "writes": 1}
    deny_cfg = {"configurable": {"thread_id": "approval-deny"}}
    graph.invoke({"request_id": "r2", "text": "Bob"}, deny_cfg)
    denied = graph.invoke(Command(resume={"approved": False}), deny_cfg)
    assert denied["status"] == "rejected" and audit["writes"] == 1
    invalid = graph.invoke({"request_id": "r3", "text": " "}, {"configurable": {"thread_id": "invalid"}})
    assert invalid["status"] == "rejected" and "__interrupt__" not in invalid
    return {"paused_next": list(snapshot.next), "approved_status": final["status"],
            "denied_status": denied["status"], "invalid_status": invalid["status"],
            "review_entries": audit["review_entries"], "writes": audit["writes"]}


def retry():
    class State(TypedDict):
        ok: bool
    attempts = {"count": 0}
    def flaky(state):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise ConnectionError("simulated temporary outage")
        return {"ok": True}
    b = StateGraph(State)
    b.add_node("flaky", flaky, retry_policy=RetryPolicy(
        initial_interval=0.001, max_interval=0.001, max_attempts=3,
        jitter=False, retry_on=ConnectionError))
    b.add_edge(START, "flaky")
    b.add_edge("flaky", END)
    assert b.compile().invoke({})["ok"] is True
    assert attempts["count"] == 3
    return {"attempts_including_first": attempts["count"]}


def pending_writes():
    class State(TypedDict):
        done: Annotated[list[str], operator.add]
    calls = {"a": 0, "b": 0}
    def a(state):
        calls["a"] += 1
        return {"done": ["A"]}
    def b(state):
        calls["b"] += 1
        if calls["b"] == 1:
            raise ValueError("simulated failure")
        return {"done": ["B"]}
    builder = StateGraph(State)
    builder.add_node("a", a)
    builder.add_node("b", b)
    builder.add_edge(START, "a")
    builder.add_edge(START, "b")
    builder.add_edge("a", END)
    builder.add_edge("b", END)
    graph = builder.compile(checkpointer=InMemorySaver())
    cfg = {"configurable": {"thread_id": "pending"}}
    try:
        graph.invoke({"done": []}, cfg, durability="sync")
    except ValueError:
        pass
    else:
        raise AssertionError("expected failure")
    result = graph.invoke(None, cfg, durability="sync")
    assert sorted(result["done"]) == ["A", "B"] and calls == {"a": 1, "b": 2}
    return {"calls": calls, "done": sorted(result["done"])}


def recursion():
    class State(TypedDict):
        count: int
    b = StateGraph(State)
    b.add_node("loop", lambda s: {"count": s["count"] + 1})
    b.add_edge(START, "loop")
    b.add_edge("loop", "loop")
    try:
        b.compile().invoke({"count": 0}, {"recursion_limit": 3})
    except GraphRecursionError:
        return {"unbounded_loop": "GraphRecursionError"}
    raise AssertionError("loop should reach recursion limit")


def streaming():
    class State(TypedDict):
        count: int
    b = StateGraph(State)
    b.add_node("inc", lambda s: {"count": s["count"] + 1})
    b.add_edge(START, "inc")
    b.add_edge("inc", END)
    events = list(b.compile().stream({"count": 0}, stream_mode="updates"))
    assert events == [{"inc": {"count": 1}}]
    return events


def run():
    results = {fn.__name__: fn() for fn in [minimal, parallel, messages, dispatch,
               approval, retry, pending_writes, recursion, streaming]}
    return {"python": platform.python_version(), "langgraph": version("langgraph"),
            "checkpoint": version("langgraph-checkpoint"), "cases": results}

if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
