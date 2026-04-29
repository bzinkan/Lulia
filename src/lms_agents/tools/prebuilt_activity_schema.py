"""Validation models for Git-backed prebuilt activity records."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


STATUS_VALUES = {"draft", "review", "approved", "published", "archived"}
DIFFICULTY_VALUES = {"support", "core", "challenge", "honors", "ap"}

SUPPORTED_VISUAL_KINDS = {
    "scientific_visual",
    "interactive_graph",
    "geometry_diagram",
    "annotated_text",
    "primary_source_viewer",
    "layered_map",
    "timeline",
    "data_lab",
    "simulation",
    "case_study",
    "code_trace",
    "sentence_builder",
    "visual_scene",
}

SUPPORTED_ACTIVITY_TYPES = {
    "visual_study",
    "document_study",
    "model_explorer",
    "timeline_builder",
    "evidence_sort",
    "argument_builder",
    "matching_pairs",
    "drag_sort",
    "case_study_lab",
    "code_trace_lab",
    "language_scene_lab",
    "data_lab",
    "geometry_lab",
    "math_model_lab",
    "layered_map",
    "source_or_timeline_study",
    "guided_activity",
    "writing_lab",
    "cer_builder",
}

SUPPORTED_CHECK_TYPES = {
    "multiple_choice",
    "hotspot",
    "short_response",
    "evidence_select",
    "drag_sort",
    "matching",
    "prediction",
    "sentence_builder",
    "code_prediction",
}


class Choice(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    text: str
    correct: bool = False


class Check(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    question: str
    choices: list[Choice] = Field(default_factory=list)
    feedback: dict[str, Any] = Field(default_factory=dict)
    standard_code: str = ""

    @field_validator("type")
    @classmethod
    def supported_check_type(cls, value: str) -> str:
        if value not in SUPPORTED_CHECK_TYPES:
            raise ValueError(f"unsupported check type '{value}'")
        return value

    @model_validator(mode="after")
    def validate_multiple_choice(self) -> "Check":
        if self.type == "multiple_choice":
            if len(self.choices) < 2:
                raise ValueError("multiple_choice checks require at least two choices")
            if not any(choice.correct for choice in self.choices):
                raise ValueError("multiple_choice checks require at least one correct choice")
        return self


class PrebuiltActivity(BaseModel):
    model_config = ConfigDict(extra="allow")

    activity_id: str
    title: str | None = None
    activity_type: str
    subject: str | None = None
    course: str | None = None
    grade_level: str | None = None
    grade_band: str | None = None
    standards: list[Any] = Field(default_factory=list)
    visual_surface: dict[str, Any] = Field(default_factory=dict)
    study_mode: dict[str, Any] = Field(default_factory=dict)
    practice_mode: dict[str, Any] = Field(default_factory=dict)
    content: dict[str, Any] = Field(default_factory=dict)
    checks: list[Check] = Field(default_factory=list)
    reflection_prompt: dict[str, Any] = Field(default_factory=dict)
    customizable_fields: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    difficulty: str = "core"
    estimated_minutes: int = 10
    status: str | None = None
    source: str = "lulia_prebuilt"
    version: int = 1

    @field_validator("activity_type")
    @classmethod
    def supported_activity_type(cls, value: str) -> str:
        if value not in SUPPORTED_ACTIVITY_TYPES:
            raise ValueError(f"unsupported activity_type '{value}'")
        return value

    @field_validator("difficulty")
    @classmethod
    def supported_difficulty(cls, value: str) -> str:
        if value not in DIFFICULTY_VALUES:
            raise ValueError(f"unsupported difficulty '{value}'")
        return value

    @field_validator("status")
    @classmethod
    def supported_status(cls, value: str | None) -> str | None:
        if value is not None and value not in STATUS_VALUES:
            raise ValueError(f"unsupported status '{value}'")
        return value

    @field_validator("estimated_minutes")
    @classmethod
    def reasonable_minutes(cls, value: int) -> int:
        if value < 1 or value > 120:
            raise ValueError("estimated_minutes must be between 1 and 120")
        return value

    @model_validator(mode="after")
    def validate_visual_kind(self) -> "PrebuiltActivity":
        kind = (self.visual_surface or {}).get("kind")
        if kind and kind not in SUPPORTED_VISUAL_KINDS:
            raise ValueError(f"unsupported visual_surface.kind '{kind}'")
        return self

    def to_seed_content(self, lesson_title: str) -> dict[str, Any]:
        content = dict(self.content or {})
        content.setdefault("title", self.title or lesson_title)
        if self.study_mode:
            content.setdefault("study_mode", self.study_mode)
        if self.practice_mode:
            content.setdefault("practice_mode", self.practice_mode)
        if self.customizable_fields:
            content.setdefault("customizable_fields", self.customizable_fields)
        return content


class PrebuiltLesson(BaseModel):
    model_config = ConfigDict(extra="allow")

    lesson_number: int
    lesson_title: str
    activity: PrebuiltActivity | None = None
    suggested_activity_type: str | None = None
    target_standards: list[Any] = Field(default_factory=list)


class PrebuiltUnit(BaseModel):
    model_config = ConfigDict(extra="allow")

    unit_number: int
    unit_title: str
    lessons: list[PrebuiltLesson]


class PrebuiltCourseFile(BaseModel):
    model_config = ConfigDict(extra="allow")

    course: str
    grade_band: str
    subject: str
    grade_level: str | None = None
    units: list[PrebuiltUnit]


def load_course_file(path: Path) -> PrebuiltCourseFile:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc

    try:
        return PrebuiltCourseFile.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"{path}: {exc}") from exc


def iter_seed_rows(course_doc: PrebuiltCourseFile, *, default_status: str = "published"):
    if default_status not in STATUS_VALUES:
        raise ValueError(f"unsupported default status '{default_status}'")

    for unit in course_doc.units:
        for lesson in unit.lessons:
            if lesson.activity is None:
                continue
            activity = lesson.activity
            status = activity.status or default_status
            if status not in STATUS_VALUES:
                raise ValueError(f"{activity.activity_id}: unsupported status '{status}'")
            yield {
                "activity_id": activity.activity_id,
                "grade_level": activity.grade_level or course_doc.grade_level,
                "grade_band": activity.grade_band or course_doc.grade_band,
                "subject": activity.subject or course_doc.subject,
                "course": activity.course or course_doc.course,
                "unit_number": unit.unit_number,
                "unit_title": unit.unit_title,
                "lesson_number": lesson.lesson_number,
                "lesson_title": lesson.lesson_title,
                "activity_type": activity.activity_type,
                "standards": activity.standards,
                "visual_surface": activity.visual_surface,
                "content": activity.to_seed_content(lesson.lesson_title),
                "checks": [check.model_dump(mode="json") for check in activity.checks],
                "reflection_prompt": activity.reflection_prompt,
                "tags": activity.tags,
                "difficulty": activity.difficulty,
                "estimated_minutes": activity.estimated_minutes,
                "status": status,
                "source": activity.source,
                "version": activity.version,
            }
