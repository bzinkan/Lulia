---
name: dashboard-frontend
description: "Use this skill whenever building, modifying, or styling any frontend page in the Lulia dashboard. Triggers include: creating new pages, building React components, styling with Tailwind CSS, designing layouts, building forms, implementing responsive design, or creating any UI element. Read this skill BEFORE writing any frontend code to ensure consistent, polished design across all pages."
---

# Lulia Dashboard Frontend Design System

## Stack
- **Framework**: Next.js 14+ (App Router)
- **Styling**: Tailwind CSS
- **Icons**: Lucide React
- **Charts**: Recharts (for analytics)
- **State**: React hooks (useState, useEffect, useContext)
- **API calls**: fetch to http://localhost:8000/api/v1/*

## Brand Identity

Lulia is a premium AI teaching partner. The dashboard should feel:
- **Clean and calm** — teachers are stressed, the UI should feel like a relief
- **Confident** — polished enough that teachers trust the system's output
- **Fast** — minimal visual clutter, clear hierarchy, quick to scan
- **Warm** — not cold/corporate, approachable and encouraging

## Color Palette

```
/* Primary */
--lulia-indigo: #4F46E5      /* Primary buttons, active states, links */
--lulia-indigo-light: #818CF8 /* Hover states, secondary accents */
--lulia-indigo-dark: #3730A3  /* Active/pressed states */
--lulia-indigo-50: #EEF2FF    /* Light background tints */

/* Semantic */
--lulia-green: #059669        /* Success, approved, graded, healthy */
--lulia-green-50: #ECFDF5     /* Success backgrounds */
--lulia-amber: #D97706        /* Warning, pending, needs attention */
--lulia-amber-50: #FFFBEB     /* Warning backgrounds */
--lulia-red: #DC2626          /* Error, rejected, overdue */
--lulia-red-50: #FEF2F2       /* Error backgrounds */
--lulia-blue: #2563EB         /* Info, links, interactive elements */
--lulia-blue-50: #EFF6FF      /* Info backgrounds */

/* Neutrals */
--lulia-gray-50: #F9FAFB      /* Page background */
--lulia-gray-100: #F3F4F6     /* Card backgrounds, table alternating rows */
--lulia-gray-200: #E5E7EB     /* Borders, dividers */
--lulia-gray-400: #9CA3AF     /* Placeholder text, disabled */
--lulia-gray-600: #4B5563     /* Secondary text */
--lulia-gray-800: #1F2937     /* Primary text */
--lulia-gray-900: #111827     /* Headings */
```

## Typography

```
/* Font: Inter (import from Google Fonts) */
Headings: font-semibold
  h1: text-2xl (page titles)
  h2: text-xl (section titles)
  h3: text-lg font-medium (subsection titles)
Body: text-sm text-gray-600 (default)
Small: text-xs text-gray-400 (metadata, timestamps)
```

## Layout Structure

```
┌─────────────────────────────────────────────────┐
│  Top Bar (h-16, white, border-b)                │
│  Logo | Search | Credit Meter | User Menu       │
├────────┬────────────────────────────────────────┤
│        │                                        │
│ Side   │  Main Content Area                     │
│ bar    │  (p-6, bg-gray-50, overflow-y-auto)    │
│ (w-64) │                                        │
│        │  ┌──────────────────────────────────┐  │
│ Nav    │  │  Page Header                     │  │
│ links  │  │  Title + Description + Actions   │  │
│        │  └──────────────────────────────────┘  │
│ white  │                                        │
│ bg     │  ┌──────────────────────────────────┐  │
│        │  │  Content Cards / Tables          │  │
│        │  │                                  │  │
│        │  └──────────────────────────────────┘  │
│        │                                        │
├────────┴────────────────────────────────────────┤
│  (No footer — sidebar + top bar is enough)      │
└─────────────────────────────────────────────────┘
```

## Sidebar Navigation

```jsx
const navItems = [
  { label: "Dashboard", icon: Home, href: "/" },
  { label: "Weekly Planner", icon: Calendar, href: "/planner" },
  { label: "New Assignment", icon: PlusCircle, href: "/assignments/new" },
  { label: "Assignments", icon: FileText, href: "/assignments" },
  { label: "Content Library", icon: Upload, href: "/library" },
  { label: "Standards", icon: BookOpen, href: "/standards" },
  { label: "Analytics", icon: BarChart3, href: "/analytics" },
  { label: "Interactive Studio", icon: Gamepad2, href: "/interactive" },
  { label: "Design Studio", icon: Palette, href: "/design" },
  { label: "Settings", icon: Settings, href: "/settings" },
];
```

Active state: `bg-indigo-50 text-indigo-700 border-r-2 border-indigo-700`
Hover: `bg-gray-50`
Default: `text-gray-600`

## Component Patterns

### Cards
```jsx
<div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
  {/* Card content */}
</div>
```
Always use: `rounded-xl`, `shadow-sm`, `border border-gray-200`, white background.
Never use: harsh shadows, square corners, colored card backgrounds (except for status cards).

