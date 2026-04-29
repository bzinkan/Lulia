"""Self-contained HTML renderers for prebuilt activity previews and copies."""
from __future__ import annotations

import html
import json
from typing import Any


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _json_for_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def _activity_title(activity: dict[str, Any]) -> str:
    content = activity.get("content") or {}
    return str(activity.get("title") or content.get("title") or activity.get("lesson_title") or "Prebuilt Activity")


def _base_css() -> str:
    return """
    :root {
      color-scheme: light;
      --ink: #28312f;
      --muted: #66736f;
      --line: #d8ded7;
      --paper: #fffaf1;
      --panel: #ffffff;
      --sage: #6e9075;
      --coral: #d86c52;
      --mustard: #d69a2d;
      --sky: #8cb9c4;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--paper);
      color: var(--ink);
    }
    .activity-shell {
      min-height: 100vh;
      padding: 22px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .topbar {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--line);
    }
    h1 {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      font-size: clamp(24px, 4vw, 40px);
      line-height: 1.05;
      letter-spacing: 0;
    }
    .meta {
      margin-top: 8px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
    }
    .chip {
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.7);
      border-radius: 999px;
      padding: 5px 10px;
      white-space: nowrap;
    }
    .mode-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    button {
      min-height: 38px;
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--ink);
      border-radius: 8px;
      padding: 8px 12px;
      font-weight: 700;
      cursor: pointer;
    }
    button.primary {
      background: var(--coral);
      border-color: var(--coral);
      color: white;
    }
    .workspace {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 320px;
      gap: 16px;
      align-items: start;
    }
    .stage-wrap, .side-panel, .doc-viewer, .model-viewer {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 12px 35px rgba(45, 49, 46, 0.08);
    }
    .stage-wrap {
      overflow: hidden;
      min-height: 520px;
    }
    .visual-stage {
      position: relative;
      width: 100%;
      aspect-ratio: 16 / 10;
      min-height: 420px;
      background: linear-gradient(180deg, #eef8f6 0%, #f8f2dd 100%);
    }
    .visual-stage img, .visual-stage > svg.base-scene {
      width: 100%;
      height: 100%;
      display: block;
      object-fit: cover;
    }
    .leader-layer {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
    }
    .leader-layer line {
      stroke: rgba(40,49,47,0.55);
      stroke-width: 1.5;
      stroke-dasharray: 4 4;
    }
    .leader-layer circle {
      fill: var(--coral);
      stroke: white;
      stroke-width: 2;
    }
    .annotation {
      position: absolute;
      transform: translate(-50%, -50%);
      border-color: rgba(40,49,47,0.18);
      background: rgba(255,255,255,0.92);
      box-shadow: 0 8px 20px rgba(40,49,47,0.16);
      font-size: 13px;
      max-width: 150px;
      white-space: normal;
    }
    .annotation.active {
      background: var(--coral);
      color: white;
      border-color: var(--coral);
    }
    .labels-hidden .annotation, .labels-hidden .leader-layer {
      display: none;
    }
    .side-panel {
      padding: 16px;
      position: sticky;
      top: 12px;
    }
    .side-panel h2 {
      margin: 0 0 8px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 22px;
    }
    .side-panel p, .check-card p, .doc-viewer p {
      color: var(--muted);
      line-height: 1.5;
      margin: 0;
    }
    .section-title {
      margin: 18px 0 8px;
      font-size: 12px;
      font-weight: 800;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .check-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      margin-top: 10px;
      background: #fffdf7;
    }
    .choice {
      width: 100%;
      text-align: left;
      margin-top: 8px;
      font-weight: 650;
    }
    .feedback {
      margin-top: 10px;
      font-size: 13px;
      font-weight: 700;
    }
    .doc-viewer, .model-viewer {
      padding: 18px;
    }
    .doc-line {
      display: grid;
      grid-template-columns: 32px 1fr;
      gap: 10px;
      padding: 12px 0;
      border-bottom: 1px solid var(--line);
      line-height: 1.65;
    }
    .line-num {
      color: var(--muted);
      font-weight: 800;
    }
    .category-grid {
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }
    .category {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #fffdf7;
    }
    .graph-box {
      width: 100%;
      aspect-ratio: 16 / 10;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcff;
      overflow: hidden;
    }
    .controls {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 12px;
      margin-top: 14px;
    }
    .control {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #fffdf7;
    }
    input[type="range"] { width: 100%; }
    textarea {
      width: 100%;
      min-height: 92px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      resize: vertical;
      font: inherit;
    }
    @media (max-width: 900px) {
      .activity-shell { padding: 14px; }
      .workspace { grid-template-columns: 1fr; }
      .side-panel { position: static; }
      .topbar { flex-direction: column; }
      .mode-actions { justify-content: flex-start; }
      .stage-wrap { min-height: 0; }
      .visual-stage { min-height: 340px; }
    }
    """


