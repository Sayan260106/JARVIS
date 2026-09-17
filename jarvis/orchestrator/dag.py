"""Directed Acyclic Graph (DAG) for Task Dependencies.

Provides topological sorting, cycle detection, execution layering,
and ready-node discovery for complex agent workflows.
"""

from __future__ import annotations
from collections import deque
from typing import Dict, List, Optional, Set

from jarvis.orchestrator.schemas import NodeStatus, TaskNode


class TaskDAG:
    """Directed Acyclic Graph managing task execution dependencies."""

    def __init__(self, name: str = "Master Task DAG"):
        self.name = name
        self.nodes: Dict[str, TaskNode] = {}
        self.adjacency: Dict[str, List[str]] = {}       # parent -> list of children
        self.in_degree: Dict[str, int] = {}             # node -> count of unsatisfied parents

    def add_node(self, node: TaskNode) -> None:
        """Adds a task node to the DAG."""
        self.nodes[node.node_id] = node
        if node.node_id not in self.adjacency:
            self.adjacency[node.node_id] = []
        if node.node_id not in self.in_degree:
            self.in_degree[node.node_id] = len(node.depends_on)

        for dep in node.depends_on:
            if dep not in self.adjacency:
                self.adjacency[dep] = []
            if node.node_id not in self.adjacency[dep]:
                self.adjacency[dep].append(node.node_id)

    def add_dependency(self, child_id: str, parent_id: str) -> None:
        """Explicitly links a child node to depend on a parent node."""
        if child_id in self.nodes:
            if parent_id not in self.nodes[child_id].depends_on:
                self.nodes[child_id].depends_on.append(parent_id)
        if parent_id not in self.adjacency:
            self.adjacency[parent_id] = []
        if child_id not in self.adjacency[parent_id]:
            self.adjacency[parent_id].append(child_id)
        self.in_degree[child_id] = len(self.nodes[child_id].depends_on) if child_id in self.nodes else 0

    def get_node(self, node_id: str) -> Optional[TaskNode]:
        """Fetches node by identifier."""
        return self.nodes.get(node_id)

    def validate(self) -> bool:
        """Validates graph consistency: all dependency IDs must exist and no cycles exist."""
        # 1. Check all referenced dependencies exist
        for nid, node in self.nodes.items():
            for dep in node.depends_on:
                if dep not in self.nodes:
                    raise ValueError(f"Node '{nid}' depends on non-existent node '{dep}'.")

        # 2. Check for cycles via topological sort simulation
        try:
            self.topological_sort()
            return True
        except ValueError:
            return False

    def topological_sort(self) -> List[TaskNode]:
        """Returns nodes in topological dependency order. Raises ValueError if cycle detected."""
        in_deg = {nid: len(node.depends_on) for nid, node in self.nodes.items()}
        queue = deque([nid for nid, deg in in_deg.items() if deg == 0])
        sorted_nodes: List[TaskNode] = []

        while queue:
            curr_id = queue.popleft()
            sorted_nodes.append(self.nodes[curr_id])

            for child_id in self.adjacency.get(curr_id, []):
                in_deg[child_id] -= 1
                if in_deg[child_id] == 0:
                    queue.append(child_id)

        if len(sorted_nodes) != len(self.nodes):
            raise ValueError("Cycle detected in Task DAG! Dependencies must form an acyclic graph.")

        return sorted_nodes

    def get_execution_levels(self) -> List[List[TaskNode]]:
        """Partitions nodes into discrete execution levels (tiers) based on maximum distance from root."""
        sorted_nodes = self.topological_sort()
        levels: Dict[str, int] = {}

        for node in sorted_nodes:
            if not node.depends_on:
                levels[node.node_id] = 0
            else:
                levels[node.node_id] = max(levels[dep] for dep in node.depends_on) + 1

        max_level = max(levels.values()) if levels else 0
        tiers: List[List[TaskNode]] = [[] for _ in range(max_level + 1)]
        for node in sorted_nodes:
            tiers[levels[node.node_id]].append(node)

        return tiers

    def get_ready_nodes(self) -> List[TaskNode]:
        """Returns all PENDING nodes whose dependencies have all completed successfully."""
        ready: List[TaskNode] = []
        for nid, node in self.nodes.items():
            if node.status != NodeStatus.PENDING:
                continue

            # Check all parent dependencies
            deps_met = True
            for parent_id in node.depends_on:
                parent = self.nodes.get(parent_id)
                if not parent or parent.status != NodeStatus.COMPLETED:
                    deps_met = False
                    break

            if deps_met:
                ready.append(node)

        return ready

    def is_complete(self) -> bool:
        """Returns True if every node is in a terminal state (COMPLETED, FAILED, or SKIPPED)."""
        terminal_statuses = {NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.SKIPPED}
        return all(node.status in terminal_statuses for node in self.nodes.values())

    def has_failures(self) -> bool:
        """Returns True if any node has failed."""
        return any(node.status == NodeStatus.FAILED for node in self.nodes.values())