### Status Cards (colored)
```jsx
// Success
<div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
  <div className="flex items-center gap-2 text-emerald-700">
    <CheckCircle className="w-5 h-5" />
    <span className="font-medium">Approved</span>
  </div>
</div>

// Warning
<div className="bg-amber-50 border border-amber-200 rounded-xl p-4">

// Error
<div className="bg-red-50 border border-red-200 rounded-xl p-4">

// Info
<div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
```

### Buttons
```jsx
// Primary
<button className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium text-sm transition-colors">
  Generate Assignment
</button>

// Secondary
<button className="bg-white hover:bg-gray-50 text-gray-700 border border-gray-300 px-4 py-2 rounded-lg font-medium text-sm transition-colors">
  Cancel
</button>

// Danger
<button className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg font-medium text-sm transition-colors">
  Delete
</button>

// Ghost
<button className="text-gray-500 hover:text-gray-700 hover:bg-gray-100 px-3 py-2 rounded-lg text-sm transition-colors">
  Edit
</button>
```
All buttons: `rounded-lg`, `text-sm`, `font-medium`, `transition-colors`.

### Form Inputs
```jsx
<label className="block text-sm font-medium text-gray-700 mb-1">Subject</label>
<select className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none">
  <option>Mathematics</option>
</select>
```

### Tables
```jsx
<div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
  <table className="w-full text-sm">
    <thead className="bg-gray-50 border-b border-gray-200">
      <tr>
        <th className="text-left px-4 py-3 font-medium text-gray-600">Title</th>
      </tr>
    </thead>
    <tbody className="divide-y divide-gray-100">
      <tr className="hover:bg-gray-50 transition-colors">
        <td className="px-4 py-3 text-gray-800">Fractions Worksheet</td>
      </tr>
    </tbody>
  </table>
</div>
```

### Page Header Pattern
```jsx
<div className="flex items-center justify-between mb-6">
  <div>
    <h1 className="text-2xl font-semibold text-gray-900">Assignments</h1>
    <p className="text-sm text-gray-500 mt-1">View and manage all generated assignments</p>
  </div>
  <button className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium text-sm">
    + New Assignment
  </button>
</div>
```

### Empty States
```jsx
<div className="text-center py-12">
  <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
  <h3 className="text-lg font-medium text-gray-900 mb-1">No assignments yet</h3>
  <p className="text-sm text-gray-500 mb-4">Generate your first assignment to get started</p>
  <button className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium text-sm">
    Generate Assignment
  </button>
</div>
```

### Loading States
```jsx
// Skeleton loading
<div className="animate-pulse">
  <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
  <div className="h-4 bg-gray-200 rounded w-1/2"></div>
</div>

// Spinner for generation
<div className="flex flex-col items-center py-12">
  <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mb-4"></div>
  <p className="text-sm text-gray-600">Generating your assignment...</p>
  <p className="text-xs text-gray-400 mt-1">This usually takes 15-30 seconds</p>
</div>
```

### Credit Meter (Top Bar)
```jsx
<div className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-lg">
  <Zap className="w-4 h-4 text-indigo-600" />
  <span className="text-sm font-medium text-gray-700">87 credits</span>
</div>
```

### Upload Zone
```jsx
<div className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-indigo-400 hover:bg-indigo-50/50 transition-colors cursor-pointer">
  <Upload className="w-8 h-8 text-gray-400 mx-auto mb-3" />
  <p className="text-sm font-medium text-gray-700">Drop files here or click to browse</p>
  <p className="text-xs text-gray-400 mt-1">PDF, DOCX, or TXT up to 50MB</p>
</div>
```

## Three Upload Buttons (Content Library)
```jsx
<div className="grid grid-cols-3 gap-4">
  <button className="flex flex-col items-center gap-3 p-6 bg-white rounded-xl border-2 border-gray-200 hover:border-indigo-400 hover:bg-indigo-50/50 transition-all">
    <BookOpen className="w-8 h-8 text-indigo-600" />
    <span className="font-medium text-gray-800">Upload Standards</span>
    <span className="text-xs text-gray-400">Custom school standards</span>
  </button>
  {/* Same pattern for Curriculum and Materials */}
</div>
```

## Responsive Breakpoints
- **Desktop**: Full sidebar + content (default)
- **Tablet (md)**: Collapsible sidebar
- **Mobile (sm)**: Bottom navigation bar instead of sidebar, full-width content

## Key Design Rules

1. **White cards on gray-50 background** — always. Never gray cards on white background.
2. **Rounded-xl for cards, rounded-lg for buttons and inputs** — consistent rounding.
3. **shadow-sm only** — never heavy shadows. The UI should feel light and airy.
4. **Indigo as primary color** — not blue, not purple. Indigo (#4F46E5).
5. **Text hierarchy**: gray-900 for headings, gray-600 for body, gray-400 for metadata.
6. **Always show loading states** — never leave the user staring at a blank screen.
7. **Empty states with illustration and CTA** — never just "No data."
8. **Hover transitions on everything interactive** — buttons, rows, cards. Use transition-colors.
9. **Inter font** — import from Google Fonts. Clean, modern, highly readable.
10. **No excessive padding** — p-6 for cards, p-4 for compact elements, px-4 py-3 for table cells.