def _animal_cell_svg() -> str:
    return """
    <svg class="base-scene" viewBox="0 0 1000 625" role="img" aria-label="Unlabeled animal cell illustration" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="cellFill" cx="48%" cy="45%" r="58%">
          <stop offset="0%" stop-color="#fff0d3"/>
          <stop offset="55%" stop-color="#f7caa7"/>
          <stop offset="100%" stop-color="#e98f75"/>
        </radialGradient>
        <radialGradient id="nucleusFill" cx="48%" cy="42%" r="55%">
          <stop offset="0%" stop-color="#cfd9ff"/>
          <stop offset="100%" stop-color="#7d87bd"/>
        </radialGradient>
      </defs>
      <rect width="1000" height="625" fill="#f4fbfa"/>
      <path d="M197 311C197 192 320 103 476 98c169-6 324 73 358 199 36 132-62 233-222 257-183 28-385-52-414-187-4-18-4-37-1-56z" fill="url(#cellFill)" stroke="#b85f54" stroke-width="12"/>
      <ellipse cx="445" cy="263" rx="116" ry="93" fill="url(#nucleusFill)" stroke="#56639b" stroke-width="8"/>
      <ellipse cx="454" cy="266" rx="38" ry="29" fill="#6975ad" opacity=".75"/>
      <path d="M302 344c45-42 94-47 145-16M303 386c60-47 127-48 197-3M325 423c56-31 116-30 181 2" fill="none" stroke="#a66d45" stroke-width="14" stroke-linecap="round"/>
      <path d="M611 218c55-29 123 0 139 45 15 42-16 88-72 95-62 7-109-38-94-86 5-19 15-36 27-54z" fill="#f5b34b" stroke="#bf7b23" stroke-width="7"/>
      <path d="M611 240c39 23 81 24 126 3M604 274c43 28 89 29 138 4M616 309c32 19 67 21 106 6" fill="none" stroke="#8f5f24" stroke-width="5" stroke-linecap="round"/>
      <path d="M674 430c47-25 103-2 116 39 13 42-20 80-75 81-47 0-88-33-83-72 2-16 18-33 42-48z" fill="#f3bc58" stroke="#b87a22" stroke-width="7"/>
      <path d="M665 469c35 19 71 22 110 8M673 500c28 15 58 17 92 6" fill="none" stroke="#8f5f24" stroke-width="5" stroke-linecap="round"/>
      <path d="M328 472c-12-39 18-70 72-75 71-7 125 29 124 75-1 44-54 72-121 63-40-5-64-26-75-63z" fill="#95c7af" stroke="#5c9479" stroke-width="7"/>
      <path d="M318 185c38 19 77 20 117 2M560 124c54 13 96 39 126 79M227 302c32 33 73 46 124 39M771 353c29 15 46 41 50 78" fill="none" stroke="#ffffff" stroke-width="16" stroke-linecap="round" opacity=".55"/>
      <circle cx="271" cy="248" r="25" fill="#be7bb4" opacity=".85"/>
      <circle cx="577" cy="383" r="21" fill="#be7bb4" opacity=".85"/>
      <circle cx="744" cy="290" r="18" fill="#be7bb4" opacity=".85"/>
    </svg>
    """


