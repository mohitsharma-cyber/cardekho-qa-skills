"""
Advanced Dependency Graph for CarDekho & BikeDekho Architecture.
Models granular relationships between:
- Jira feature
- Screen
- Module
- API
- Navigation
- Business flow
- Existing test cases

Supports hierarchical parent-child structures (e.g. Model Detail ➔ Gallery, Colours, Videos, Variants, Price, Lead CTA).
"""

from enum import Enum
from typing import Dict, List, Set, Optional, Any

class NodeType(str, Enum):
    FEATURE = "FEATURE"
    SCREEN = "SCREEN"
    MODULE = "MODULE"
    API = "API"
    NAVIGATION = "NAVIGATION"
    BUSINESS_FLOW = "BUSINESS_FLOW"
    TEST_CASE = "TEST_CASE"

class RelationType(str, Enum):
    CONTAINS = "CONTAINS"
    SIBLING = "SIBLING"
    DEPENDS_ON = "DEPENDS_ON"
    NAVIGATES_TO = "NAVIGATES_TO"
    CALLS_API = "CALLS_API"
    FEEDS_FLOW = "FEEDS_FLOW"
    TESTS = "TESTS"

class DependencyGraph:
    """Directed, typed dependency graph supporting multi-layer automotive relationships."""

    def __init__(self):
        # Backward-compatible adjacency maps
        self.adj_list: Dict[str, Set[str]] = {}
        self.reverse_adj: Dict[str, Set[str]] = {}

        # Typed nodes and relationship stores
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.typed_edges: Dict[str, Dict[str, Set[str]]] = {}

        self._build_default_graph()

    def register_node(
        self,
        name: str,
        node_type: NodeType,
        display_name: Optional[str] = None,
        parent: Optional[str] = None,
        apis: Optional[List[str]] = None,
        test_cases: Optional[List[str]] = None,
        tags: Optional[List[str]] = None
    ):
        clean_name = name.lower().strip()
        self.nodes[clean_name] = {
            "name": clean_name,
            "display_name": display_name or name,
            "type": node_type.value,
            "parent": parent.lower().strip() if parent else None,
            "children": set(),
            "apis": apis or [],
            "test_cases": test_cases or [],
            "tags": tags or []
        }
        if clean_name not in self.adj_list:
            self.adj_list[clean_name] = set()
        if clean_name not in self.reverse_adj:
            self.reverse_adj[clean_name] = set()
        if clean_name not in self.typed_edges:
            self.typed_edges[clean_name] = {}

        if parent:
            p_clean = parent.lower().strip()
            if p_clean in self.nodes:
                self.nodes[p_clean]["children"].add(clean_name)
            self.add_typed_edge(p_clean, clean_name, RelationType.CONTAINS)

    def add_typed_edge(self, source: str, target: str, relation: RelationType):
        s = source.lower().strip()
        t = target.lower().strip()

        if s not in self.typed_edges:
            self.typed_edges[s] = {}
        if relation.value not in self.typed_edges[s]:
            self.typed_edges[s][relation.value] = set()
        self.typed_edges[s][relation.value].add(t)

        # Mirror in basic adjacency for backward compatibility
        self.add_edge(s, t)

    def add_edge(self, source: str, target: str):
        s = source.lower().strip()
        t = target.lower().strip()
        if s not in self.adj_list:
            self.adj_list[s] = set()
        self.adj_list[s].add(t)

        if t not in self.reverse_adj:
            self.reverse_adj[t] = set()
        self.reverse_adj[t].add(s)

    def _build_default_graph(self):
        """Builds comprehensive automotive domain model with hierarchical clusters."""
        # 1. Register Modules & Screens
        self.register_node("model_details", NodeType.SCREEN, display_name="Model Detail", tags=["core_pdp"])
        self.register_node("home", NodeType.SCREEN, display_name="Home Screen", tags=["top_level"])
        self.register_node("search", NodeType.SCREEN, display_name="Global Search", tags=["discovery"])
        self.register_node("drawer", NodeType.NAVIGATION, display_name="Navigation Drawer")
        self.register_node("change_url", NodeType.SCREEN, display_name="Change URL Environment")
        self.register_node("auth", NodeType.MODULE, display_name="Authentication / Login")
        self.register_node("news", NodeType.MODULE, display_name="News & Editorial")
        self.register_node("used_cars", NodeType.MODULE, display_name="Used Cars Marketplace")

        # 2. Model Detail Tree (as specified in prompt):
        # Model Detail
        #  ├── Gallery
        #  ├── Colours
        #  ├── Videos
        #  ├── Variants
        #  ├── Price
        #  └── Lead CTA
        self.register_node(
            "gallery", NodeType.FEATURE, display_name="Gallery",
            parent="model_details",
            apis=["/api/v1/model/gallery", "/api/v1/model/overview"],
            test_cases=["TC-GALLERY-01", "TC-GALLERY-02"]
        )
        self.register_node(
            "colours", NodeType.FEATURE, display_name="Colours",
            parent="model_details",
            apis=["/api/v1/model/colors"],
            test_cases=["TC-COLOURS-01"]
        )
        self.register_node(
            "videos", NodeType.FEATURE, display_name="Videos",
            parent="model_details",
            apis=["/api/v1/model/videos"],
            test_cases=["TC-VIDEOS-01"]
        )
        self.register_node(
            "variants", NodeType.FEATURE, display_name="Variants",
            parent="model_details",
            apis=["/api/v1/model/variants"],
            test_cases=["TC-VARIANTS-01", "TC-VARIANTS-02"]
        )
        self.register_node(
            "price", NodeType.FEATURE, display_name="Price",
            parent="model_details",
            apis=["/api/v1/price"],
            test_cases=["TC-PRICE-01", "TC-PRICE-02"]
        )
        self.register_node(
            "lead_cta", NodeType.FEATURE, display_name="Lead CTA",
            parent="model_details",
            apis=["/api/v1/lead/submit"],
            test_cases=["TC-LEAD-01"]
        )

        # 3. Model Navigation & Sibling cluster links
        self.register_node("model_navigation", NodeType.NAVIGATION, display_name="Model navigation")
        self.add_typed_edge("model_details", "model_navigation", RelationType.CONTAINS)
        self.add_typed_edge("gallery", "model_navigation", RelationType.NAVIGATES_TO)
        self.add_typed_edge("colours", "model_navigation", RelationType.NAVIGATES_TO)
        self.add_typed_edge("videos", "model_navigation", RelationType.NAVIGATES_TO)
        self.add_typed_edge("variants", "model_navigation", RelationType.NAVIGATES_TO)
        self.add_typed_edge("price", "model_navigation", RelationType.NAVIGATES_TO)

        # Siblings in media cluster
        self.add_typed_edge("gallery", "colours", RelationType.SIBLING)
        self.add_typed_edge("gallery", "videos", RelationType.SIBLING)
        self.add_typed_edge("colours", "videos", RelationType.SIBLING)

        # Siblings in price/variant cluster
        self.register_node("emi_calculator", NodeType.FEATURE, display_name="EMI Calculator", parent="model_details")
        self.add_typed_edge("price", "variants", RelationType.SIBLING)
        self.add_typed_edge("price", "emi_calculator", RelationType.SIBLING)
        self.add_typed_edge("price", "lead_cta", RelationType.DEPENDS_ON)

        # Legacy direct edge mapping for backward compatibility
        legacy_edges = [
            ("change_url", "api_gateway"),
            ("api_gateway", "home"),
            ("api_gateway", "search"),
            ("api_gateway", "model_details"),
            ("api_gateway", "price_tab"),
            ("api_gateway", "lead_form"),
            ("drawer", "home"),
            ("drawer", "change_url"),
            ("drawer", "search"),
            ("drawer", "auth"),
            ("home", "search"),
            ("search", "search_engine"),
            ("search_engine", "model_details"),
            ("model_details", "variant_details"),
            ("model_details", "price_tab"),
            ("model_details", "reviews"),
            ("model_details", "lead_form"),
            ("pricing_engine", "price_tab"),
            ("pricing_engine", "emi_calculator"),
            ("pricing_engine", "variant_details"),
            ("price_tab", "lead_form"),
            ("price_tab", "variant_details"),
            ("price_tab", "emi_calculator"),
            ("auth", "lead_form"),
            ("auth", "reviews"),
            ("lead_flow", "lead_form")
        ]
        for u, v in legacy_edges:
            self.add_edge(u, v)

    def get_feature_hierarchy(self, feature_name: str) -> Dict[str, Any]:
        """
        Retrieves parent container, siblings, related APIs, navigation components,
        and test cases for a target feature.
        """
        fn = feature_name.lower().strip()
        node = self.nodes.get(fn)
        if not node:
            # Fallback fuzzy match
            for k in self.nodes:
                if fn in k or k in fn:
                    node = self.nodes[k]
                    fn = k
                    break

        if not node:
            return {
                "name": feature_name,
                "display_name": feature_name,
                "parent": None,
                "siblings": [],
                "children": [],
                "apis": [],
                "navigation": [],
                "test_cases": []
            }

        parent_name = node.get("parent")
        siblings = []
        canonical_order = ["Gallery", "Colours", "Videos", "Variants", "Price", "Lead CTA", "EMI Calculator"]
        if parent_name and parent_name in self.nodes:
            parent_node = self.nodes[parent_name]
            raw_sibs = [
                self.nodes[c]["display_name"]
                for c in parent_node.get("children", set())
                if c != fn and c in self.nodes
            ]
            # Deterministic sorting respecting canonical hierarchy
            siblings = sorted(
                raw_sibs,
                key=lambda s: canonical_order.index(s) if s in canonical_order else 999
            )

        # Gather outgoing typed relations
        typed = self.typed_edges.get(fn, {})
        navs = [
            self.nodes[target]["display_name"]
            for target in typed.get(RelationType.NAVIGATES_TO.value, set())
            if target in self.nodes
        ]
        if not navs and parent_name:
            # Check parent navigation
            p_typed = self.typed_edges.get(parent_name, {})
            navs = [
                self.nodes[target]["display_name"]
                for target in p_typed.get(RelationType.CONTAINS.value, set())
                if "navigation" in target and target in self.nodes
            ]

        apis = node.get("apis", [])
        tests = node.get("test_cases", [])

        return {
            "name": fn,
            "display_name": node.get("display_name", feature_name),
            "parent": parent_name,
            "parent_display": self.nodes[parent_name]["display_name"] if parent_name in self.nodes else None,
            "siblings": siblings,
            "children": [self.nodes[c]["display_name"] for c in node.get("children", set()) if c in self.nodes],
            "apis": apis,
            "navigation": navs or ["Model navigation"],
            "test_cases": tests
        }

    def get_unrelated_modules(self, target_area: str) -> List[str]:
        """
        Identifies modules outside the blast radius of the target area
        to justify their exclusion from regression.
        """
        ta = target_area.lower().strip()
        if "gallery" in ta or "colour" in ta or "video" in ta or "model" in ta or "spec" in ta or "variant" in ta or "price" in ta:
            return ["Unrelated Home modules", "News", "Used Cars"]
        elif "search" in ta:
            return ["Price calculator", "News", "Used Cars appraisal", "Service Cost"]
        elif "auth" in ta:
            return ["Search autosuggest", "News articles", "Gallery full screen view"]
        elif "change_url" in ta:
            return ["News editorial", "Used Cars valuation"]
        return ["Unrelated Home modules", "News", "Used Cars"]

    def get_downstream_impacts(self, nodes: List[str], max_depth: int = 1) -> Set[str]:
        """Finds direct downstream dependencies up to max_depth."""
        visited: Set[str] = set()
        queue = [(n.lower().strip(), 0) for n in nodes]

        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            neighbors = self.adj_list.get(current, set())
            for neighbor in neighbors:
                if neighbor not in visited and neighbor not in [n.lower().strip() for n in nodes]:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))

        return visited

    def get_upstream_dependencies(self, node: str) -> Set[str]:
        return self.reverse_adj.get(node.lower().strip(), set())
