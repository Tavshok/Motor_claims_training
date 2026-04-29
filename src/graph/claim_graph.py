# src/graph/claim_graph.py
"""
Convert a fused claim dict into a networkx graph and export to GraphML.
Nodes: components, images, documents, cost items
Edges: relationships like HAS_DAMAGE, SHOWN_IN, COSTS, SUPPORTS, CONTRADICTS
"""

import networkx as nx
from typing import Dict, Any
from pathlib import Path

def build_claim_graph(claim: Dict[str, Any], claim_id: str) -> nx.MultiDiGraph:
    """
    Build a directed multi-graph representing the claim.
    Node types: 'component', 'image', 'document', 'cost_item'
    """
    G = nx.MultiDiGraph()

    # ── Document node ──
    doc_id = f"doc_{claim_id}"
    G.add_node(doc_id, type="document", file_name=claim["file_name"])

    # ── Vehicle node (optional) ──
    vehicle = claim.get("vehicle", {})
    if any(v for v in vehicle.values()):
        veh_id = f"veh_{claim_id}"
        G.add_node(veh_id, type="vehicle", **vehicle)
        G.add_edge(doc_id, veh_id, relationship="DESCRIBES")

    # ── Component nodes ──
    for comp in claim.get("damage_components", []):
        comp_id = f"comp_{claim_id}_{comp['component_id']}"
        G.add_node(comp_id, type="component", **comp)
        G.add_edge(doc_id, comp_id, relationship="HAS_DAMAGE")

        # Link images that detect this component
        for img_link in comp.get("linked_image_detections", []):
            img_id = f"img_{claim_id}_{img_link['image_path']}"
            # Ensure image node exists
            if not G.has_node(img_id):
                G.add_node(img_id, type="image",
                           image_path=img_link["image_path"],
                           page_number=img_link["page_number"])
            G.add_edge(comp_id, img_id, relationship="SHOWN_IN",
                       confidence=img_link["confidence"],
                       bbox=img_link["bbox"])

    # ── Cost item nodes ──
    for cost in claim.get("cost_breakdown", []):
        cost_id = f"cost_{claim_id}_{cost['description'][:20].replace(' ', '_')}"
        G.add_node(cost_id, type="cost_item",
                   description=cost["description"],
                   amount_usd=cost["amount_usd"],
                   original_currency=cost["original_currency"],
                   component_id=cost["component_id"])
        # Link to document
        G.add_edge(doc_id, cost_id, relationship="HAS_COST")
        # Link to component if mapped
        if cost["component_id"]:
            target_comp_id = f"comp_{claim_id}_{cost['component_id']}"
            if G.has_node(target_comp_id):
                G.add_edge(cost_id, target_comp_id, relationship="FOR_COMPONENT")

    # ── Image nodes not yet created from components (full page images) ──
    for img_meta in claim.get("images", []):
        img_id = f"img_{claim_id}_{img_meta['image_path']}"
        if not G.has_node(img_id):
            G.add_node(img_id, type="image",
                       image_path=img_meta["image_path"],
                       page_number=img_meta["page_number"])
        # Link image to document
        G.add_edge(doc_id, img_id, relationship="CONTAINS_IMAGE")
        # Link detections that didn't match a component (or add their relationships)
        for det in img_meta.get("detections", []):
            # Check if any existing component node matches
            matched = False
            for node in G.nodes():
                if G.nodes[node].get("type") == "component":
                    comp_name = G.nodes[node].get("canonical_name", "").lower()
                    if comp_name in det["label"].lower():
                        G.add_edge(node, img_id, relationship="SHOWN_IN",
                                   confidence=det["confidence"], bbox=det["bbox"])
                        matched = True
                        break
            if not matched:
                # Orphan detection node
                det_id = f"det_{claim_id}_{det['label'].replace(' ', '_')[:30]}"
                if not G.has_node(det_id):
                    G.add_node(det_id, type="detection",
                               label=det["label"],
                               confidence=det["confidence"],
                               bbox=det["bbox"])
                G.add_edge(img_id, det_id, relationship="HAS_DETECTION")

    return G

def export_graph(G: nx.MultiDiGraph, output_path: Path):
    """Write graph to GraphML format."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    nx.write_graphml(G, str(output_path))