def _water_cycle_svg() -> str:
    return """
    <svg class="base-scene" viewBox="0 0 1000 625" role="img" aria-label="Unlabeled water cycle landscape" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="sky" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="#bfe3f1"/>
          <stop offset="100%" stop-color="#eff8fb"/>
        </linearGradient>
        <linearGradient id="water" x1="0" x2="1">
          <stop offset="0%" stop-color="#6fb5c6"/>
          <stop offset="100%" stop-color="#3d879e"/>
        </linearGradient>
      </defs>
      <rect width="1000" height="625" fill="url(#sky)"/>
      <circle cx="125" cy="105" r="48" fill="#ffd35a"/>
      <path d="M0 380l168-176 110 120 137-160 173 214z" fill="#7f9b72"/>
      <path d="M158 215l42 46 35-39 44 103-111-121zM414 165l58 82 46-57 69 190z" fill="#eff3ed" opacity=".9"/>
      <path d="M420 386c88-42 165-48 230-18 74 35 152 40 350 17v240H0V438c172 35 307 18 420-52z" fill="#88b66f"/>
      <path d="M0 482c145-35 260-30 348 18 96 53 206 52 344 8 95-30 198-41 308-34v151H0z" fill="url(#water)" opacity=".9"/>
      <path d="M515 262c54-48 119-44 160 3 54-19 104 8 117 52 17 58-34 99-103 82H475c-78 12-122-53-90-105 24-39 80-52 130-32z" fill="#fff" opacity=".9"/>
      <path d="M205 195c34-27 80-24 107 4 42-13 78 11 84 43 9 47-36 72-84 59H166c-48 8-78-33-59-67 16-29 56-39 98-39z" fill="#fff" opacity=".82"/>
      <path d="M690 420c-43 18-85 42-126 74-48 38-98 54-150 48 53-20 91-47 115-81 34-46 85-60 161-41z" fill="#4d9670"/>
      <path d="M420 505c36 30 74 43 115 37 30-4 58-17 84-38" fill="none" stroke="#d9f1f7" stroke-width="18" stroke-linecap="round" opacity=".75"/>
      <path d="M692 341c0 42 0 42-19 72M733 344c-3 39-3 39-26 70M651 346c-2 33-2 33-17 57" stroke="#5c93ad" stroke-width="8" stroke-linecap="round" opacity=".7"/>
      <path d="M316 438c28 38 34 82 19 131M388 448c26 49 28 94 6 137" stroke="#3f7e6b" stroke-width="7" stroke-linecap="round" opacity=".55"/>
      <path d="M210 390c26-43 50-82 71-116" stroke="#f4ffff" stroke-width="10" stroke-linecap="round" opacity=".75"/>
      <path d="M232 288l48-17 0 51z" fill="#f4ffff" opacity=".75"/>
    </svg>
    """


def _linear_graph_svg() -> str:
    return """
    <svg id="linearGraph" viewBox="0 0 800 500" role="img" aria-label="Linear graph explorer" xmlns="http://www.w3.org/2000/svg">
      <rect width="800" height="500" fill="#fbfcff"/>
      <g stroke="#e4e8ef" stroke-width="1">
        <path d="M80 40v380M150 40v380M220 40v380M290 40v380M360 40v380M430 40v380M500 40v380M570 40v380M640 40v380M710 40v380"/>
        <path d="M80 420h640M80 350h640M80 280h640M80 210h640M80 140h640M80 70h640"/>
      </g>
      <path d="M80 420h640M80 420V40" stroke="#28312f" stroke-width="3" fill="none"/>
      <path id="modelLine" d="M80 385L710 105" stroke="#d86c52" stroke-width="6" stroke-linecap="round" fill="none"/>
      <circle id="pointA" cx="80" cy="385" r="8" fill="#6e9075"/>
      <circle id="pointB" cx="710" cy="105" r="8" fill="#6e9075"/>
    </svg>
    """


def _scene_html(visual_surface: dict[str, Any]) -> str:
    image_url = visual_surface.get("image_url")
    if image_url:
        return f'<img src="{_esc(image_url)}" alt="{_esc(visual_surface.get("alt") or "Activity visual")}" />'
    scene = visual_surface.get("scene")
    if scene == "animal_cell":
        return _animal_cell_svg()
    if scene == "water_cycle":
        return _water_cycle_svg()
    if scene == "linear_graph":
        return _linear_graph_svg()
    return """
    <svg class="base-scene" viewBox="0 0 1000 625" role="img" aria-label="Abstract unlabeled activity surface" xmlns="http://www.w3.org/2000/svg">
      <rect width="1000" height="625" fill="#eef8f6"/>
      <path d="M80 460c120-170 260-240 420-210s260 12 420-80v310H80z" fill="#a5c9b2"/>
      <circle cx="380" cy="265" r="95" fill="#f1c27b"/>
      <circle cx="635" cy="330" r="120" fill="#8cb9c4"/>
    </svg>
    """


def _checks_html(checks: list[dict[str, Any]]) -> str:
    if not checks:
        return "<p>No checks have been added yet.</p>"
    cards = []
    for index, check in enumerate(checks):
        choices = check.get("choices") or []
        buttons = "".join(
            f'<button class="choice" data-check="{index}" data-correct="{str(bool(choice.get("correct"))).lower()}">{_esc(choice.get("id"))}. {_esc(choice.get("text"))}</button>'
            for choice in choices
        )
        cards.append(
            f"""
            <div class="check-card">
              <p><strong>{_esc(check.get("question"))}</strong></p>
              {buttons}
              <div class="feedback" id="feedback-{index}" aria-live="polite"></div>
            </div>
            """
        )
    return "".join(cards)


