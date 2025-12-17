from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import hashlib
import json
import time
import os
import random

def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode('utf-8')
    return hashlib.sha256(data).hexdigest()

def generate_mock_world_id() -> str:
    return f"0x{sha256_hex(str(time.time_ns()))[:16]}"

@dataclass
class OAEParams:
    memory_decay: float = 0.10      
    entropy_guard: float = 0.85     
    learn_rate: float = 0.05        
    recovery_rate: float = 0.20     

@dataclass
class DigitalOrgan:
    organ_id: str
    schema: str                     
    volatile: bool = False          
    
    properties: Dict[str, float] = field(default_factory=lambda: {
        "strength": 10.0,
        "fatigue": 0.0,
        "integrity": 100.0
    })

@dataclass
class Soken:
    """Container ที่ผูกกับ Identity"""
    did: str                        
    ddna_sha256: str                
    digital_organs: Dict[str, DigitalOrgan] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

class OAE:
    """
    Organ Adjustment Engine: ควบคุมสมดุล, การเติบโต, และความเสื่อมถอย
    """
    def __init__(self, soken: Soken, params: OAEParams):
        self.soken = soken
        self.params = params
        self._ckpt_dir = "./oae_checkpoints"

    def resonance(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        [Active Phase]
        context: { "organ_id": "arm_right", "intensity": 0.8, "action": "lift" }
        """
        target_id = context.get("organ_id")
        intensity = float(context.get("intensity", 0.5))
        
        report = {"status": "ignored", "impact": 0.0}

        if target_id and target_id in self.soken.digital_organs:
            organ = self.soken.digital_organs[target_id]
            
            effective_impact = intensity * (1.0 - (self.params.entropy_guard * 0.3))
            
            if "motor" in organ.schema: 
                current_str = organ.properties.get("strength", 10.0)
                gain = effective_impact * self.params.learn_rate
                organ.properties["strength"] = min(100.0, current_str + gain)
                
                current_fatigue = organ.properties.get("fatigue", 0.0)
                fatigue_spike = intensity * 10.0  
                organ.properties["fatigue"] = min(100.0, current_fatigue + fatigue_spike)
                
                report = {
                    "organ": target_id,
                    "strength_gain": f"+{gain:.4f}",
                    "new_strength": organ.properties["strength"],
                    "fatigue_spike": f"+{fatigue_spike:.2f}"
                }

            elif "cognitive" in organ.schema: 
                pass

            self.soken.meta["last_active_organ"] = target_id
            self.soken.meta["last_active_ts"] = time.time()

        return report

    def decay_tick(self) -> Dict[str, Any]:
        """
        [Passive Phase] ทำงานตามเวลา (Recovery & Atrophy)
        """
        recovered = []
        atrophied = []

        for oid, organ in self.soken.digital_organs.items():
            props = organ.properties
            
            if props.get("fatigue", 0) > 0:
                loss = props["fatigue"] * self.params.recovery_rate
                props["fatigue"] = max(0.0, props["fatigue"] - loss)
                recovered.append(f"{oid} (fatigue -{loss:.2f})")

            if props.get("strength", 0) > 10.0 and props.get("fatigue", 0) < 1.0:
                decay_amt = props["strength"] * (self.params.memory_decay * 0.01)
                props["strength"] -= decay_amt
                atrophied.append(f"{oid} (str -{decay_amt:.4f})")

        return {"recovered": recovered, "atrophied": atrophied}

    def checkpoint(self, label: str) -> str:
        """Snapshot"""
        os.makedirs(self._ckpt_dir, exist_ok=True)
        
        snapshot = {
            "did": self.soken.did,
            "timestamp": time.time(),
            "label": label,
            "organs": {
                k: {
                    "id": v.organ_id,
                    "props": v.properties
                } for k, v in self.soken.digital_organs.items()
            }
        }
        
        data_bytes = json.dumps(snapshot, indent=2).encode('utf-8')
        file_hash = sha256_hex(data_bytes)[:12]
        filename = f"{self.soken.did.split(':')[-1]}_{label}_{file_hash}.json"
        path = os.path.join(self._ckpt_dir, filename)
        
        with open(path, "wb") as f:
            f.write(data_bytes)
            
        return path

def run_simulation():
    print("--- 🟢 INITIALIZING OAE SYSTEM ---")
    
    mock_nullifier = generate_mock_world_id()
    user_did = f"did:world:{mock_nullifier}"
    print(f"User Authenticated: {user_did}")

    limbs = {
        "arm_left": DigitalOrgan("arm_left", "motor_v1_precision"),
        "arm_right": DigitalOrgan("arm_right", "motor_v1_power", volatile=True),
        "legs": DigitalOrgan("legs", "motor_v1_endurance")
    }
    
    my_soken = Soken(
        did=user_did,
        ddna_sha256=sha256_hex("unique_biometric_seed"),
        digital_organs=limbs
    )

    engine = OAE(
        my_soken, 
        OAEParams(learn_rate=0.1, recovery_rate=0.3) 
    )

    print("\n--- 💪 ACTION: Lifting Heavy Object (Right Arm) ---")
    res1 = engine.resonance({
        "organ_id": "arm_right",
        "intensity": 0.9,  
        "action": "lift"
    })
    print(f"Effect: {res1}")

    print("\n--- 🏃 ACTION: Sprinting (Legs) ---")
    res2 = engine.resonance({
        "organ_id": "legs",
        "intensity": 0.6,
        "action": "run"
    })
    print(f"Effect: {res2}")

    ckpt1 = engine.checkpoint("post_workout")
    print(f"\n💾 State Saved: {ckpt1}")

    print("\n--- 💤 TIME PASSING (Resting & Recovery) ---")  
    for i in range(3):
        decay_res = engine.decay_tick()
        print(f"Tick {i+1}: {decay_res}")
        time.sleep(0.5)

    print("\n--- 📊 FINAL STATUS ---")
    r_arm = my_soken.digital_organs["arm_right"].properties
    print(f"Right Arm -> Strength: {r_arm['strength']:.2f}, Fatigue: {r_arm['fatigue']:.2f}")

if __name__ == "__main__":
    run_simulation()