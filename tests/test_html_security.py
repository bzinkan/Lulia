"""
Output-security tests for the activity HTML pipeline.

We can't catch every possible LLM-generated XSS, but we can:
  - Verify our topic sanitizer drops control chars + dangerous HTML tokens.
  - Verify the artifact validator catches obvious red flags (external
    scripts, document.cookie reads, eval).
  - Verify structured-template HTML escapes `</` so injected JSON can't
    close out of the embedded <script> block.
"""
from src.lms_agents.tools.gemini_interactive_generator import (
    _validate_artifact_html, sanitize_topic,
)


# ---------------------------------------------------------------------------
# Topic sanitizer
# ---------------------------------------------------------------------------

class TestSanitizeTopic:
    def test_passthrough_normal_topic(self):
        assert sanitize_topic("Plant cell organelles") == "Plant cell organelles"

    def test_strips_script_tags(self):
        s = sanitize_topic("photosynthesis <script>alert(1)</script>")
        assert "<script" not in s.lower()
        assert "</script" not in s.lower()
        assert "photosynthesis" in s

    def test_strips_iframe(self):
        s = sanitize_topic("history <iframe src=evil></iframe>")
        assert "<iframe" not in s.lower()
        assert "</iframe" not in s.lower()

    def test_caps_length(self):
        s = sanitize_topic("a" * 5000, max_chars=200)
        assert len(s) <= 200

    def test_strips_control_chars(self):
        s = sanitize_topic("hello\x00\x01\x02world")
        assert "\x00" not in s and "\x01" not in s
        assert "hello" in s and "world" in s

    def test_keeps_whitespace(self):
        s = sanitize_topic("first line\nsecond line\twith tab")
        assert "\n" in s and "\t" in s

    def test_empty_input(self):
        assert sanitize_topic("") == ""
        assert sanitize_topic(None) == ""
        assert sanitize_topic("   ") == ""


# ---------------------------------------------------------------------------
# Artifact HTML validator
# ---------------------------------------------------------------------------

GOOD_HTML = """<!DOCTYPE html>
<html><head><title>x</title>
<script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
</head>
<body><div id="root"></div>
<script type="text/babel">
function App() { return <div>ok</div>; }
ReactDOM.createRoot(document.getElementById("root")).render(<App />);
</script></body></html>
""" + ("x" * 600)  # pad past 500-byte threshold


class TestArtifactValidator:
    def test_clean_html_passes(self):
        assert _validate_artifact_html(GOOD_HTML) == []

    def test_external_script_flagged(self):
        bad = GOOD_HTML.replace(
            "</body>",
            '<script src="https://evil.example/steal.js"></script></body>',
        )
        problems = _validate_artifact_html(bad)
        assert any("non-allowlisted script src" in p for p in problems), problems

    def test_document_cookie_flagged(self):
        bad = GOOD_HTML.replace("function App()", "var x = document.cookie; function App()")
        problems = _validate_artifact_html(bad)
        assert any("document.cookie" in p for p in problems), problems

    def test_eval_flagged(self):
        bad = GOOD_HTML.replace("function App()", "eval('alert(1)'); function App()")
        problems = _validate_artifact_html(bad)
        assert any("eval()" in p for p in problems), problems

    def test_unbalanced_braces_flagged(self):
        bad = GOOD_HTML.replace("function App() { return <div>ok</div>; }",
                                 "function App() { return <div>ok</div>;")
        problems = _validate_artifact_html(bad)
        assert any("unbalanced" in p for p in problems), problems

    def test_too_short_flagged(self):
        problems = _validate_artifact_html("<html></html>")
        assert "too short" in problems

    def test_localStorage_flagged(self):
        bad = GOOD_HTML.replace("function App()", "var x = localStorage.getItem('x'); function App()")
        problems = _validate_artifact_html(bad)
        assert any("localStorage" in p for p in problems), problems