def _header(activity: dict[str, Any]) -> str:
    standards = activity.get("standards") or []
    standard_chips = "".join(
        f'<span class="chip">{_esc(std.get("code") if isinstance(std, dict) else std)}</span>'
        for std in standards[:3]
    )
    return f"""
      <div class="topbar">
        <div>
          <h1>{_esc(_activity_title(activity))}</h1>
          <div class="meta">
            <span class="chip">{_esc(activity.get("course"))}</span>
            <span class="chip">{_esc(activity.get("subject"))}</span>
            <span class="chip">{_esc(activity.get("estimated_minutes"))} min</span>
            {standard_chips}
          </div>
        </div>
        <div class="mode-actions">
          <button id="toggleLabels" type="button">Labels on</button>
          <button id="practiceMode" type="button" class="primary">Practice</button>
        </div>
      </div>
    """


def _script(activity: dict[str, Any]) -> str:
    return f"""
    <script>
      const activity = {_json_for_script(activity)};
      const checks = activity.checks || [];
      const surface = activity.visual_surface || {{}};
      const annotations = surface.annotations || [];
      const stage = document.querySelector('.visual-stage');
      const detailTitle = document.getElementById('detailTitle');
      const detailText = document.getElementById('detailText');
      const toggle = document.getElementById('toggleLabels');
      const practice = document.getElementById('practiceMode');

      function selectAnnotation(item) {{
        document.querySelectorAll('.annotation').forEach(btn => btn.classList.toggle('active', btn.dataset.id === item.id));
        if (detailTitle) detailTitle.textContent = item.label || 'Study target';
        if (detailText) detailText.textContent = item.description || '';
      }}

      document.querySelectorAll('.annotation').forEach(btn => {{
        btn.addEventListener('click', () => {{
          const item = annotations.find(a => a.id === btn.dataset.id);
          if (item) selectAnnotation(item);
        }});
      }});
      if (annotations.length) selectAnnotation(annotations[0]);

      if (toggle && stage) {{
        toggle.addEventListener('click', () => {{
          const hidden = stage.classList.toggle('labels-hidden');
          toggle.textContent = hidden ? 'Labels off' : 'Labels on';
        }});
      }}
      if (practice && stage) {{
        practice.addEventListener('click', () => {{
          stage.classList.add('labels-hidden');
          if (toggle) toggle.textContent = 'Labels off';
        }});
      }}

      document.querySelectorAll('.choice').forEach(button => {{
        button.addEventListener('click', () => {{
          const index = Number(button.dataset.check);
          const check = checks[index] || {{}};
          const feedback = check.feedback || {{}};
          const target = document.getElementById(`feedback-${{index}}`);
          const correct = button.dataset.correct === 'true';
          if (target) {{
            target.textContent = correct ? (feedback.correct || 'Correct.') : (feedback.incorrect || 'Try again.');
            target.style.color = correct ? '#2f7d4f' : '#b04435';
          }}
        }});
      }});

      const slopeInput = document.getElementById('control-slope');
      const interceptInput = document.getElementById('control-intercept');
      const equation = document.getElementById('equationReadout');
      const line = document.getElementById('modelLine');
      const pointA = document.getElementById('pointA');
      const pointB = document.getElementById('pointB');
      function updateGraph() {{
        if (!slopeInput || !interceptInput || !line) return;
        const slope = Number(slopeInput.value);
        const intercept = Number(interceptInput.value);
        const y0 = 420 - intercept * 35;
        const y1 = Math.max(45, 420 - (intercept + slope * 9) * 25);
        line.setAttribute('d', `M80 ${{y0}}L710 ${{y1}}`);
        if (pointA) pointA.setAttribute('cy', y0);
        if (pointB) pointB.setAttribute('cy', y1);
        if (equation) equation.textContent = `d = ${{slope}}t + ${{intercept}}`;
      }}
      [slopeInput, interceptInput].forEach(input => input && input.addEventListener('input', updateGraph));
      updateGraph();
    </script>
    """


