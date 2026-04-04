---
name: dashboard-frontend
description: "Use this skill whenever building, modifying, or styling any frontend page in the Lulia dashboard. Triggers include: creating new pages, building React components, styling with Tailwind CSS, designing layouts, building forms, implementing responsive design, or creating any UI element. Read this skill BEFORE writing any frontend code."
---

# Lulia Dashboard Frontend Design System

## Stack
- **Framework**: Next.js 14+ (App Router)
- **Styling**: Tailwind CSS + custom CSS variables
- **Fonts**: DM Serif Display (headings), DM Sans (body)
- **Icons**: Lucide React
- **Charts**: Recharts (amber/orange color scheme)
- **State**: React hooks (useState, useEffect, useContext)
- **API calls**: fetch to http://localhost:8000/api/v1/*

## Brand Identity

Lulia's design is warm, editorial, and human. It should feel like opening a beautifully designed planner — not like logging into a tech tool. The aesthetic is inspired by editorial dashboards with warm tones, serif headings, generous whitespace, and personality.

**It should feel:** Warm, inviting, calm, confident, personal
**It should NOT feel:** Cold, corporate, generic SaaS, cluttered, tech-heavy
**It should NOT look like:** MagicSchool (purple), Canva (blue/white), generic AI tools

## Color Palette

```css
:root {
  /* Outer background — the warm tinted layer behind content */
  --lulia-bg-outer: #F5DEC3;           /* Warm peach */
  --lulia-bg-outer-light: #FBE8D3;     /* Lighter peach for variants */

  /* Content background — where cards and content sit */
  --lulia-bg-content: #FEF9F2;         /* Warm cream */
  --lulia-bg-sidebar: #FEF7EE;         /* Sidebar cream */
  --lulia-bg-card: #FFFFFF;            /* White cards */

  /* Primary accent — orange/amber */
  --lulia-primary: #F97316;            /* Primary buttons, CTA, active states */
  --lulia-primary-light: #FB923C;      /* Hover states */
  --lulia-primary-lighter: #FDBA74;    /* Subtle accents */
  --lulia-primary-lightest: #FED7AA;   /* Tinted backgrounds */
  --lulia-primary-bg: #FFF7ED;         /* Very light orange background */
  --lulia-primary-dark: #EA580C;       /* Pressed/active */
  --lulia-primary-darkest: #9A3412;    /* Text on light orange */

  /* Text colors */
  --lulia-text-primary: #1C1917;       /* Headings, primary text */
  --lulia-text-secondary: #78716C;     /* Body text, descriptions */
  --lulia-text-muted: #A8A29E;         /* Metadata, labels, timestamps */
  --lulia-text-sidebar: #B8976A;       /* Inactive sidebar items */
  --lulia-text-sidebar-active: #78350F; /* Active sidebar item */

  /* Semantic colors */
  --lulia-green: #22C55E;             /* Success, complete, graded */
  --lulia-green-bg: #DCFCE7;          /* Green card backgrounds */
  --lulia-green-text: #16A34A;        /* Green text */
  --lulia-red: #EF4444;              /* Error, overdue, needs attention */
  --lulia-red-bg: #FEF2F2;           /* Red backgrounds */
  --lulia-amber: #D97706;            /* Warning, pending */
  --lulia-amber-bg: #FEF3C7;         /* Amber backgrounds */
  --lulia-blue: #2563EB;             /* Info, interactive, links */
  --lulia-blue-bg: #DBEAFE;          /* Blue backgrounds */
  --lulia-pink: #DB2777;             /* Games, fun elements */
  --lulia-pink-bg: #FCE7F3;          /* Pink backgrounds */
  --lulia-teal: #5EAAA0;             /* Accent (used for "View All" cards) */

  /* Borders */
  --lulia-border: #E7E5E4;           /* Default card borders */
  --lulia-border-light: #F5F5F4;     /* Subtle dividers */
}
```

## Typography

```css
/* Import both fonts */
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;500;600&display=swap');

/* DM Serif Display — headings only */
h1 { font-family: 'DM Serif Display', serif; font-size: 22px; color: var(--lulia-text-primary); }
h2 { font-family: 'DM Serif Display', serif; font-size: 18px; color: var(--lulia-text-primary); }
h3 { font-family: 'DM Serif Display', serif; font-size: 14px; color: var(--lulia-text-primary); }

/* DM Sans — everything else */
body { font-family: 'DM Sans', sans-serif; font-size: 14px; color: var(--lulia-text-secondary); }
```

Use DM Serif Display ONLY for page titles, section headings, and card titles. Everything else uses DM Sans. The contrast between serif headings and sans-serif body is what gives the editorial feel.

## Layout Structure

