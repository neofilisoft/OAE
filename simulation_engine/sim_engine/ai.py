from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Any

import networkx as nx
import numpy as np
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest

from .lineage import LineageEngine
from .models import AllelePair, Entity


class AIAdvisor:
    def __init__(self, lineage: LineageEngine) -> None:
        self.lineage = lineage
        self.anomaly_model = IsolationForest(random_state=42, contamination=0.15)
        self._anomaly_fitted = False
        self.cluster_model: KMeans | None = None

    def _entity_vector(self, entity: Entity) -> np.ndarray:
        dominant_count = sum(1 for pair in entity.genome.loci.values() if pair.first.isupper() or pair.second.isupper())
        recessive_pairs = sum(1 for pair in entity.genome.loci.values() if pair.first == pair.second and pair.first.islower())
        vector = np.array(
            [
                float(entity.age),
                float(entity.identity.generation_index),
                float(entity.identity.trust_score),
                float(entity.genome.fitness_score),
                float(entity.genome.heterozygosity()),
                float(len(entity.parent_ids)),
                float(len(entity.offspring_ids)),
                float(len(entity.genome.founder_tags)),
                float(dominant_count),
                float(recessive_pairs),
            ],
            dtype=float,
        )
        return vector

    def mate_recommendation(
        self,
        entity_id: str,
        candidate_ids: list[str] | None = None,
        max_results: int = 5,
        inbreeding_threshold: float = 0.125,
    ) -> list[dict[str, Any]]:
        subject = self.lineage.get_entity(entity_id)
        candidates = candidate_ids or [eid for eid in self.lineage.entities if eid != entity_id]
        recommendations: list[dict[str, Any]] = []
        for candidate_id in candidates:
            if candidate_id == entity_id:
                continue
            candidate = self.lineage.get_entity(candidate_id)
            allow, kinship = self.lineage.prevent_inbreeding(entity_id, candidate_id, threshold=inbreeding_threshold)
            if not allow or not candidate.alive or not subject.alive:
                continue
            diversity = self._pair_diversity(subject, candidate)
            trust = (subject.identity.trust_score + candidate.identity.trust_score) / 2.0
            fitness = (subject.genome.fitness_score + candidate.genome.fitness_score) / 2.0
            age_alignment = 1.0 - min(abs(subject.age - candidate.age) / 100.0, 1.0)
            composite = 0.4 * diversity + 0.25 * trust + 0.25 * fitness + 0.10 * age_alignment
            recommendations.append(
                {
                    "candidate_id": candidate_id,
                    "candidate_name": candidate.name,
                    "score": round(composite, 6),
                    "diversity": round(diversity, 6),
                    "kinship": kinship,
                    "trust": round(trust, 6),
                    "fitness": round(fitness, 6),
                    "explanation": self.explain_mate_score(subject, candidate, composite, diversity, kinship, trust, fitness),
                }
            )
        recommendations.sort(key=lambda item: item["score"], reverse=True)
        return recommendations[:max_results]

    def _pair_diversity(self, first: Entity, second: Entity) -> float:
        shared_loci = set(first.genome.loci).union(second.genome.loci)
        if not shared_loci:
            return 0.0
        diversity_sum = 0.0
        for locus in shared_loci:
            a = first.genome.loci.get(locus)
            b = second.genome.loci.get(locus)
            if a and b:
                diversity_sum += 1.0 if a.canonical_tuple() != b.canonical_tuple() else 0.0
            else:
                diversity_sum += 0.5
        return diversity_sum / len(shared_loci)

    def predict_offspring_traits(self, parent_a_id: str, parent_b_id: str, samples: int = 512) -> dict[str, Any]:
        parent_a = self.lineage.get_entity(parent_a_id)
        parent_b = self.lineage.get_entity(parent_b_id)
        rng = np.random.default_rng(42)
        loci = sorted(set(parent_a.genome.loci).union(parent_b.genome.loci))
        outcomes: dict[str, Counter[str]] = {locus: Counter() for locus in loci}
        mutation_risk = Counter[str]()
        for _ in range(samples):
            for locus in loci:
                pair_a = parent_a.genome.loci.get(locus, AllelePair(first="x", second="x"))
                pair_b = parent_b.genome.loci.get(locus, AllelePair(first="x", second="x"))
                inherited = AllelePair(
                    first=rng.choice([pair_a.first, pair_a.second]).item(),
                    second=rng.choice([pair_b.first, pair_b.second]).item(),
                )
                key = "/".join(inherited.canonical_tuple())
                outcomes[locus][key] += 1
                if inherited.first == inherited.second and inherited.first.islower():
                    mutation_risk[locus] += 1
        return {
            "parents": [parent_a_id, parent_b_id],
            "trait_distribution": {
                locus: {genotype: round(count / samples, 6) for genotype, count in counter.items()}
                for locus, counter in outcomes.items()
            },
            "recessive_risk": {locus: round(count / samples, 6) for locus, count in mutation_risk.items()},
            "summary": self._trait_prediction_summary(outcomes, mutation_risk, samples),
        }

    def _trait_prediction_summary(self, outcomes: dict[str, Counter[str]], risk: Counter[str], samples: int) -> list[str]:
        notes: list[str] = []
        for locus, counter in outcomes.items():
            top_genotype, count = counter.most_common(1)[0]
            notes.append(f"{locus}: likely genotype {top_genotype} ({count / samples:.1%})")
        for locus, count in risk.items():
            probability = count / samples
            if probability >= 0.25:
                notes.append(f"{locus}: elevated recessive-expression risk ({probability:.1%})")
        return notes

    def anomaly_detection(self) -> list[dict[str, Any]]:
        entity_ids = list(self.lineage.entities.keys())
        if not entity_ids:
            return []
        matrix = np.vstack([self._entity_vector(self.lineage.get_entity(eid)) for eid in entity_ids])
        self.anomaly_model.fit(matrix)
        self._anomaly_fitted = True
        scores = self.anomaly_model.decision_function(matrix)
        labels = self.anomaly_model.predict(matrix)
        anomalies: list[dict[str, Any]] = []
        for entity_id, score, label in zip(entity_ids, scores, labels, strict=True):
            if label == -1:
                entity = self.lineage.get_entity(entity_id)
                anomalies.append(
                    {
                        "entity_id": entity_id,
                        "name": entity.name,
                        "anomaly_score": round(float(score), 6),
                        "reason": self._heuristic_anomaly_reason(entity),
                    }
                )
        anomalies.sort(key=lambda item: item["anomaly_score"])
        return anomalies

    def _heuristic_anomaly_reason(self, entity: Entity) -> str:
        if entity.identity.trust_score < 0.3:
            return "low trust score"
        if len(entity.parent_ids) > 2:
            return "invalid parent count"
        if entity.age == 0 and entity.lifecycle_state.value not in {"embryo", "infant"}:
            return "age-state mismatch"
        if entity.crypto.content_hash and not entity.crypto.signed_snapshot:
            return "partial cryptographic identity"
        return "feature outlier"

    def lineage_clustering(self, n_clusters: int = 3) -> dict[str, int]:
        entity_ids = list(self.lineage.entities.keys())
        if len(entity_ids) < n_clusters:
            n_clusters = max(1, len(entity_ids))
        if n_clusters == 0:
            return {}
        matrix = np.vstack([self._entity_vector(self.lineage.get_entity(eid)) for eid in entity_ids])
        self.cluster_model = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
        labels = self.cluster_model.fit_predict(matrix)
        return {entity_id: int(label) for entity_id, label in zip(entity_ids, labels, strict=True)}

    def mutation_pattern_analysis(self) -> dict[str, Any]:
        locus_counter = Counter()
        reason_counter = Counter()
        transitions = Counter()
        for entity in self.lineage.entities.values():
            for record in entity.genome.mutation_history:
                locus_counter[record.locus] += 1
                reason_counter[record.reason] += 1
                transitions[f"{'/'.join(record.previous.canonical_tuple())}->{'/'.join(record.current.canonical_tuple())}"] += 1
        return {
            "locus_frequency": dict(locus_counter),
            "reason_frequency": dict(reason_counter),
            "transitions": dict(transitions),
        }

    def identity_fraud_detection(self) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        seen_hashes: dict[str, str] = {}
        for entity in self.lineage.entities.values():
            content_hash = entity.crypto.content_hash
            if not content_hash:
                findings.append(
                    {
                        "entity_id": entity.identity.entity_id,
                        "severity": "medium",
                        "reason": "missing content hash",
                    }
                )
                continue
            if content_hash in seen_hashes and seen_hashes[content_hash] != entity.identity.entity_id:
                findings.append(
                    {
                        "entity_id": entity.identity.entity_id,
                        "severity": "high",
                        "reason": f"duplicate snapshot hash with {seen_hashes[content_hash]}",
                    }
                )
            else:
                seen_hashes[content_hash] = entity.identity.entity_id
            if len(entity.parent_ids) != len(set(entity.parent_ids)):
                findings.append(
                    {
                        "entity_id": entity.identity.entity_id,
                        "severity": "high",
                        "reason": "duplicate parent references",
                    }
                )
        return findings

    def explainability_report(self, entity_id: str) -> dict[str, Any]:
        entity = self.lineage.get_entity(entity_id)
        recommendations = self.mate_recommendation(entity_id, max_results=3)
        lineage = self.lineage.lineage_summary(entity_id)
        anomalies = [item for item in self.anomaly_detection() if item["entity_id"] == entity_id]
        return {
            "entity": entity.name,
            "identity": entity.identity.model_dump(),
            "lineage": lineage,
            "top_mate_recommendations": recommendations,
            "anomalies": anomalies,
            "derived_signals": {
                "heterozygosity": entity.genome.heterozygosity(),
                "inheritance_rights": self.lineage.inheritance_rights_score(entity_id),
                "dominant_traits": self.lineage.dominant_traits(entity_id),
            },
        }

    def relationship_matrix(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for first_id, second_id in combinations(self.lineage.entities.keys(), 2):
            rows.append(
                {
                    "first_id": first_id,
                    "second_id": second_id,
                    "kinship": self.lineage.kinship_coefficient(first_id, second_id),
                }
            )
        return rows

    def graph_centrality(self) -> dict[str, float]:
        if len(self.lineage.graph) == 0:
            return {}
        centrality = nx.betweenness_centrality(self.lineage.graph)
        return {entity_id: round(score, 6) for entity_id, score in centrality.items()}

    def explain_mate_score(
        self,
        subject: Entity,
        candidate: Entity,
        composite: float,
        diversity: float,
        kinship: float,
        trust: float,
        fitness: float,
    ) -> str:
        return (
            f"compatibility={composite:.3f}; diversity={diversity:.3f}; "
            f"kinship={kinship:.3f}; trust={trust:.3f}; fitness={fitness:.3f}; "
            f"subject={subject.name}; candidate={candidate.name}"
        )
