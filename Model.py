from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import hashlib, json, time, os
from enum import Enum
from datetime import datetime

# ---------- Enums สำหรับกำหนดค่าตายตัว ----------
class IntelligenceLevel(Enum):
    GI_1 = "GI-1"  # Basic Response
    GI_2 = "GI-2"  # Pattern Recognition
    GI_3 = "GI-3"  # Adaptive Learning
    GI_4 = "GI-4"  # Strategic Reasoning
    GI_5 = "GI-5"  # Abstract Consciousness
    GI_X = "GI-X"  # Transcendent

class EntityStatus(Enum):
    OPERATIONAL = "OPERATIONAL"
    STANDBY = "STANDBY"
    MAINTENANCE = "MAINTENANCE"
    DAMAGED = "DAMAGED"
    TERMINATED = "TERMINATED"

class PsycheTrait(Enum):
    STOIC_ANALYTIC = "Stoic-Analytic"
    EMPATHIC_CREATIVE = "Empathic-Creative"
    LOGICAL_PRECISE = "Logical-Precise"
    CHAOTIC_ADAPTIVE = "Chaotic-Adaptive"
    GUARDIAN_PROTECTIVE = "Guardian-Protective"

# ---------- Core Entity Model ----------
@dataclass
class SyntheticEntity:
    """โมเดลหลักสำหรับสิ่งมีชีวิตสังเคราะห์"""
    
    # ----- Identity -----
    entity_name: str
    id: str = field(default_factory=lambda: f"0x{hashlib.sha256(str(time.time_ns()).encode()).hexdigest()[:16]}")
    
    # ----- Metadata -----
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # ----- Physical Statistics -----
    physical_stats: Dict[str, float] = field(default_factory=dict)
    
    # ----- Psyche Profile -----
    psyche: Dict[str, str] = field(default_factory=dict)
    
    # ----- Status -----
    status: EntityStatus = EntityStatus.OPERATIONAL
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    mission_log: List[MissionRecord] = field(default_factory=list)
    
    def __post_init__(self):
        """คำนวณ checksum และ validate ข้อมูล"""
        if 'checksum' not in self.metadata:
            self.metadata['checksum'] = self._calculate_checksum()
    
    def _calculate_checksum(self) -> str:
        """สร้าง checksum สำหรับตรวจสอบ integrity"""
        data = f"{self.id}{self.entity_name}{json.dumps(self.physical_stats, sort_keys=True)}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def verify_integrity(self) -> bool:
        """ตรวจสอบว่า data ถูกแก้ไขหรือไม่"""
        stored_checksum = self.metadata.get('checksum', '')
        current_checksum = self._calculate_checksum()
        return stored_checksum == current_checksum
    
    def update_physical_stats(self, part: str, value: float):
        """อัปเดตสภาพร่างกาย"""
        self.physical_stats[part] = value
        self.last_active = time.time()
        self.metadata['checksum'] = self._calculate_checksum()
    
    def add_mission_log(self, mission: MissionRecord):
        """บันทึกประวัติการปฏิบัติภารกิจ"""
        self.mission_log.append(mission)
        self.last_active = time.time()

@dataclass
class MissionRecord:
    """บันทึกภารกิจของ entity"""
    mission_id: str = field(default_factory=lambda: hashlib.md5(str(time.time_ns()).encode()).hexdigest()[:8])
    timestamp: float = field(default_factory=time.time)
    mission_type: str
    success: bool
    notes: Optional[str] = None
    damage_taken: Dict[str, float] = field(default_factory=dict)

