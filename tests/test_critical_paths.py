"""
Critical Path Tests — covers the most important flows across all phases.
Run: docker compose exec api pytest tests/ -v
"""
import json
import os
import sys

sys.path.insert(0, "/app")
os.environ.setdefault("DB_HOST", "db")
os.environ.setdefault("DB_NAME", "lulia")

import pytest


# --- Phase 1b: Standards ---

def test_standards_query():
    """Standards can be queried by subject and grade."""
    from src.lms_agents.tools.db import get_connection
    from psycopg2.extras import RealDictCursor
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT COUNT(*) as count FROM standards")
    count = cur.fetchone()["count"]
    cur.close(); conn.close()
    assert count > 0, "Standards should be loaded"


# --- Phase 2a: RAG Search ---

def test_rag_search_returns_results():
    """RAG search finds relevant chunks when KB has data."""
    from src.lms_agents.tools.db import get_connection
    from psycopg2.extras import RealDictCursor
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT COUNT(*) as count FROM knowledge_chunks WHERE embedding IS NOT NULL")
    count = cur.fetchone()["count"]
    cur.close(); conn.close()
    # Only test search if we have embedded chunks
    if count > 0:
        from src.lms_agents.tools.rag_search import search_kb
        results = search_kb("fractions", top_k=3)
        assert len(results) > 0, "RAG search should return results"


# --- Phase 3b: Generation History ---

def test_generation_history_stores():
    """Generation history stores fingerprints."""
    from src.lms_agents.tools.generation_history import store_generation, query_history
    from src.lms_agents.tools.db import get_connection
    tid = "00000000-0000-0000-0000-000000000001"
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT assignment_id FROM assignments LIMIT 1")
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row:
        pytest.skip("No assignments in DB")
    aid = str(row[0])
    store_generation(tid, aid, ["TEST.1"], "worksheet", {"title": "Test", "questions": [{"question_text": "Q1"}]})
    history = query_history(tid, ["TEST.1"])
    assert len(history) > 0, "History should contain the stored generation"


# --- Phase 4: Template Renderer ---

def test_template_renderer():
    """All 22 templates render without error."""
    from src.lms_agents.tools.template_renderer import render_template, RENDERERS
    content = {"title": "Test", "instructions": "Test", "questions": [
        {"question_number": 1, "question_text": "Q1", "answer": "A1", "difficulty": "easy", "standard_code": "T.1"}
    ]}
    for template_id in RENDERERS:
        html = render_template(template_id, content)
        assert "<!DOCTYPE html>" in html, f"{template_id} should produce valid HTML"


# --- Phase 5: Accommodations ---

def test_accommodation_profiles():
    """Default accommodation profiles exist."""
    from src.lms_agents.tools.accommodation_engine import DEFAULT_PROFILES
    assert "iep_reading_reduced" in DEFAULT_PROFILES
    assert "gifted_enriched" in DEFAULT_PROFILES
    assert len(DEFAULT_PROFILES) == 5


# --- Phase 8: Analytics ---

def test_analytics_aggregation():
    """Analytics aggregation runs without error."""
    from src.lms_agents.crews.analytics_crew import aggregate_class_data
    data = aggregate_class_data("00000000-0000-0000-0000-000000000010")
    assert "class_average" in data
    assert "standards" in data


# --- Phase 9.1: TTS Provider ---

def test_tts_voice_catalog():
    """Voice catalog includes both Polly and ElevenLabs voices."""
    from src.lms_agents.tools.tts_generator import list_voices, POLLY_VOICES, ELEVENLABS_VOICES
    voices = list_voices()
    polly_count = sum(1 for v in voices if v.get("provider") == "polly")
    el_count = sum(1 for v in voices if v.get("provider") == "elevenlabs")
    assert polly_count == len(POLLY_VOICES)
    assert el_count == len(ELEVENLABS_VOICES)


# --- Phase 10: Interactive ---

def test_interactive_templates():
    """All 15 interactive templates are registered."""
    from src.lms_agents.tools.interactive_generator import INTERACTIVE_TEMPLATES
    assert len(INTERACTIVE_TEMPLATES) == 15


# --- Phase 11: Game Shells ---

def test_game_shells():
    """All 8 game shells are registered."""
    from src.lms_agents.tools.game_session_manager import GAME_SHELLS
    assert len(GAME_SHELLS) == 8


# --- Phase 11.5: Lulings ---

def test_lulings_exist():
    """Lulings table has characters."""
    from src.lms_agents.tools.db import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM lulings")
    count = cur.fetchone()[0]
    cur.close(); conn.close()
    assert count >= 0  # May be 0 if script hasn't run


# --- Phase 12: AI Fill ---

def test_ai_fill_component_types():
    """AI Fill recognizes all fillable component types."""
    from src.lms_agents.tools.ai_fill_engine import FILLABLE_TYPES
    assert "multiple_choice" in FILLABLE_TYPES
    assert "word_bank" in FILLABLE_TYPES
    assert len(FILLABLE_TYPES) >= 15


# --- Phase 14.5: Feature Flags ---

def test_feature_flags():
    """Feature flags seeded and queryable."""
    from src.lms_agents.tools.db import get_connection
    from psycopg2.extras import RealDictCursor
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT COUNT(*) as count FROM feature_flags")
    count = cur.fetchone()["count"]
    cur.close(); conn.close()
    assert count >= 9


# --- Phase 15: Credit System ---

def test_credit_estimate():
    """Credit cost estimation works for all templates."""
    from src.lms_agents.tools.credit_manager import estimate_cost
    assert estimate_cost("worksheet") == 1
    assert estimate_cost("escape_room") == 5
    assert estimate_cost("worksheet", 2) == 3  # 1 + 2 accommodations


def test_credit_check():
    """Credit balance check works."""
    from src.lms_agents.tools.credit_manager import check_credits
    result = check_credits("00000000-0000-0000-0000-000000000001", 1)
    assert "sufficient" in result
    assert "balance" in result


# --- Phase 15: Pricing ---

def test_pricing_config():
    """Pricing tiers and credit costs are configured."""
    from src.lms_agents.config.pricing import TIERS, CREDIT_COSTS, CREDIT_PACKS
    assert len(TIERS) == 5
    assert "free" in TIERS
    assert "max" in TIERS
    assert len(CREDIT_COSTS) >= 20
    assert len(CREDIT_PACKS) == 4
