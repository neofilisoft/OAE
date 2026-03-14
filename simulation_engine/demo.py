from pprint import pprint

from repro_engine import SimulationEngine


def main() -> None:
    engine = SimulationEngine(signing_key="demo-secret", seed=7)

    a = engine.make_entity(
        name="Alya",
        sex="female",
        age=28,
        family_id="FALCON",
        lineage_id="L-01",
        loci={"eye": ("B", "b"), "height": ("T", "t"), "immune": ("R", "r")},
        founder_tags=["falcon", "north"],
    )
    b = engine.make_entity(
        name="Borin",
        sex="male",
        age=31,
        family_id="FALCON",
        lineage_id="L-01",
        loci={"eye": ("b", "b"), "height": ("T", "T"), "immune": ("R", "R")},
        founder_tags=["falcon", "east"],
    )
    c = engine.make_entity(
        name="Cyra",
        sex="female",
        age=27,
        family_id="WOLF",
        lineage_id="L-02",
        loci={"eye": ("B", "B"), "height": ("t", "t"), "immune": ("R", "r")},
        founder_tags=["wolf"],
    )

    engine.pair_entities(a.identity.entity_id, b.identity.entity_id, tick=1)
    engine.birth_entity(a.identity.entity_id, b.identity.entity_id, name="Darian", sex="male", tick=2)
    engine.birth_entity(a.identity.entity_id, b.identity.entity_id, name="Elia", sex="female", tick=3)
    engine.mutate_trait(a.identity.entity_id, locus="immune", new_pair=("R", "R"), reason="therapy", tick=4)
    engine.verify_identity(a.identity.entity_id, tick=5)
    engine.ai_intervention(a.identity.entity_id, tick=6)
    engine.lineage_split(c.identity.entity_id, new_family_id="WOLF-SOUTH", tick=7)
    engine.death_event(b.identity.entity_id, tick=8)
    engine.run(until_tick=10)

    print("=== EVENT LOG ===")
    pprint(engine.event_log)

    print("\n=== LINEAGE SUMMARY: Alya ===")
    pprint(engine.lineage.lineage_summary(a.identity.entity_id))

    print("\n=== AI RECOMMENDATIONS: Alya ===")
    pprint(engine.ai.mate_recommendation(a.identity.entity_id))

    print("\n=== TRAIT PREDICTION Alya x Cyra ===")
    pprint(engine.ai.predict_offspring_traits(a.identity.entity_id, c.identity.entity_id, samples=128))

    print("\n=== ANOMALIES ===")
    pprint(engine.ai.anomaly_detection())

    print("\n=== CLUSTERS ===")
    pprint(engine.ai.lineage_clustering(n_clusters=2))

    print("\n=== FRAUD DETECTION ===")
    pprint(engine.ai.identity_fraud_detection())


if __name__ == "__main__":
    main()
