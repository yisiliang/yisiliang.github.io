"""Run pause and resume in different Python processes against a local SQLite DB."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import interrupt, Command

class State(TypedDict):
    item: str
    approved: bool

def review(state):
    return {"approved": interrupt({"item": state["item"]}) is True}

def worker(db, phase):
    b = StateGraph(State)
    b.add_node("review", review)
    b.add_edge(START, "review")
    b.add_edge("review", END)
    with SqliteSaver.from_conn_string(db) as saver:
        graph = b.compile(checkpointer=saver)
        cfg = {"configurable": {"thread_id": "restart-demo"}}
        if phase == "pause":
            result = graph.invoke({"item": "demo"}, cfg, durability="sync")
            assert result["__interrupt__"]
            return {"phase": "paused", "next": list(graph.get_state(cfg).next)}
        result = graph.invoke(Command(resume=True), cfg, durability="sync")
        assert result["approved"] is True and not graph.get_state(cfg).next
        return {"phase": "resumed", "approved": result["approved"]}

if __name__ == "__main__":
    if len(sys.argv) == 3:
        print(json.dumps(worker(sys.argv[1], sys.argv[2])))
    else:
        with tempfile.TemporaryDirectory(prefix="langgraph-restart-") as folder:
            db = str(Path(folder) / "checkpoints.sqlite")
            results = [json.loads(subprocess.check_output(
                [sys.executable, __file__, db, phase], text=True)) for phase in ["pause", "resume"]]
            print(json.dumps({"separate_processes": results}, indent=2))
