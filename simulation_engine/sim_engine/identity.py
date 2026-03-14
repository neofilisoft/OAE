from __future__ import annotations

import hashlib
import hmac
import json
from datetime import timezone, datetime
from typing import Any

from .models import CryptoIdentity, Entity, LogicalIdentity


class IdentityService:
    def __init__(self, signing_key: str) -> None:
        self.signing_key = signing_key.encode("utf-8")

    @staticmethod
    def _stable_json(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

    def logical_snapshot(self, entity: Entity) -> dict[str, Any]:
        logical: LogicalIdentity = entity.identity
        return {
            "entity_id": logical.entity_id,
            "lineage_id": logical.lineage_id,
            "family_id": logical.family_id,
            "generation_index": logical.generation_index,
            "public_metadata": logical.public_metadata,
            "private_metadata": logical.private_metadata,
            "trust_score": logical.trust_score,
            "provenance_record": logical.provenance_record,
            "parents": sorted(entity.parent_ids),
            "offspring": sorted(entity.offspring_ids),
            "genome_loci": {k: v.canonical_tuple() for k, v in sorted(entity.genome.loci.items())},
            "markers": sorted(entity.genome.markers),
            "founder_tags": sorted(entity.genome.founder_tags),
            "traits": entity.traits,
            "alive": entity.alive,
            "updated_at": entity.updated_at.isoformat(),
        }

    def content_hash(self, entity: Entity) -> str:
        snapshot = self._stable_json(self.logical_snapshot(entity))
        return hashlib.sha256(snapshot.encode("utf-8")).hexdigest()

    def mutation_history_checksum(self, entity: Entity) -> str:
        payload = [
            {
                "locus": record.locus,
                "previous": record.previous.canonical_tuple(),
                "current": record.current.canonical_tuple(),
                "reason": record.reason,
                "timestamp": record.timestamp.isoformat(),
            }
            for record in entity.genome.mutation_history
        ]
        return hashlib.blake2b(self._stable_json({"history": payload}).encode("utf-8"), digest_size=32).hexdigest()

    def sign_snapshot(self, entity: Entity) -> str:
        message = self.content_hash(entity).encode("utf-8")
        return hmac.new(self.signing_key, message, hashlib.sha256).hexdigest()

    def sign_event(self, entity_id: str, event_name: str, payload: dict[str, Any]) -> str:
        message = self._stable_json(
            {
                "entity_id": entity_id,
                "event_name": event_name,
                "payload": payload,
            }
        ).encode("utf-8")
        return hmac.new(self.signing_key, message, hashlib.sha256).hexdigest()

    def build_crypto_identity(self, entity: Entity) -> CryptoIdentity:
        return CryptoIdentity(
            content_hash=self.content_hash(entity),
            signed_snapshot=self.sign_snapshot(entity),
            mutation_history_checksum=self.mutation_history_checksum(entity),
            event_signature=self.sign_event(entity.identity.entity_id, "snapshot", self.logical_snapshot(entity)),
            last_verified_at=datetime.now(timezone.utc),
        )

    def seal_entity(self, entity: Entity) -> Entity:
        entity.touch()
        pending_hash = self.content_hash(entity)
        entity.identity.provenance_record.append(f"sealed:{pending_hash}")
        entity.touch()
        entity.crypto = self.build_crypto_identity(entity)
        return entity

    def verify_entity(self, entity: Entity) -> tuple[bool, dict[str, object]]:
        expected_content_hash = self.content_hash(entity)
        expected_snapshot_sig = self.sign_snapshot(entity)
        expected_checksum = self.mutation_history_checksum(entity)
        expected_event_sig = self.sign_event(entity.identity.entity_id, "snapshot", self.logical_snapshot(entity))
        ok = (
            entity.crypto.content_hash == expected_content_hash
            and entity.crypto.signed_snapshot == expected_snapshot_sig
            and entity.crypto.mutation_history_checksum == expected_checksum
            and entity.crypto.event_signature == expected_event_sig
        )
        diagnostics = {
            "content_hash_match": entity.crypto.content_hash == expected_content_hash,
            "signed_snapshot_match": entity.crypto.signed_snapshot == expected_snapshot_sig,
            "mutation_history_match": entity.crypto.mutation_history_checksum == expected_checksum,
            "event_signature_match": entity.crypto.event_signature == expected_event_sig,
        }
        if ok:
            entity.crypto.last_verified_at = datetime.now(timezone.utc)
        return ok, diagnostics
