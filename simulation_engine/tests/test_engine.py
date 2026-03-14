from repro_engine import SimulationEngine


def build_engine() -> SimulationEngine:
    engine = SimulationEngine(signing_key="test-secret", seed=1)
    e1 = engine.make_entity(
        name="RootA",
        sex="female",
        age=30,
        family_id="A",
        lineage_id="L1",
        loci={"eye": ("B", "b"), "height": ("T", "t")},
        founder_tags=["alpha"],
    )
    e2 = engine.make_entity(
        name="RootB",
        sex="male",
        age=32,
        family_id="A",
        lineage_id="L1",
        loci={"eye": ("b", "b"), "height": ("T", "T")},
        founder_tags=["alpha", "beta"],
    )
    e3 = engine.make_entity(
        name="RootC",
        sex="female",
        age=25,
        family_id="B",
        lineage_id="L2",
        loci={"eye": ("B", "B"), "height": ("t", "t")},
        founder_tags=["gamma"],
    )
    engine.pair_entities(e1.identity.entity_id, e2.identity.entity_id, tick=1)
    engine.birth_entity(e1.identity.entity_id, e2.identity.entity_id, name="Child1", sex="male", tick=2)
    engine.run(until_tick=2)
    return engine


def test_birth_creates_child_and_links() -> None:
    engine = build_engine()
    child = [entity for entity in engine.lineage.entities.values() if entity.name == "Child1"][0]
    assert len(child.parent_ids) == 2
    assert child.identity.generation_index == 1
    assert child.identity.entity_id in engine.lineage.get_entity(child.parent_ids[0]).offspring_ids


def test_kinship_detects_close_relationships() -> None:
    engine = build_engine()
    child = [entity for entity in engine.lineage.entities.values() if entity.name == "Child1"][0]
    kinship = engine.lineage.kinship_coefficient(child.identity.entity_id, child.parent_ids[0])
    assert kinship >= 0.5


def test_identity_verification_round_trip() -> None:
    engine = build_engine()
    entity = next(iter(engine.lineage.entities.values()))
    valid, diagnostics = engine.identity.verify_entity(entity)
    assert valid is True
    assert all(diagnostics.values())


def test_trait_prediction_has_distribution() -> None:
    engine = build_engine()
    ids = list(engine.lineage.entities.keys())[:2]
    result = engine.ai.predict_offspring_traits(ids[0], ids[1], samples=64)
    assert "trait_distribution" in result
    assert "eye" in result["trait_distribution"]


def test_ai_report_is_structured() -> None:
    engine = build_engine()
    entity_id = list(engine.lineage.entities.keys())[0]
    report = engine.ai.explainability_report(entity_id)
    assert "lineage" in report
    assert "derived_signals" in report
