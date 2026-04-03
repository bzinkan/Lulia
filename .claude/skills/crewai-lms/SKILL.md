---
name: crewai-lms
description: "Use this skill whenever building, modifying, or debugging CrewAI agents, crews, tasks, or tools for the AI-powered LMS. Triggers include: writing agent YAML, creating crew files, defining tasks, building tools, configuring multi-model LLM routing (Claude vs Gemini vs Bedrock), or troubleshooting agent execution. Also trigger for work order patterns, suggest-then-approve workflow, Generation History dedup, accommodation version generation, or interactive activity generation."
---

# CrewAI LMS Agent Development

## LLM Routing (Three Providers, Zero Overlap)

| Provider | Used For | SDK |
|----------|---------|-----|
| Claude (Anthropic) | All content generation, reasoning, coding, React components, planning, chat | anthropic / langchain_anthropic |
| Gemini (Google) | Google Slides, Google Forms, Imagen illustrations for video | google-generativeai / langchain_google |
| AWS Bedrock (Titan) | Text embedding for RAG Knowledge Base | boto3 (same as S3) |

Format Agent routing by output format:
- `google_slides` / `google_forms` → Gemini Flash
- `interactive_assessment` / `live_game` → Claude (generates React)
- `pdf_*` (worksheet, task cards, Bingo, etc.) → Claude Haiku
- `video` → Claude Opus (script) + Gemini Imagen (illustrations)

## Agent Registry (16 Agents, 5 Crews)

| # | Agent | Crew | LLM |
|---|-------|------|-----|
| 1 | Lesson Planner | Planning | Sonnet |
| 2 | Knowledge Ingestion | Knowledge | Haiku |
| 3 | Curriculum Agent | Assignment | Sonnet |
| 4 | Content Agent | Assignment | Opus/Sonnet |
| 5 | Video Script Agent | Assignment | Opus |
| 6 | Rubric Agent | Assignment | Sonnet |
| 7 | QA Agent | Assignment | Opus |
| 8 | Format Agent | Assignment | **Gemini/Haiku** |
| 9 | OCR Agent | Scan&Grade | ML |
| 10 | Match Agent | Scan&Grade | Haiku |
| 11 | Grading Agent | Scan&Grade | Sonnet |
| 12 | Review Router | Scan&Grade | Haiku |
| 13 | Analytics Agent | Analytics | Haiku |
| 14 | Report Agent | Analytics | Haiku |
| 15 | Standards Import | Standards | Opus |
| 16 | Crosswalk Agent | Standards | Sonnet |

## Crew 1: Assignment Generation (Updated Chain)

Standard: Curriculum → Content → Rubric → QA → Format
Video: Curriculum → Video Script → Rubric → QA → Format (Imagen)
Interactive: Curriculum → Content → QA → Format (Claude generates React → S3)

Content Agent checks Generation History before generating. Can produce IEP/504/ELL/Gifted versions.
QA Agent verifies no semantic duplicates AND fact-checks against RAG KB.
Grading Agent processes both paper scans AND interactive activity responses.

## Work Order Pattern

```python
work_order = {
    "work_order_id": "WO-2026-W12-THU-01",
    "output_template_id": "interactive_assessment",  # or "task_cards", "bingo", etc.
    "output_format": "react_s3",  # "pdf", "google_slides", "google_forms", "video"
    "interaction_types": ["drag_drop", "multiple_choice"],  # for interactive
    "game_shell_id": None,  # "gold_rush", "tower_defense" for live games
    "standards_ids": ["OH.4.NF.5"],
    "standards_tier": "state",
    "question_count": 12,
    "has_kb_coverage": True,
    "accommodation_versions": ["iep_reduced", "ell_beginner"],
    "student_access_method": "class_code",
    "randomize_per_student": True,
    "google_classroom": {"course_id": "12345", "topic": "Week 12"}
}
```

## Generation History Check (Content Agent)

```python
previous = generation_history.query(
    teacher_id=teacher_id,
    standard_codes=work_order["standards_ids"],
    freshness_window_months=6
)
prompt += f"\nDo NOT generate content similar to: {previous.summaries}"
```

## Accommodation Generation

```python
for profile in work_order.get("accommodation_versions", []):
    modifications = get_profile_modifications(profile)
    modified = content_agent.regenerate(original, modifications)
    qa_agent.review(modified)
    format_agent.render(modified, same_template=True)  # dignity: same visual design
```

## Key Rules

1. Three providers: Claude (reasoning), Gemini (Google + Imagen), Bedrock (embedding)
2. Format Agent is multi-model — routes by output format
3. Content Agent ALWAYS checks Generation History before generating
4. QA Agent verifies no duplicates AND fact-checks against RAG KB
5. Interactive: Claude generates React → S3. Game shells are pre-built, only questions generated.
6. Accommodation versions use SAME template (dignity principle)
7. Planner is subject-aware: labs for science, passages for ELA, manipulatives for math
8. Flexible duration: 1 day (sub plan) to year-long overview
