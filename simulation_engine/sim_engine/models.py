from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LifecycleState(str, Enum):
    EMBRYO = "embryo"
    INFANT = "infant"
    JUVENILE = "juvenile"
    ADULT = "adult"
    ELDER = "elder"
    DECEASED = "deceased"


class AllelePair(BaseModel):
    model_config = ConfigDict(frozen=True)

    first: str = Field(min_length=1)
    second: str = Field(min_length=1)

    def canonical_tuple(self) -> tuple[str, str]:
        return tuple(sorted((self.first, self.second)))

    def dominant_allele(self) -> str:
        for allele in (self.first, self.second):
            if allele.isupper():
                return allele
        return sorted((self.first, self.second))[0]

    def diversity_score(self) -> float:
        return 1.0 if self.first != self.second else 0.0


class MutationRecord(BaseModel):
    locus: str
    previous: AllelePair
    current: AllelePair
    reason: str = "random"
    timestamp: datetime = Field(default_factory=utcnow)


class TraitRule(BaseModel):
    name: str
    locus: str
    dominant_map: dict[str, str] = Field(default_factory=dict)
    recessive_map: dict[str, str] = Field(default_factory=dict)
    codominant_pairs: dict[str, str] = Field(default_factory=dict)
    numeric_impact: dict[str, float] = Field(default_factory=dict)

    def express(self, pair: AllelePair) -> str:
        a, b = pair.canonical_tuple()
        key = f"{a}/{b}"
        if key in self.codominant_pairs:
            return self.codominant_pairs[key]
        dominant = pair.dominant_allele()
        if dominant in self.dominant_map:
            return self.dominant_map[dominant]
        if a == b and a in self.recessive_map:
            return self.recessive_map[a]
        return self.dominant_map.get(a) or self.dominant_map.get(b) or self.recessive_map.get(a) or key


class GenomeProfile(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    loci: dict[str, AllelePair] = Field(default_factory=dict)
    markers: list[str] = Field(default_factory=list)
    founder_tags: list[str] = Field(default_factory=list)
    mutation_history: list[MutationRecord] = Field(default_factory=list)
    derived_traits: dict[str, str] = Field(default_factory=dict)
    fitness_score: float = 0.5

    @field_validator("fitness_score")
    @classmethod
    def validate_fitness(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("fitness_score must be between 0.0 and 1.0")
        return value

    def heterozygosity(self) -> float:
        if not self.loci:
            return 0.0
        total = sum(pair.diversity_score() for pair in self.loci.values())
        return total / len(self.loci)


class LogicalIdentity(BaseModel):
    entity_id: str
    lineage_id: str
    family_id: str
    generation_index: int = 0
    public_metadata: dict[str, Any] = Field(default_factory=dict)
    private_metadata: dict[str, Any] = Field(default_factory=dict)
    trust_score: float = 0.5
    provenance_record: list[str] = Field(default_factory=list)

    @field_validator("generation_index")
    @classmethod
    def non_negative_generation(cls, value: int) -> int:
        if value < 0:
            raise ValueError("generation_index must be non-negative")
        return value

    @field_validator("trust_score")
    @classmethod
    def valid_trust_score(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("trust_score must be between 0.0 and 1.0")
        return value


class CryptoIdentity(BaseModel):
    content_hash: str = ""
    signed_snapshot: str = ""
    mutation_history_checksum: str = ""
    event_signature: str = ""
    last_verified_at: datetime | None = None


class LegalOverlay(BaseModel):
    inheritance_group: str = "default"
    rights_multiplier: float = 1.0
    is_recognized_offspring: bool = True
    notes: list[str] = Field(default_factory=list)
    branch_label: str | None = None


class Entity(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    name: str
    sex: Literal["female", "male", "other"] = "other"
    age: int = 0
    lifecycle_state: LifecycleState = LifecycleState.INFANT
    genome: GenomeProfile = Field(default_factory=GenomeProfile)
    identity: LogicalIdentity
    crypto: CryptoIdentity = Field(default_factory=CryptoIdentity)
    legal: LegalOverlay = Field(default_factory=LegalOverlay)
    parent_ids: list[str] = Field(default_factory=list)
    offspring_ids: list[str] = Field(default_factory=list)
    partner_ids: list[str] = Field(default_factory=list)
    social_links: dict[str, list[str]] = Field(default_factory=dict)
    traits: dict[str, Any] = Field(default_factory=dict)
    alive: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @field_validator("age")
    @classmethod
    def non_negative_age(cls, value: int) -> int:
        if value < 0:
            raise ValueError("age must be non-negative")
        return value

    @model_validator(mode="after")
    def enforce_alive_state(self) -> "Entity":
        if self.lifecycle_state == LifecycleState.DECEASED and self.alive:
            raise ValueError("deceased entities must have alive=False")
        if self.lifecycle_state != LifecycleState.DECEASED and not self.alive:
            raise ValueError("non-deceased entities must have alive=True")
        return self

    def touch(self) -> None:
        self.updated_at = utcnow()

    def add_offspring(self, child_id: str) -> None:
        if child_id not in self.offspring_ids:
            self.offspring_ids.append(child_id)
            self.touch()

    def add_parent(self, parent_id: str) -> None:
        if parent_id not in self.parent_ids:
            self.parent_ids.append(parent_id)
            self.touch()

    def add_partner(self, partner_id: str) -> None:
        if partner_id not in self.partner_ids:
            self.partner_ids.append(partner_id)
            self.touch()
