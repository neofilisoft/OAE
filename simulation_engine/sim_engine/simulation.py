from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from .ai import AIAdvisor
from .identity import IdentityService
from .lineage import LineageEngine
from .models import (
    AllelePair,
    Entity,
    GenomeProfile,
    LifecycleState,
    LogicalIdentity,
    MutationRecord,
)


@dataclass(order=True)
class ScheduledEvent:
    tick: int
    priority: int
    event_type: str = field(compare=False)
    payload: dict[str, Any] = field(compare=False, default_factory=dict)


class SimulationEngine:
    def __init__(self, signing_key: str = "change-me", seed: int = 42) -> None:
        self.lineage = LineageEngine()
        self.identity = IdentityService(signing_key=signing_key)
        self.ai = AIAdvisor(self.lineage)
        self.current_tick = 0
        self._queue: list[ScheduledEvent] = []
        self._id_counter = itertools.count(1)
        self.rng = np.random.default_rng(seed)
        self.event_log: list[dict[str, Any]] = []
        self.event_handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
            "birth": self._handle_birth,
            "pairing": self._handle_pairing,
            "trait_mutation": self._handle_trait_mutation,
            "death": self._handle_death,
            "lineage_split": self._handle_lineage_split,
            "identity_verification": self._handle_identity_verification,
            "ai_intervention": self._handle_ai_intervention,
        }

    def schedule(self, event_type: str, tick: int, payload: dict[str, Any], priority: int = 100) -> None:
        if event_type not in self.event_handlers:
            raise KeyError(f"unsupported event_type: {event_type}")
        heapq.heappush(self._queue, ScheduledEvent(tick=tick, priority=priority, event_type=event_type, payload=payload))

    def register_entity(self, entity: Entity) -> Entity:
        self.identity.seal_entity(entity)
        self.lineage.add_entity(entity)
        self.event_log.append({"tick": self.current_tick, "event": "register", "entity_id": entity.identity.entity_id})
        return entity

    def make_entity(
        self,
        name: str,
        sex: str,
        age: int,
        family_id: str,
        lineage_id: str,
        generation_index: int = 0,
        loci: dict[str, tuple[str, str]] | None = None,
        founder_tags: list[str] | None = None,
        public_metadata: dict[str, Any] | None = None,
        private_metadata: dict[str, Any] | None = None,
        lifecycle_state: LifecycleState | None = None,
    ) -> Entity:
        entity_id = f"E{next(self._id_counter):05d}"
        state = lifecycle_state or self._infer_lifecycle(age)
        genome = GenomeProfile(
            loci={key: AllelePair(first=value[0], second=value[1]) for key, value in (loci or {}).items()},
            founder_tags=founder_tags or [],
            fitness_score=float(self.rng.uniform(0.45, 0.95)),
        )
        entity = Entity(
            name=name,
            sex=sex,
            age=age,
            lifecycle_state=state,
            genome=genome,
            identity=LogicalIdentity(
                entity_id=entity_id,
                lineage_id=lineage_id,
                family_id=family_id,
                generation_index=generation_index,
                public_metadata=public_metadata or {},
                private_metadata=private_metadata or {},
                trust_score=float(self.rng.uniform(0.55, 0.95)),
                provenance_record=[f"created@tick:{self.current_tick}"],
            ),
        )
        return self.register_entity(entity)

    def run(self, until_tick: int | None = None, max_events: int | None = None) -> list[dict[str, Any]]:
        processed = 0
        while self._queue:
            scheduled = heapq.heappop(self._queue)
            if until_tick is not None and scheduled.tick > until_tick:
                heapq.heappush(self._queue, scheduled)
                break
            self.current_tick = scheduled.tick
            handler = self.event_handlers[scheduled.event_type]
            result = handler(scheduled.payload)
            self.event_log.append(
                {
                    "tick": self.current_tick,
                    "event": scheduled.event_type,
                    "payload": scheduled.payload,
                    "result": result,
                }
            )
            processed += 1
            if max_events is not None and processed >= max_events:
                break
        return self.event_log

    def pair_entities(self, first_id: str, second_id: str, tick: int | None = None) -> None:
        self.schedule("pairing", tick or self.current_tick, {"first_id": first_id, "second_id": second_id}, priority=10)

    def birth_entity(self, parent_a_id: str, parent_b_id: str, name: str, sex: str, tick: int | None = None) -> None:
        self.schedule(
            "birth",
            tick or self.current_tick,
            {"parent_a_id": parent_a_id, "parent_b_id": parent_b_id, "name": name, "sex": sex},
            priority=20,
        )

    def mutate_trait(self, entity_id: str, locus: str, new_pair: tuple[str, str], reason: str = "random", tick: int | None = None) -> None:
        self.schedule(
            "trait_mutation",
            tick or self.current_tick,
            {"entity_id": entity_id, "locus": locus, "new_pair": new_pair, "reason": reason},
            priority=30,
        )

    def death_event(self, entity_id: str, tick: int | None = None) -> None:
        self.schedule("death", tick or self.current_tick, {"entity_id": entity_id}, priority=40)

    def lineage_split(self, entity_id: str, new_family_id: str, tick: int | None = None) -> None:
        self.schedule(
            "lineage_split",
            tick or self.current_tick,
            {"entity_id": entity_id, "new_family_id": new_family_id},
            priority=50,
        )

    def verify_identity(self, entity_id: str, tick: int | None = None) -> None:
        self.schedule("identity_verification", tick or self.current_tick, {"entity_id": entity_id}, priority=60)

    def ai_intervention(self, entity_id: str, tick: int | None = None) -> None:
        self.schedule("ai_intervention", tick or self.current_tick, {"entity_id": entity_id}, priority=70)

    def _handle_pairing(self, payload: dict[str, Any]) -> dict[str, Any]:
        first = self.lineage.get_entity(payload["first_id"])
        second = self.lineage.get_entity(payload["second_id"])
        allowed, kinship = self.lineage.prevent_inbreeding(first.identity.entity_id, second.identity.entity_id)
        if not allowed:
            return {"paired": False, "reason": f"inbreeding threshold exceeded ({kinship})"}
        first.add_partner(second.identity.entity_id)
        second.add_partner(first.identity.entity_id)
        self.identity.seal_entity(first)
        self.identity.seal_entity(second)
        return {"paired": True, "kinship": kinship}

    def _handle_birth(self, payload: dict[str, Any]) -> dict[str, Any]:
        parent_a = self.lineage.get_entity(payload["parent_a_id"])
        parent_b = self.lineage.get_entity(payload["parent_b_id"])
        allowed, kinship = self.lineage.prevent_inbreeding(parent_a.identity.entity_id, parent_b.identity.entity_id)
        if not allowed:
            return {"born": False, "reason": f"blocked by inbreeding rule ({kinship})"}

        child_id = f"E{next(self._id_counter):05d}"
        child_loci: dict[str, AllelePair] = {}
        all_loci = set(parent_a.genome.loci).union(parent_b.genome.loci)
        for locus in all_loci:
            pair_a = parent_a.genome.loci.get(locus, AllelePair(first="x", second="x"))
            pair_b = parent_b.genome.loci.get(locus, AllelePair(first="x", second="x"))
            child_loci[locus] = AllelePair(
                first=self.rng.choice([pair_a.first, pair_a.second]).item(),
                second=self.rng.choice([pair_b.first, pair_b.second]).item(),
            )

        generation = max(parent_a.identity.generation_index, parent_b.identity.generation_index) + 1
        founder_tags = sorted(set(parent_a.genome.founder_tags).intersection(parent_b.genome.founder_tags)) or sorted(
            set(parent_a.genome.founder_tags).union(parent_b.genome.founder_tags)
        )
        child = Entity(
            name=payload["name"],
            sex=payload["sex"],
            age=0,
            lifecycle_state=LifecycleState.INFANT,
            genome=GenomeProfile(
                loci=child_loci,
                founder_tags=founder_tags,
                fitness_score=float(np.clip((parent_a.genome.fitness_score + parent_b.genome.fitness_score) / 2.0, 0.0, 1.0)),
            ),
            identity=LogicalIdentity(
                entity_id=child_id,
                lineage_id=parent_a.identity.lineage_id,
                family_id=parent_a.identity.family_id,
                generation_index=generation,
                public_metadata={"born_at_tick": self.current_tick},
                private_metadata={},
                trust_score=float(np.clip((parent_a.identity.trust_score + parent_b.identity.trust_score) / 2.0, 0.0, 1.0)),
                provenance_record=[
                    f"born@tick:{self.current_tick}",
                    f"parent:{parent_a.identity.entity_id}",
                    f"parent:{parent_b.identity.entity_id}",
                ],
            ),
            parent_ids=[parent_a.identity.entity_id, parent_b.identity.entity_id],
        )
        self.identity.seal_entity(child)
        self.lineage.add_entity(child)
        self.lineage.add_parent_child_relation(parent_a.identity.entity_id, child.identity.entity_id)
        self.lineage.add_parent_child_relation(parent_b.identity.entity_id, child.identity.entity_id)
        self.identity.seal_entity(parent_a)
        self.identity.seal_entity(parent_b)
        return {"born": True, "child_id": child.identity.entity_id, "kinship": kinship}

    def _handle_trait_mutation(self, payload: dict[str, Any]) -> dict[str, Any]:
        entity = self.lineage.get_entity(payload["entity_id"])
        locus = payload["locus"]
        new_pair = AllelePair(first=payload["new_pair"][0], second=payload["new_pair"][1])
        old_pair = entity.genome.loci.get(locus, AllelePair(first="x", second="x"))
        entity.genome.loci[locus] = new_pair
        entity.genome.mutation_history.append(
            MutationRecord(locus=locus, previous=old_pair, current=new_pair, reason=payload.get("reason", "random"))
        )
        entity.identity.trust_score = float(max(0.0, entity.identity.trust_score - 0.01))
        self.identity.seal_entity(entity)
        return {"mutated": True, "entity_id": entity.identity.entity_id, "locus": locus}

    def _handle_death(self, payload: dict[str, Any]) -> dict[str, Any]:
        entity = self.lineage.get_entity(payload["entity_id"])
        object.__setattr__(entity, "alive", False)
        object.__setattr__(entity, "lifecycle_state", LifecycleState.DECEASED)
        self.identity.seal_entity(entity)
        return {"deceased": True, "entity_id": entity.identity.entity_id}

    def _handle_lineage_split(self, payload: dict[str, Any]) -> dict[str, Any]:
        entity = self.lineage.get_entity(payload["entity_id"])
        previous_family = entity.identity.family_id
        entity.identity.family_id = payload["new_family_id"]
        entity.legal.branch_label = f"{payload['new_family_id']}:split"
        entity.identity.provenance_record.append(f"family_split:{previous_family}->{payload['new_family_id']}")
        self.identity.seal_entity(entity)
        return {"split": True, "from": previous_family, "to": payload["new_family_id"]}

    def _handle_identity_verification(self, payload: dict[str, Any]) -> dict[str, Any]:
        entity = self.lineage.get_entity(payload["entity_id"])
        valid, diagnostics = self.identity.verify_entity(entity)
        return {"verified": valid, "diagnostics": diagnostics}

    def _handle_ai_intervention(self, payload: dict[str, Any]) -> dict[str, Any]:
        entity_id = payload["entity_id"]
        recommendations = self.ai.mate_recommendation(entity_id, max_results=3)
        anomalies = [item for item in self.ai.anomaly_detection() if item["entity_id"] == entity_id]
        report = self.ai.explainability_report(entity_id)
        return {
            "recommendations": recommendations,
            "anomalies": anomalies,
            "report": report,
        }

    @staticmethod
    def _infer_lifecycle(age: int) -> LifecycleState:
        if age <= 0:
            return LifecycleState.INFANT
        if age < 12:
            return LifecycleState.JUVENILE
        if age < 50:
            return LifecycleState.ADULT
        return LifecycleState.ELDER