```
┌──────────────────────────────────────────────────────┐
│              Warm peach outer background               │
│  ┌──────┬───────────────────────────────────────────┐ │
│  │      │                                           │ │
│  │ Side │  Content area (warm cream #FEF9F2)        │ │
│  │ bar  │                                           │ │
│  │      │  ┌─ Top Row ────────────────────────────┐ │ │
│  │ Cream│  │ "Dashboard" (DM Serif)   [CTA Card]  │ │ │
│  │ bg   │  │  Stats with colored dots              │ │ │
│  │      │  └──────────────────────────────────────┘ │ │
│  │Avatar│                                           │ │
│  │Name  │  ┌─ Mid Row ───────────┬────────────────┐ │ │
│  │Role  │  │ Activity Chart      │ Top Standards   │ │ │
│  │      │  │ (line chart, amber) │ (list + %)     │ │ │
│  │ Nav  │  └────────────────────┴────────────────┘ │ │
│  │items │                                           │ │
│  │      │  ┌─ Bottom Row ────────────────────────┐  │ │
│  │      │  │ Materials: [W] [T] [Q] [G] [All]    │  │ │
│  │      │  └─────────────────────────────────────┘  │ │
│  └──────┴───────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

The warm peach outer background is KEY. This is what makes it feel different from every other dashboard. Content cards sit on cream, not white-on-gray like every SaaS tool.

## Sidebar

```jsx
<aside className="w-20 bg-[#FEF7EE] flex flex-col items-center py-4 gap-2 rounded-l-2xl">
  {/* Avatar */}
  <div className="w-10 h-10 rounded-full bg-[#E8985A] flex items-center justify-center text-white font-semibold text-sm">
    {initials}
  </div>
  <p className="text-[9px] font-semibold text-[#78350F]">{name}</p>
  <p className="text-[7px] text-[#A8742B]">{role}</p>

  {/* Nav items — text only, no icons needed */}
  <nav className="mt-3 flex flex-col gap-1 w-full">
    {navItems.map(item => (
      <button className={`text-[9px] py-1 text-center ${
        item.active
          ? 'font-semibold text-[#78350F]'
          : 'text-[#B8976A]'
      }`}>
        {item.label}
        {item.badge && <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#F97316] ml-1" />}
      </button>
    ))}
  </nav>
</aside>
```

The sidebar uses TEXT navigation, not icons. This matches the editorial/planner feel. Active item is bold with a colored dot badge.

## Component Patterns

### CTA Card (Top Right — "Plan Your Week")
```jsx
<div className="relative overflow-hidden rounded-[14px] bg-[#F97316] p-3 w-[140px]">
  {/* Decorative circles */}
  <div className="absolute -top-2 -right-2 w-14 h-14 rounded-full bg-[#FB923C]" />
  <div className="absolute bottom-1 right-5 w-7 h-7 rounded-full bg-[#FDBA74]" />
  <div className="absolute top-2 right-10 w-5 h-5 rounded-full bg-[#FED7AA]" />
  <p className="relative z-10 text-white font-bold text-sm">Plan Your Week</p>
  <p className="relative z-10 text-[#FED7AA] text-xs">Auto-pilot ready</p>
</div>
```

The decorative circles inside the CTA card add personality. Use this pattern for promotional/action cards throughout the dashboard.

### Stats Row (With Colored Dots)
```jsx
<div className="flex gap-6 mt-2">
  <div>
    <p className="text-[8px] text-[#A8A29E] flex items-center gap-1">
      <span className="w-1.5 h-1.5 rounded-full bg-[#22C55E]" />
      Credits
    </p>
    <p className="text-xl font-bold text-[#1C1917]">87</p>
  </div>
  {/* Repeat for each stat */}
</div>
```

### Content Cards (White on Cream)
```jsx
<div className="bg-white rounded-[14px] p-3">
  {/* Card content */}
</div>
```
Always `rounded-[14px]`. No borders unless needed for separation. No shadows. White cards on cream background provide enough contrast.

### Activity Chart
Use Recharts with an Area chart. Line color: `#F97316`. Fill: `#F97316` at 15% opacity. Single data point callout at the peak.

### Material Category Cards (Bottom Row)
```jsx
<div className="bg-white rounded-xl p-2 text-center flex flex-col items-center gap-1">
  <div className="w-7 h-7 rounded-lg bg-[#DCFCE7] flex items-center justify-center text-[#16A34A] text-xs font-bold">
    W
  </div>
  <p className="text-[8px] font-semibold text-[#44403C]">Worksheets</p>
  <p className="text-sm font-bold text-[#16A34A]">+3</p>
</div>
```

Each material type has its own icon color:
- Worksheets: green (#16A34A on #DCFCE7)
- Task Cards: amber (#D97706 on #FEF3C7)
- Quizzes/Interactive: blue (#2563EB on #DBEAFE)
- Games: pink (#DB2777 on #FCE7F3)
- Videos: orange (#EA580C on #FFF7ED)

### "View All" Accent Card
```jsx
<div className="bg-[#5EAAA0] rounded-xl p-2 text-center flex flex-col items-center justify-center text-white">
  <p className="text-[10px] font-bold">All<br/>Materials</p>
  <div className="w-5 h-5 rounded-full bg-white/20 flex items-center justify-center mt-1">›</div>
</div>
```

### Standard Badges
```jsx
<span className="text-[7px] px-1.5 py-0.5 rounded bg-[#FFF7ED] text-[#9A3412] border border-[#FDBA74]">
  4.NF.1
</span>
```

### Buttons
```jsx
// Primary
<button className="bg-[#F97316] hover:bg-[#EA580C] text-white px-4 py-2 rounded-xl font-medium text-sm transition-colors">
  Generate Assignment
</button>

// Secondary
<button className="bg-white hover:bg-[#FFF7ED] text-[#78350F] border border-[#E7E5E4] px-4 py-2 rounded-xl font-medium text-sm transition-colors">
  Cancel
</button>

// Ghost / Link
<button className="text-[#F97316] hover:text-[#EA580C] text-sm font-medium">
  View more ›
</button>
```

### Form Inputs
```jsx
<label className="block text-xs font-medium text-[#78350F] mb-1">Subject</label>
<select className="w-full border border-[#E7E5E4] bg-white rounded-xl px-3 py-2 text-sm text-[#1C1917] focus:ring-2 focus:ring-[#FDBA74] focus:border-[#F97316] outline-none">
  <option>Mathematics</option>
</select>
```

### Empty States
```jsx
<div className="text-center py-12">
  <div className="w-12 h-12 rounded-2xl bg-[#FFF7ED] flex items-center justify-center mx-auto mb-4">
    <FileText className="w-6 h-6 text-[#FDBA74]" />
  </div>
  <h3 className="text-lg text-[#1C1917] font-['DM_Serif_Display'] mb-1">No assignments yet</h3>
  <p className="text-sm text-[#A8A29E] mb-4">Generate your first assignment to get started</p>
  <button className="bg-[#F97316] hover:bg-[#EA580C] text-white px-4 py-2 rounded-xl font-medium text-sm">
    Generate Assignment
  </button>
</div>
```

### Loading States
```jsx
// Generation spinner
<div className="flex flex-col items-center py-12">
  <div className="w-8 h-8 border-2 border-[#F97316] border-t-transparent rounded-full animate-spin mb-4" />
  <p className="text-sm text-[#78716C]">Generating your assignment...</p>
  <p className="text-xs text-[#A8A29E] mt-1">This usually takes 15-30 seconds</p>
</div>
```

### Upload Zone
```jsx
<div className="border-2 border-dashed border-[#FDBA74] rounded-2xl p-8 text-center hover:border-[#F97316] hover:bg-[#FFF7ED] transition-colors cursor-pointer">
  <Upload className="w-8 h-8 text-[#FDBA74] mx-auto mb-3" />
  <p className="text-sm font-medium text-[#78350F]">Drop files here or click to browse</p>
  <p className="text-xs text-[#A8A29E] mt-1">PDF, DOCX, or TXT up to 50MB</p>
</div>
```

### Tables
```jsx
<div className="bg-white rounded-[14px] overflow-hidden">
  <table className="w-full text-sm">
    <thead>
      <tr className="border-b border-[#F5F5F4]">
        <th className="text-left px-4 py-3 text-[8px] uppercase tracking-wider text-[#A8A29E] font-medium">Title</th>
      </tr>
    </thead>
    <tbody className="divide-y divide-[#F5F5F4]">
      <tr className="hover:bg-[#FFF7ED] transition-colors">
        <td className="px-4 py-3 text-[#1C1917]">Fractions Worksheet</td>
      </tr>
    </tbody>
  </table>
</div>
```

## Responsive Breakpoints
- **Desktop**: Full sidebar + content (default)
- **Tablet (md)**: Sidebar collapses to icon-only (just avatar + initials per nav item)
- **Mobile (sm)**: Bottom tab bar replaces sidebar, full-width content, peach background still visible as top strip

## Key Design Rules

1. **Warm peach outer background (#F5DEC3)** — This is the signature. Content sits on cream (#FEF9F2), cards are white. Three layers of warmth.
2. **DM Serif Display for headings ONLY** — Never use serif for body text, labels, or buttons. The serif/sans contrast IS the design.
3. **Rounded-[14px] for all cards** — Generous rounding. Not rounded-lg (8px) — that's too subtle. 14px minimum.
4. **No shadows** — The warm background layers provide depth. Shadows would make it feel like generic SaaS.
5. **Orange (#F97316) as primary accent** — Not blue, not purple, not green. Orange is warm and completely different from competitors.
6. **Colored dots for status** — Small colored circles (5px) next to stat labels, like the reference design.
7. **Text-based sidebar navigation** — No icon-heavy sidebar. Just text labels with a dot badge for active items.
8. **Decorative circles on CTA cards** — Adds personality and playfulness without illustrations.
9. **Category cards with individual colors** — Each material type has its own color. The last card is always the teal accent "View All" card.
10. **"View more ›" links** — Use the right-pointing angle bracket, not arrows or icons. Orange color.
11. **Line charts, not bar charts** — For activity/analytics. Orange line with subtle fill. Single callout point.
12. **No uppercase except tiny labels** — Only 8px metadata labels use uppercase + letter-spacing. Everything else is sentence case.