def _visual_study(activity: dict[str, Any]) -> str:
    visual_surface = activity.get("visual_surface") or {}
    annotations = visual_surface.get("annotations") or []
    leader_lines = "".join(
        f'<line x1="{float(item.get("x", 0))}%" y1="{float(item.get("y", 0))}%" x2="{float(item.get("target_x", 0))}%" y2="{float(item.get("target_y", 0))}%"></line>'
        f'<circle cx="{float(item.get("target_x", 0))}%" cy="{float(item.get("target_y", 0))}%" r="5"></circle>'
        for item in annotations
    )
    labels = "".join(
        f'<button type="button" class="annotation" data-id="{_esc(item.get("id"))}" style="left:{float(item.get("x", 0))}%;top:{float(item.get("y", 0))}%">{_esc(item.get("label"))}</button>'
        for item in annotations
    )
    content = activity.get("content") or {}
    reflection = activity.get("reflection_prompt") or {}
    return f"""
      <div class="workspace">
        <div class="stage-wrap">
          <div class="visual-stage">
            {_scene_html(visual_surface)}
            <svg class="leader-layer" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">{leader_lines}</svg>
            {labels}
          </div>
        </div>
        <aside class="side-panel">
          <h2 id="detailTitle">Study target</h2>
          <p id="detailText">{_esc(content.get("objective"))}</p>
          <div class="section-title">Check</div>
          {_checks_html(activity.get("checks") or [])}
          <div class="section-title">Reflection</div>
          <p>{_esc(reflection.get("prompt"))}</p>
          <textarea aria-label="Reflection response"></textarea>
        </aside>
      </div>
    """


def _document_study(activity: dict[str, Any]) -> str:
    content = activity.get("content") or {}
    categories = content.get("annotation_categories") or []
    passage = content.get("passage") or []
    reflection = activity.get("reflection_prompt") or {}
    lines = "".join(
        f'<div class="doc-line"><span class="line-num">{idx}</span><span>{_esc(line)}</span></div>'
        for idx, line in enumerate(passage, start=1)
    )
    category_html = "".join(
        f'<div class="category"><strong>{_esc(cat.get("label"))}</strong><p>{_esc(cat.get("description"))}</p></div>'
        for cat in categories
    )
    return f"""
      <div class="workspace">
        <main class="doc-viewer">
          <p class="section-title">{_esc(content.get("document_title"))}</p>
          <h2>{_esc(content.get("objective"))}</h2>
          <p>{_esc(content.get("source_context"))}</p>
          <div>{lines}</div>
        </main>
        <aside class="side-panel">
          <h2>Study Panel</h2>
          <p>{_esc((activity.get("study_mode") or {}).get("prompt"))}</p>
          <div class="category-grid">{category_html}</div>
          <div class="section-title">Check</div>
          {_checks_html(activity.get("checks") or [])}
          <div class="section-title">Reflection</div>
          <p>{_esc(reflection.get("prompt"))}</p>
          <textarea aria-label="Reflection response"></textarea>
        </aside>
      </div>
    """


def _model_explorer(activity: dict[str, Any]) -> str:
    content = activity.get("content") or {}
    controls = content.get("controls") or []
    controls_html = "".join(
        f"""
        <label class="control">
          <strong>{_esc(control.get("label"))}</strong>
          <input id="control-{_esc(control.get("id"))}" type="range" min="{_esc(control.get("min"))}" max="{_esc(control.get("max"))}" step="{_esc(control.get("step"))}" value="{_esc(control.get("value"))}" />
        </label>
        """
        for control in controls
    )
    reflection = activity.get("reflection_prompt") or {}
    return f"""
      <div class="workspace">
        <main class="model-viewer">
          <h2>{_esc(content.get("objective"))}</h2>
          <p>{_esc(content.get("scenario"))}</p>
          <p class="section-title" id="equationReadout">{_esc(content.get("formula"))}</p>
          <div class="graph-box">{_linear_graph_svg()}</div>
          <div class="controls">{controls_html}</div>
        </main>
        <aside class="side-panel">
          <h2>Model Thinking</h2>
          <p>{_esc((activity.get("study_mode") or {}).get("prompt"))}</p>
          <div class="section-title">Check</div>
          {_checks_html(activity.get("checks") or [])}
          <div class="section-title">Reflection</div>
          <p>{_esc(reflection.get("prompt"))}</p>
          <textarea aria-label="Reflection response"></textarea>
        </aside>
      </div>
    """


def build_prebuilt_activity_html(activity: dict[str, Any]) -> str:
    """Render a prebuilt activity as standalone HTML for preview or assignment use."""
    activity_type = activity.get("activity_type")
    if activity_type == "document_study":
        body = _document_study(activity)
    elif activity_type == "model_explorer":
        body = _model_explorer(activity)
    else:
        body = _visual_study(activity)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_esc(_activity_title(activity))}</title>
  <style>{_base_css()}</style>
</head>
<body>
  <div class="activity-shell">
    {_header(activity)}
    {body}
  </div>
  {_script(activity)}
</body>
</html>
"""
