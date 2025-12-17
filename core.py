from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import hashlib, json, time, os

def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

@dataclass
class OAEParams:
    memory_decay: float = 0.55      
    entropy_guard: float = 0.62     
    learn_rate: float = 0.08        

@dataclass
class DigitalOrgan:
    organ_id: str
    state_uri: Optional[str] = None   
    state_hash: Optional[str] = None  
    schema: str = "generic_v1"
    volatile: bool = False

@dataclass
class Soken:
    did: str
    ddna_sha256: str
    non_fungible: bool = True
    unique_identity: bool = True
    transferable: bool = True
    merge_policy: str = "oae-consensus"
    digital_organs: Dict[str, DigitalOrgan] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

class OAE:
    """
    OAE stabilizes identity state under entropy.
    It exposes: resonance(), decay_tick(), checkpoint(), verify_integrity().
    """

    def __init__(self, soken: Soken, params: OAEParams):
        self.soken = soken
        self.params = params
        self._checkpoint_dir = self.soken.meta.get("checkpoint_dir", "./oae_ckpt")

    def resonance(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply a high-energy event (empathic/intent exchange).
        Returns an effect dict describing adjustments.
        """
        inten = float(context.get("intensity", 0.5))       
        align = float(context.get("alignment", 0.5))       
        
        effective = inten * align * (1.0 - self.params.entropy_guard * 0.6)
       
        prev_lr = float(self.soken.meta.get("effective_learn_rate", self.params.learn_rate))
        new_lr = max(0.0, min(1.0, prev_lr + effective * 0.05))
        self.soken.meta["effective_learn_rate"] = new_lr

        target_organ = context.get("organ_id")
        if target_organ and target_organ in self.soken.digital_organs:
            self.soken.meta["hot_organ"] = target_organ
            self.soken.meta["hot_organ_at"] = time.time()

        return {
            "effective_impact": effective,
            "learn_rate_prev": prev_lr,
            "learn_rate_new": new_lr,
            "guard": self.params.entropy_guard,
            "target_organ": target_organ,
        }

    def decay_tick(self, now: Optional[float] = None) -> Dict[str, Any]:
        """
        Enact memory decay and stabilize volatile organs.
        Call this periodically (e.g., per session/hour/day).
        """
        now = now or time.time()
        decay = self.params.memory_decay      
        emo = float(self.soken.meta.get("affect_level", 0.0))
        new_emo = emo * (1.0 - 0.5 * decay)  
        self.soken.meta["affect_level"] = new_emo

        cooled = []
        for oid, organ in self.soken.digital_organs.items():
            if organ.volatile:
                cooled.append(oid)
        return {"affect_prev": emo, "affect_new": new_emo, "volatile_cooled": cooled}

    def checkpoint(self, label: str) -> str:
        """
        Create a tamper-evident snapshot (metadata-only; organ payload stays off-chain).
        Returns checkpoint file path.
        """
        os.makedirs(self._checkpoint_dir, exist_ok=True)
        payload = {
            "did": self.soken.did,
            "ddna_sha256": self.soken.ddna_sha256,
            "policy": {
                "non_fungible": self.soken.non_fungible,
                "unique_identity": self.soken.unique_identity,
                "transferable": self.soken.transferable,
                "merge_policy": self.soken.merge_policy,
            },
            "digital_organs": {k: {
                "organ_id": v.organ_id,
                "state_uri": v.state_uri,
                "state_hash": v.state_hash,
                "schema": v.schema,
                "volatile": v.volatile,
            } for k, v in self.soken.digital_organs.items()},
            "meta": self.soken.meta,
            "oae_params": self.params.__dict__,
            "ts": time.time(),
            "label": label,
        }
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        digest = sha256_hex(raw)
        path = os.path.join(self._checkpoint_dir, f"{label}_{digest[:16]}.json")
        with open(path, "wb") as f:
            f.write(raw)
        return path

    @staticmethod
    def verify_integrity(snapshot_bytes: bytes) -> str:
        """
        Verify hash of a given snapshot payload. Returns sha256 hex.
        """
        return sha256_hex(snapshot_bytes)

if __name__ == "__main__":
    s = Soken(
        did="did:mitas:example",
        ddna_sha256="abc123...",
        digital_organs={
            "memory": DigitalOrgan(organ_id="memory", schema="episodic_v1", volatile=False),
            "emotion": DigitalOrgan(organ_id="emotion", schema="affect_v1", volatile=True),
        },
        meta={"affect_level": 0.7, "checkpoint_dir": "./ckpt"},
    )

    limbs_organs = {  
        "arm_left": DigitalOrgan(
            organ_id="arm_left", 
            schema="motor_control_v1", 
            volatile=False  
        ),
        
        "arm_right": DigitalOrgan(
            organ_id="arm_right", 
            schema="motor_control_v1", 
            volatile=True   
        ),

        "legs": DigitalOrgan(
            organ_id="legs", 
            schema="locomotion_v1", 
            volatile=False
        )
    }

    s.digital_organs.update(limbs_organs)
    print(f"Total Organs after integration: {len(s.digital_organs)}")

    oae = OAE(s, OAEParams(memory_decay=0.55, entropy_guard=0.62, learn_rate=0.08))

    print("\n--- Triggering Resonance ---")
    resonance_result = oae.resonance({
        "intensity": 0.9, 
        "alignment": 1.0, 
        "organ_id": "legs" 
    })
    print("Resonance Result:", resonance_result)

    print("\n--- Routine Operations ---")
    print("Decay Tick:", oae.decay_tick())
    
    ckpt_path = oae.checkpoint("post_limbs_integration")
    print("Checkpoint Saved:", ckpt_path)