---
name: standards-system
description: "Use this skill whenever working with educational standards. Triggers include: building the three-tier hierarchy (Custom then State then National), loading pre-loaded state standards, implementing Standards Import Agent, Crosswalk Agent, querying standards by tier priority, configuring state dropdown, or handling Upload Standards lane."
---

# Three-Tier Standards System

## Tier Hierarchy

| Priority | Tier | Source | Examples |
|----------|------|--------|----------|
| 1 (highest) | Custom | Upload Standards button | Archdiocese, private school, charter |
| 2 | State | Settings dropdown (50 + DC) | Ohio Learning Standards, Texas TEKS |
| 3 (fallback) | National | Built-in, always available | Common Core, NGSS, C3 |

All 50 states + DC pre-loaded by system operator before any teacher signs up.
Teachers never upload state or national standards — they just select their state from a dropdown.

## Priority Query

```sql
SELECT s.*, f.tier, f.name as framework_name
FROM standards s
JOIN standards_frameworks f ON s.framework_id = f.framework_id
WHERE f.is_active = true AND s.subject = $1 AND s.grade_level = $2
ORDER BY f.priority ASC, s.code ASC;
```

First results = highest priority tier. Agents use the first tier with matching standards.

## Per-Procedure Standard Citations

Every lesson plan procedure phase includes specific standard codes:
```
Direct Instruction (15 min): Decimal notation using place value models
  Standard: Ohio 4.NF.6 — Use decimal notation for fractions
```

## Database Schema

```sql
CREATE TABLE standards_frameworks (
    framework_id UUID PRIMARY KEY, name VARCHAR NOT NULL,
    tier VARCHAR NOT NULL, state_code VARCHAR,
    authority VARCHAR, subjects_covered JSONB,
    grade_range VARCHAR, is_active BOOLEAN DEFAULT true,
    priority INT NOT NULL, created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE standards (
    standard_id UUID PRIMARY KEY, framework_id UUID REFERENCES standards_frameworks,
    parent_id UUID REFERENCES standards, code VARCHAR NOT NULL,
    description TEXT NOT NULL, grade_level VARCHAR, subject VARCHAR,
    domain VARCHAR, cluster VARCHAR, cognitive_level VARCHAR
);

CREATE TABLE standards_crosswalks (
    crosswalk_id UUID PRIMARY KEY, source_standard_id UUID, target_standard_id UUID,
    confidence FLOAT, mapping_type VARCHAR,
    auto_suggested BOOLEAN DEFAULT true, educator_approved BOOLEAN DEFAULT false
);
```

## State Standards JSON Format

```json
{
  "framework": {"name": "Ohio's Learning Standards", "state_code": "OH",
                "authority": "Ohio DOE", "subjects": ["Math","ELA","Science","Social Studies"]},
  "standards": [
    {"code": "OH.4.NF.5", "description": "Express fraction with denominator 10...",
     "grade": "4", "subject": "Mathematics", "domain": "Number and Operations",
     "cognitive_level": "Apply", "common_core_equivalent": "4.NF.5"}
  ]
}
```

## Key Rules

1. Custom always wins — overrides state and national for that subject
2. State fills gaps — covers subjects custom doesn't have
3. National is always fallback — never deleted
4. Standard codes appear everywhere: lesson plans, assignments, analytics, interactive activities
5. Crosswalks are suggestions — educator must approve before shown on lesson plans
6. Analytics track by active tier — mastery data uses teacher's actual framework
