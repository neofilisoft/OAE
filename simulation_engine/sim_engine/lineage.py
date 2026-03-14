from __future__ import annotations

from collections import Counter, deque
from typing import Iterable

import networkx as nx

from .models import Entity


class LineageEngine:
    def __init__(self) -> None:
        self.graph = nx.DiGraph()
        self.entities: dict[str, Entity] = {}

    def add_entity(self, entity: Entity) -> None:
        entity_id = entity.identity.entity_id
        self.entities[entity_id] = entity
        self.graph.add_node(entity_id)
        for parent_id in entity.parent_ids:
            self.add_parent_child_relation(parent_id, entity_id)

    def get_entity(self, entity_id: str) -> Entity:
        return self.entities[entity_id]

    def add_parent_child_relation(self, parent_id: str, child_id: str) -> None:
        if parent_id == child_id:
            raise ValueError("entity cannot be its own parent")
        self.graph.add_node(parent_id)
        self.graph.add_node(child_id)
        self.graph.add_edge(parent_id, child_id)
        if nx.is_directed_acyclic_graph(self.graph) is False:
            self.graph.remove_edge(parent_id, child_id)
            raise ValueError("lineage graph must remain acyclic")
        if parent_id in self.entities:
            self.entities[parent_id].add_offspring(child_id)
        if child_id in self.entities:
            self.entities[child_id].add_parent(parent_id)
            if len(self.entities[child_id].parent_ids) > 2:
                raise ValueError("child cannot have more than two biological parents in this model")

    def ancestors(self, entity_id: str, max_depth: int | None = None) -> dict[str, int]:
        if entity_id not in self.graph:
            return {}
        result: dict[str, int] = {}
        queue = deque([(entity_id, 0)])
        while queue:
            current, depth = queue.popleft()
            if max_depth is not None and depth >= max_depth:
                continue
            for parent in self.graph.predecessors(current):
                parent_depth = depth + 1
                if parent not in result or parent_depth < result[parent]:
                    result[parent] = parent_depth
                    queue.append((parent, parent_depth))
        return result

    def descendants(self, entity_id: str, max_depth: int | None = None) -> dict[str, int]:
        if entity_id not in self.graph:
            return {}
        result: dict[str, int] = {}
        queue = deque([(entity_id, 0)])
        while queue:
            current, depth = queue.popleft()
            if max_depth is not None and depth >= max_depth:
                continue
            for child in self.graph.successors(current):
                child_depth = depth + 1
                if child not in result or child_depth < result[child]:
                    result[child] = child_depth
                    queue.append((child, child_depth))
        return result

    def ancestor_depth(self, ancestor_id: str, descendant_id: str) -> int | None:
        return self.ancestors(descendant_id).get(ancestor_id)

    def common_ancestors(self, first_id: str, second_id: str) -> dict[str, tuple[int, int]]:
        first_ancestors = self.ancestors(first_id)
        second_ancestors = self.ancestors(second_id)
        shared = set(first_ancestors).intersection(second_ancestors)
        return {ancestor: (first_ancestors[ancestor], second_ancestors[ancestor]) for ancestor in shared}

    def kinship_coefficient(self, first_id: str, second_id: str, max_depth: int = 8) -> float:
        if first_id == second_id:
            return 1.0
        first_anc = self.ancestors(first_id, max_depth=max_depth)
        second_anc = self.ancestors(second_id, max_depth=max_depth)
        coeff = 0.0
        if second_id in first_anc:
            coeff += 0.5 ** first_anc[second_id]
        if first_id in second_anc:
            coeff += 0.5 ** second_anc[first_id]
        for ancestor in set(first_anc).intersection(second_anc):
            d1 = first_anc[ancestor]
            d2 = second_anc[ancestor]
            coeff += 0.5 ** (d1 + d2)
        return round(min(coeff, 1.0), 6)

    def bloodline_purity_score(self, entity_id: str, founder_tag: str) -> float:
        entity = self.entities[entity_id]
        own_tags = entity.genome.founder_tags
        own_score = 1.0 if founder_tag in own_tags else 0.0
        ancestors = self.ancestors(entity_id, max_depth=8)
        weighted = own_score
        total_weight = 1.0
        for ancestor_id, depth in ancestors.items():
            ancestor_entity = self.entities.get(ancestor_id)
            if ancestor_entity is None:
                continue
            weight = 0.5 ** depth
            total_weight += weight
            if founder_tag in ancestor_entity.genome.founder_tags:
                weighted += weight
        return round(weighted / total_weight, 6) if total_weight else 0.0

    def family_branch(self, entity_id: str) -> str:
        entity = self.entities[entity_id]
        if entity.legal.branch_label:
            return entity.legal.branch_label
        ancestors = self.ancestors(entity_id, max_depth=3)
        if not ancestors:
            return f"{entity.identity.family_id}:root"
        closest = min(ancestors.items(), key=lambda item: item[1])[0]
        founder = self.entities[closest]
        return f"{entity.identity.family_id}:{founder.name.lower().replace(' ', '_')}"

    def inheritance_rights_score(self, entity_id: str) -> float:
        entity = self.entities[entity_id]
        score = 1.0
        if not entity.legal.is_recognized_offspring:
            score *= 0.25
        score *= entity.legal.rights_multiplier
        score *= max(0.1, entity.identity.trust_score)
        purity_bonus = entity.genome.fitness_score * 0.15 + entity.genome.heterozygosity() * 0.15
        return round(score + purity_bonus, 6)

    def dominant_traits(self, entity_id: str) -> dict[str, str]:
        entity = self.entities[entity_id]
        result: dict[str, str] = {}
        for locus, pair in entity.genome.loci.items():
            result[locus] = pair.dominant_allele()
        return result

    def prevent_inbreeding(self, first_id: str, second_id: str, threshold: float = 0.125) -> tuple[bool, float]:
        kinship = self.kinship_coefficient(first_id, second_id)
        return kinship < threshold, kinship

    def legal_social_overlay(self, entity_id: str) -> dict[str, object]:
        entity = self.entities[entity_id]
        return {
            "inheritance_group": entity.legal.inheritance_group,
            "branch": self.family_branch(entity_id),
            "recognized": entity.legal.is_recognized_offspring,
            "social_links": entity.social_links,
            "rights_score": self.inheritance_rights_score(entity_id),
        }

    def lineage_summary(self, entity_id: str) -> dict[str, object]:
        entity = self.entities[entity_id]
        ancestor_map = self.ancestors(entity_id, max_depth=6)
        descendant_map = self.descendants(entity_id, max_depth=6)
        founder_counts = Counter()
        for related_id in [entity_id, *ancestor_map.keys()]:
            related = self.entities.get(related_id)
            if related:
                founder_counts.update(related.genome.founder_tags)
        return {
            "entity_id": entity_id,
            "name": entity.name,
            "parents": list(self.graph.predecessors(entity_id)),
            "children": list(self.graph.successors(entity_id)),
            "ancestors": ancestor_map,
            "descendants": descendant_map,
            "branch": self.family_branch(entity_id),
            "founder_tag_distribution": dict(founder_counts),
            "heterozygosity": entity.genome.heterozygosity(),
        }

    def subgraph(self, entity_ids: Iterable[str]) -> nx.DiGraph:
        return self.graph.subgraph(entity_ids).copy()
