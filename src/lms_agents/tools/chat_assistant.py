"""
Chat Assistant — context-aware AI chat for teachers.

Uses Claude with function calling. Knows the current page context,
class, and assignment. Can trigger actions across the system.
"""
import json
import logging
import os
import re
from uuid import uuid4

import anthropic
from psycopg2.extras import Json, RealDictCursor

from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)
SONNET = "claude-sonnet-4-20250514"

TOOLS = [
    {
        "name": "search_knowledge_base",
        "description": "Search the teacher's uploaded curriculum materials and textbooks",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "get_class_analytics",
        "description": "Get class performance data: mastery percentages, struggling standards",
        "input_schema": {"type": "object", "properties": {"class_id": {"type": "string"}}, "required": ["class_id"]},
    },
    {
        "name": "explain_standard",
        "description": "Explain an educational standard in plain language with teaching tips",
        "input_schema": {"type": "object", "properties": {"standard_code": {"type": "string"}}, "required": ["standard_code"]},
    },
    {
        "name": "recommend_template",
        "description": "Suggest the best assignment template for a topic and subject",
        "input_schema": {"type": "object", "properties": {"subject": {"type": "string"}, "topic": {"type": "string"}}, "required": ["subject", "topic"]},
    },
    {
        "name": "find_assignment",
        "description": "Search existing assignments by keyword",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
]


def _execute_tool(name: str, args: dict, teacher_id: str) -> str:
    """Execute a tool call and return the result as a string."""
    try:
        if name == "search_knowledge_base":
            from src.lms_agents.tools.rag_search import search_kb
            results = search_kb(query=args["query"], teacher_id=teacher_id, top_k=3)
            return json.dumps([{"source": r["source_name"], "content": r["content"][:200]} for r in results])

        elif name == "get_class_analytics":
            from src.lms_agents.crews.analytics_crew import aggregate_class_data
            data = aggregate_class_data(args["class_id"])
            return json.dumps({"average": data["class_average"], "struggling": [s["standard_code"] for s in data.get("struggling_standards", [])], "mastered": data["mastered_count"]})

        elif name == "explain_standard":
            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT code, description FROM standards WHERE code ILIKE %s LIMIT 3", (f"%{args['standard_code']}%",))
            rows = [dict(r) for r in cur.fetchall()]
            cur.close(); conn.close()
            return json.dumps(rows) if rows else "Standard not found"

        elif name == "recommend_template":
            templates = {"Mathematics": ["worksheet", "task_cards", "bingo"], "ELA": ["reading_comprehension", "vocab_cards"], "Science": ["lab_activity", "graphic_organizer"]}
            recs = templates.get(args.get("subject", ""), ["worksheet", "quiz_test"])
            return json.dumps({"recommended": recs, "topic": args.get("topic", "")})

        elif name == "find_assignment":
            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                "SELECT assignment_id, title, output_template_id, created_at FROM assignments WHERE title ILIKE %s ORDER BY created_at DESC LIMIT 5",
                (f"%{args['query']}%",),
            )
            rows = [dict(r) for r in cur.fetchall()]
            cur.close(); conn.close()
            return json.dumps(rows)

    except Exception as e:
        return json.dumps({"error": str(e)})

    return "{}"


def chat_message(
    teacher_id: str,
    message: str,
    context: dict | None = None,
    session_id: str | None = None,
) -> dict:
    """
    Process a chat message from a teacher.
    Returns Claude's response + any function call results.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"response": "Chat assistant is not configured. Please set your Anthropic API key.", "tool_results": []}

    client = anthropic.Anthropic(api_key=api_key)

    # Load or create session
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if session_id:
        cur.execute("SELECT messages FROM chat_sessions WHERE session_id = %s AND teacher_id = %s::uuid", (session_id, teacher_id))
        row = cur.fetchone()
        history = row["messages"] if row else []
    else:
        session_id = str(uuid4())
        history = []

    # Add user message
    history.append({"role": "user", "content": message})

    # Build system prompt with context
    ctx = context or {}
    system = (
        "You are Lulia's AI teaching assistant. You help teachers create standards-aligned content, "
        "understand analytics, and manage their classroom. Be warm, concise, and actionable. "
        f"Current page: {ctx.get('page', 'dashboard')}. "
        f"Current class: {ctx.get('class_name', 'not selected')}. "
        "Use the available tools when the teacher asks for data or actions. "
        "Always respond helpfully even without tools."
    )

    # Filter history to only simple text messages (no tool blocks)
    clean_history = [m for m in history if isinstance(m.get("content"), str)]

    # Call Claude with tools
    try:
        response = client.messages.create(
            model=SONNET, max_tokens=1024, system=system,
            messages=clean_history[-10:],  # Keep last 10 messages for context window
            tools=TOOLS,
        )

        # Process response
        tool_results = []
        assistant_text = ""

        for block in response.content:
            if block.type == "text":
                assistant_text += block.text
            elif block.type == "tool_use":
                result = _execute_tool(block.name, block.input, teacher_id)
                tool_results.append({"tool": block.name, "input": block.input, "result": json.loads(result) if result.startswith(("{", "[")) else result})

        # If there were tool calls but no text, summarize the tool results
        if tool_results and not assistant_text:
            tool_summary = "; ".join(f"[{tr['tool']}] returned data" for tr in tool_results)
            assistant_text = f"I found some information for you. {tool_summary}."

        # Store in history (simplified for storage)
        history.append({"role": "assistant", "content": assistant_text})

    except Exception as e:
        log.error(f"[Chat] Error: {e}")
        assistant_text = "I'm sorry, I had trouble processing that. Could you try again?"
        history.append({"role": "assistant", "content": assistant_text})

    # Save session
    cur2 = conn.cursor()
    cur2.execute(
        """INSERT INTO chat_sessions (session_id, teacher_id, messages, context, updated_at)
           VALUES (%s, %s::uuid, %s, %s, NOW())
           ON CONFLICT (session_id) DO UPDATE SET messages = %s, updated_at = NOW()""",
        (session_id, teacher_id, Json(history[-20:]), Json(ctx), Json(history[-20:])),
    )
    conn.commit()
    cur.close(); cur2.close(); conn.close()

    return {
        "response": assistant_text,
        "tool_results": tool_results,
        "session_id": session_id,
    }
