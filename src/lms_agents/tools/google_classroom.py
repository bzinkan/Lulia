"""
Google Classroom API — list courses, push assignments, manage topics.
"""
import logging
import os

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from src.lms_agents.tools.google_auth import get_credentials

log = logging.getLogger(__name__)


def _get_service(teacher_id: str, api: str = "classroom", version: str = "v1"):
    """Build a Google API service client."""
    credentials = get_credentials(teacher_id)
    if not credentials:
        raise ValueError("Teacher not connected to Google")
    return build(api, version, credentials=credentials)


def list_courses(teacher_id: str) -> list[dict]:
    """List teacher's active Classroom courses."""
    service = _get_service(teacher_id, "classroom", "v1")
    results = service.courses().list(teacherId="me", courseStates=["ACTIVE"]).execute()
    courses = results.get("courses", [])
    return [
        {
            "course_id": c["id"],
            "name": c.get("name", ""),
            "section": c.get("section", ""),
            "enrollment_code": c.get("enrollmentCode", ""),
        }
        for c in courses
    ]


def list_students(teacher_id: str, course_id: str) -> list[dict]:
    """List students in a Classroom course."""
    service = _get_service(teacher_id, "classroom", "v1")
    results = service.courses().students().list(courseId=course_id).execute()
    students = results.get("students", [])
    return [
        {
            "student_id": s["userId"],
            "name": s.get("profile", {}).get("name", {}).get("fullName", ""),
            "email": s.get("profile", {}).get("emailAddress", ""),
        }
        for s in students
    ]


def create_topic(teacher_id: str, course_id: str, topic_name: str) -> str:
    """Create a topic in Classroom for organizing assignments. Returns topic ID."""
    service = _get_service(teacher_id, "classroom", "v1")
    topic = service.courses().topics().create(
        courseId=course_id, body={"name": topic_name}
    ).execute()
    return topic["topicId"]


def push_assignment_to_classroom(
    teacher_id: str,
    course_id: str,
    title: str,
    description: str,
    materials: list[dict] | None = None,
    topic_id: str | None = None,
    max_points: int | None = None,
    student_ids: list[str] | None = None,
) -> dict:
    """
    Push an assignment to Google Classroom.

    materials: [{"link": {"url": "..."}}, {"driveFile": {"driveFile": {"id": "..."}}}]
    student_ids: if provided, assigns to specific students (for accommodations)
    """
    service = _get_service(teacher_id, "classroom", "v1")

    coursework = {
        "title": title,
        "description": description,
        "workType": "ASSIGNMENT",
        "state": "PUBLISHED",
    }

    if materials:
        coursework["materials"] = materials
    if topic_id:
        coursework["topicId"] = topic_id
    if max_points:
        coursework["maxPoints"] = max_points

    if student_ids:
        coursework["assigneeMode"] = "INDIVIDUAL_STUDENTS"
        coursework["individualStudentsOptions"] = {"studentIds": student_ids}
    else:
        coursework["assigneeMode"] = "ALL_STUDENTS"

    result = service.courses().courseWork().create(
        courseId=course_id, body=coursework
    ).execute()

    return {
        "coursework_id": result["id"],
        "alternate_link": result.get("alternateLink", ""),
    }


def upload_to_drive(teacher_id: str, file_path: str, filename: str, mime_type: str = "application/pdf") -> str:
    """Upload a file to Google Drive and return the file ID."""
    service = _get_service(teacher_id, "drive", "v3")

    file_metadata = {"name": filename}
    media = MediaFileUpload(file_path, mimetype=mime_type)
    file = service.files().create(
        body=file_metadata, media_body=media, fields="id"
    ).execute()

    # Make it viewable by anyone with the link
    service.permissions().create(
        fileId=file["id"],
        body={"type": "anyone", "role": "reader"},
    ).execute()

    return file["id"]
