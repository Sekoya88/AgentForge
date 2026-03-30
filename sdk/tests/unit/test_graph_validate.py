import pytest
from pydantic import ValidationError
from agentforge.graph_validate import (
    GraphDefinitionValidated,
    GraphEdge,
    GraphNode,
    parse_and_validate_graph,
)


class TestParseAndValidateGraph:
    def test_valid_single_node(self):
        raw = {
            "nodes": [{"id": "n1", "type": "llm", "config": {}}],
            "edges": [],
            "entry_point": "n1",
        }
        gd = parse_and_validate_graph(raw)
        assert gd.entry_point == "n1"
        assert len(gd.nodes) == 1

    def test_auto_entry_point_from_first_node(self):
        raw = {
            "nodes": [{"id": "first", "type": "llm", "config": {}}],
        }
        gd = parse_and_validate_graph(raw)
        assert gd.entry_point == "first"

    def test_empty_nodes_raises(self):
        with pytest.raises(ValueError, match="nodes must be non-empty"):
            parse_and_validate_graph({"nodes": []})

    def test_none_input_raises(self):
        with pytest.raises(ValueError, match="nodes must be non-empty"):
            parse_and_validate_graph(None)

    def test_entry_point_not_in_nodes_raises(self):
        raw = {
            "nodes": [{"id": "n1", "type": "llm", "config": {}}],
            "entry_point": "nonexistent",
        }
        with pytest.raises(ValueError, match="entry_point"):
            parse_and_validate_graph(raw)

    def test_edge_from_unknown_node_raises(self):
        raw = {
            "nodes": [{"id": "n1", "type": "llm", "config": {}}],
            "edges": [{"from": "unknown", "to": "n1"}],
            "entry_point": "n1",
        }
        with pytest.raises(ValueError, match="edge from unknown node"):
            parse_and_validate_graph(raw)

    def test_edge_to_unknown_node_raises(self):
        raw = {
            "nodes": [{"id": "n1", "type": "llm", "config": {}}],
            "edges": [{"from": "n1", "to": "unknown"}],
            "entry_point": "n1",
        }
        with pytest.raises(ValueError, match="edge to unknown node"):
            parse_and_validate_graph(raw)

    def test_edge_to_end_is_valid(self):
        raw = {
            "nodes": [{"id": "n1", "type": "llm", "config": {}}],
            "edges": [{"from": "n1", "to": "END"}],
            "entry_point": "n1",
        }
        gd = parse_and_validate_graph(raw)
        assert gd.edges[0].to == "END"

    def test_edge_from_start_is_valid(self):
        raw = {
            "nodes": [{"id": "n1", "type": "llm", "config": {}}],
            "edges": [{"from": "START", "to": "n1"}],
            "entry_point": "n1",
        }
        gd = parse_and_validate_graph(raw)
        assert gd.edges[0].from_ == "START"

    def test_parallel_nodes_valid(self):
        raw = {
            "nodes": [
                {"id": "a", "type": "llm", "config": {}},
                {"id": "b", "type": "llm", "config": {}},
            ],
            "entry_point": "a",
            "parallel_nodes": ["a", "b"],
        }
        gd = parse_and_validate_graph(raw)
        assert "a" in gd.parallel_nodes

    def test_parallel_node_unknown_raises(self):
        raw = {
            "nodes": [{"id": "n1", "type": "llm", "config": {}}],
            "entry_point": "n1",
            "parallel_nodes": ["ghost"],
        }
        with pytest.raises(ValueError, match="parallel_nodes references unknown"):
            parse_and_validate_graph(raw)

    def test_to_dict_round_trip(self):
        raw = {
            "nodes": [{"id": "n1", "type": "llm", "config": {}}],
            "edges": [{"from": "n1", "to": "END"}],
            "entry_point": "n1",
        }
        gd = parse_and_validate_graph(raw)
        d = gd.to_dict()
        assert d["entry_point"] == "n1"
        assert d["edges"][0]["from"] == "n1"

    def test_schema_version_default(self):
        raw = {"nodes": [{"id": "n1", "config": {}}], "entry_point": "n1"}
        gd = parse_and_validate_graph(raw)
        assert gd.graph_schema_version == "1.0"

    def test_custom_schema_version(self):
        raw = {
            "nodes": [{"id": "n1", "config": {}}],
            "entry_point": "n1",
            "graph_schema_version": "2.0",
        }
        gd = parse_and_validate_graph(raw)
        assert gd.graph_schema_version == "2.0"
