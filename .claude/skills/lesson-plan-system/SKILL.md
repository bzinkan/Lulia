---
name: lesson-plan-system
description: "Use this skill whenever working with lesson plan generation, configurable templates, per-procedure standard citations, flexible duration planning (1 day to 1 year), subject-aware template selection, document rendering, admin submission, or the Weekly Planner with Accept/Modify/Start Over workflow."
---

# Lesson Plan Output System

## Flexible Duration

| Duration | Planner Output | Detail Level |
|----------|---------------|-------------|
| 1 day | Single day plan with 1-3 activities | Full daily detail |
| Custom days | Plan for specific days (Tue-Thu) | Full daily detail |
| Full week | Mon-Fri with varied templates | Full daily detail |
| Multi-week unit | 2-6 week plan with arc | Daily detail + progression |
| Semester | 18-week high-level | Unit blocks, no daily detail |
| Year | 36-40 week overview | Units, pacing, assessment weeks |

## Subject-Aware Template Selection

| Subject | Templates Planner Favors |
|---------|------------------------|
| Science | Lab activities, graphic organizers, virtual labs, video explainers |
| Math | Worksheets, task cards, Bingo, virtual store/manipulatives, math quest |
| ELA | Reading comprehension, writing prompts, choose-your-adventure, word building |
| Social Studies | Escape rooms, map explorer, timeline, historical decision sim |

Teacher can always override. Planner makes smart defaults.

## Three Response Options

- **ACCEPT** → Generate all materials. Calendar created if enabled.
- **MODIFY** → Edit inline — swap templates, change days, adjust. Re-preview.
- **START OVER** → Discard entirely. Fresh plan with different templates and content.

## Configurable Template Presets

| Preset | Fields |
|--------|--------|
| Minimal | Standards, objectives, materials, assessment |
| Standard | Standards (per-procedure), objectives, materials, 3 procedures, assessment |
| Detailed | Standard + bell ringer, closure, differentiation, vocabulary, tech |
| Full Compliance | Detailed + all accommodations, cross-curricular, homework, reflection |
| Custom | Toggle each of 20+ fields individually |

## Per-Procedure Standard Citations

```json
{
  "phase": "Direct Instruction",
  "duration_minutes": 15,
  "description": "Introduce decimal notation using place value models",
  "standards_addressed": [
    {"code": "OH.4.NF.6", "description": "Use decimal notation", "tier": "state"}
  ]
}
```

## Output Channels (All Optional)

1. Dashboard preview (always)
2. PDF / DOCX download
3. Google Doc pushed to admin's shared Drive folder
4. Visual calendar PDF
5. Google Calendar events
6. Google Classroom topic organization

## Two Dashboard Layouts

- **Subject-Grid**: Rows = subjects, Columns = days. For multi-subject teachers.
- **Period-List**: One subject, tabs for periods. Same plan for all or customize per period.
- Switchable anytime via toggle button.

## Key Rules

1. Standards are per-procedure (minimum per-day, recommended per-procedure)
2. Locked fields: Subject/Grade/Date and Standards Alignment always appear
3. Custom school templates preserve logos and formatting
4. Each plan stores its rendered state — template changes don't affect past plans
5. Rich previews generated in 5-10 seconds using Haiku (lightweight mockups)
6. Generation History checked to ensure fresh content every plan