# ---------- Repository สำหรับ Synthetic Entities ----------
class SyntheticRepository:
    """จัดการ JSON storage สำหรับ synthetic beings"""
    
    def __init__(self, base_path: str = "./synthetic_db"):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)
    
    def save_entity(self, entity: SyntheticEntity):
        """บันทึก entity ลง JSON"""
        file_path = os.path.join(self.base_path, f"{entity.id}.json")
        
        data = {
            'entity_name': entity.entity_name,
            'id': entity.id,
            'metadata': entity.metadata,
            'physical_stats': entity.physical_stats,
            'psyche': entity.psyche,
            'status': entity.status.value,
            'created_at': entity.created_at,
            'last_active': entity.last_active,
            'mission_log': [
                {
                    'mission_id': m.mission_id,
                    'timestamp': m.timestamp,
                    'mission_type': m.mission_type,
                    'success': m.success,
                    'notes': m.notes,
                    'damage_taken': m.damage_taken
                }
                for m in entity.mission_log
            ]
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return file_path
    
    def load_entity(self, entity_id: str) -> Optional[SyntheticEntity]:
        """โหลด entity จาก JSON"""
        file_path = os.path.join(self.base_path, f"{entity_id}.json")
        
        if not os.path.exists(file_path):
            return None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # แปลง JSON -> Object
        entity = SyntheticEntity(
            entity_name=data['entity_name'],
            id=data['id'],
            metadata=data['metadata'],
            physical_stats=data['physical_stats'],
            psyche=data['psyche'],
            status=EntityStatus(data['status']),
            created_at=data['created_at'],
            last_active=data['last_active']
        )
        
        # โหลด mission log
        for m_data in data.get('mission_log', []):
            mission = MissionRecord(
                mission_id=m_data['mission_id'],
                timestamp=m_data['timestamp'],
                mission_type=m_data['mission_type'],
                success=m_data['success'],
                notes=m_data.get('notes'),
                damage_taken=m_data.get('damage_taken', {})
            )
            entity.mission_log.append(mission)
        
        return entity
    
    def list_all_entities(self) -> List[str]:
        """แสดง entity ทั้งหมดในระบบ"""
        files = os.listdir(self.base_path)
        return [f.replace('.json', '') for f in files if f.endswith('.json')]

# ---------- Command & Control System ----------
class C2System:
    """ระบบควบคุมสิ่งมีชีวิตสังเคราะห์"""
    
    def __init__(self):
        self.repository = SyntheticRepository()
        self.active_entities: Dict[str, SyntheticEntity] = {}
    
    def deploy_entity(self, entity: SyntheticEntity):
        """ปล่อย entity ปฏิบัติภารกิจ"""
        self.active_entities[entity.id] = entity
        entity.status = EntityStatus.OPERATIONAL
        self.repository.save_entity(entity)
        print(f"🔄 [{entity.entity_name}]  deployed | ID: {entity.id[:8]}...")
    
    def recall_entity(self, entity_id: str):
        """เรียก entity กลับฐาน"""
        if entity_id in self.active_entities:
            entity = self.active_entities[entity_id]
            entity.status = EntityStatus.STANDBY
            self.repository.save_entity(entity)
            del self.active_entities[entity_id]
            print(f"🔄 [{entity.entity_name}] recalled")
    
    def assess_readiness(self, entity: SyntheticEntity) -> bool:
        """ประเมินความพร้อมก่อนปฏิบัติภารกิจ"""
        # ตรวจสอบ integrity
        if not entity.verify_integrity():
            print(f"⚠️ [{entity.entity_name}] integrity check FAILED")
            return False
        
        # ตรวจสอบ physical condition
        fatigue = entity.physical_stats.get('fatigue_all', 0)
        if fatigue > 80:
            print(f"⚠️ [{entity.entity_name}] fatigue too high: {fatigue}%")
            return False
        
        # ตรวจสอบ core status
        core = entity.physical_stats.get('core', 0)
        if core < 1.0:
            print(f"⚠️ [{entity.entity_name}] core critical: {core}")
            return False
        
        return True

# ---------- สร้าง Aetheris ----------
def create_aetheris():
    """สร้าง Aetheris - Stoic-Analytic Synthetic Being"""
    
    aetheris = SyntheticEntity(
        entity_name="Aetheris",
        metadata={
            "ddna": "7b9e-synthetic-x912",
            "gender": "Male",
            "intelligence_level": IntelligenceLevel.GI_4.value,
            "generation": 7,
            "manufacturer": "Aether Labs"
        },
        physical_stats={
            "right_arm": 3.45,
            "left_arm": 1.12,  # อ่อนแอกว่า ออกแบบมาเพื่อความสมดุล?
            "legs": 5.88,
            "core": 2.55,
            "fatigue_all": 0.00,
            "neural_link": 4.21,
            "sensor_array": 3.89
        },
        psyche={
            "trait": PsycheTrait.STOIC_ANALYTIC.value,
            "preference": "Sapiosexual",
            "drive": "Evolutionary Optimization",
            "loyalty": "Aether Labs",
            "philosophy": "Logic over Emotion, Efficiency over Art"
        }
    )
    
    return aetheris

# ---------- ตัวอย่างการใช้งาน ----------
if __name__ == "__main__":
    # สร้าง C2 System
    c2 = C2System()
    
    # สร้าง Aetheris
    aetheris = create_aetheris()
    
    # ตรวจสอบความพร้อม
    if c2.assess_readiness(aetheris):
        # Deploy
        c2.deploy_entity(aetheris)
        
        # เพิ่มภารกิจ
        mission = MissionRecord(
            mission_type="Reconnaissance",
            success=True,
            notes="Collected 2.4TB of strategic data",
            damage_taken={"left_arm": 0.05, "sensor_array": 0.12}
        )
        aetheris.add_mission_log(mission)
        
        # อัปเดตสภาพ
        aetheris.update_physical_stats("fatigue_all", 23.5)
        aetheris.update_physical_stats("left_arm", 1.07)  # เสียหายเล็กน้อย
        
        # Save
        c2.repository.save_entity(aetheris)
        
        print("\nAetheris Status Report:")
        print(f"   Integrity: {'OK' if aetheris.verify_integrity() else 'Corrupted'}")
        print(f"   Missions: {len(aetheris.mission_log)}")
        print(f"   Fatigue: {aetheris.physical_stats['fatigue_all']}%")
        print(f"   Status: {aetheris.status.value}")
        
        # เรียกกลับ
        c2.recall_entity(aetheris.id)
    
    # แสดง entity ทั้งหมดในระบบ
    print(f"\nActive Entities in Database: {c2.repository.list_all_entities()}")
