"""
Workflow Definition for "VidAudit".

This module defines the Directed Acyclic Graph (DAG) that orchestrates video compliance audit process. It connects nodes (functional units)
using StateGraph primitive from LangGraph.

Architecture:
    [START] -> [index_video_node] -> [audit_content_node] -> [END]
"""

from langgraph.graph import StateGraph, END

# Importing State Schema
from backend.src.graph.state import VideoAuditState

# Importing Functional Nodes
from backend.src.graph.nodes import (
    index_video_node,
    audit_content_node
)

def create_graph():
    """
    Constructs and compiles LangGraph workflow.

    Returns:
        CompiledGraph: Runnable graph object ready for execution.
    """
    # 1. Initializing Graph with State Schema
    # This ensures all nodes adhere to 'VideoAuditState' data structure.
    workflow = StateGraph(VideoAuditState)

    # 2. Adding Nodes (Workers)
    # First argument is unique name of node in graph ("indexer", "auditor").
    # Second argument is function to execute (index_video_node, audit_content_node).
    workflow.add_node("indexer", index_video_node)
    workflow.add_node("auditor", audit_content_node)

    # 3. Defining Edges (Logic Flow)
    # Defining entry point: When graph starts, go to 'indexer'.
    workflow.set_entry_point("indexer")

    # Connecting 'indexer' -> 'auditor'
    # Once video is indexed (transcript extracted), moving to compliance auditing.
    workflow.add_edge("indexer", "auditor")

    # Connecting 'auditor' -> END
    # Once audit is complete, workflow finishes.
    workflow.add_edge("auditor", END)

    # 4. Compiling Graph
    # This validates connections and creates executable runnable.
    app = workflow.compile() # This will check for disconnected nodes, cycles, and schema mismatches (Any type of errors will be raised here).

    return app

# Exposing runnable app for import by API or CLI
app = create_graph()