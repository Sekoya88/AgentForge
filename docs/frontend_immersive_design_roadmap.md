# 🌌 AgentForge — Immersive Frontend Design Roadmap

> **Vision**: Transform AgentForge from a functional platform into an **experiential, gallery-grade interface** that feels like stepping into a living neural network. Every pixel breathes. Every interaction rewards. The platform should evoke the feeling of controlling something powerful, dangerous, and beautiful — like piloting an AI spaceship.

> **Design DNA**: Experimental lab aesthetic × dark glassmorphism × generative art × cinematic motion. Inspired by 21st.dev Entropy, Vercel's design language, Linear's precision, and Midjourney's sense of wonder.

---

## Table of Contents

1. [Phase 0 — Design System Foundation](#phase-0--design-system-foundation)
2. [Phase 1 — Landing Page: The First Breath](#phase-1--landing-page-the-first-breath)
3. [Phase 2 — Agent Builder: The Forge Experience](#phase-2--agent-builder-the-forge-experience)
4. [Phase 3 — Real-Time Execution: Living Flow](#phase-3--real-time-execution-living-flow)
5. [Phase 4 — Chat & Conversation: The Dialogue Canvas](#phase-4--chat--conversation-the-dialogue-canvas)
6. [Phase 5 — Dashboard & Inner Pages: Mission Control](#phase-5--dashboard--inner-pages-mission-control)
7. [Phase 6 — Micro-Interactions & Polish Layer](#phase-6--micro-interactions--polish-layer)
8. [Component Inventory & Gap Analysis](#component-inventory--gap-analysis)
9. [Technical Architecture Notes](#technical-architecture-notes)

---

## Phase 0 — Design System Foundation

> **Priority**: 🔴 CRITICAL — must land first, everything depends on it
> **Effort**: ~2-3 days
> **Files**: `globals.css`, new `src/components/fx/` directory, `layout.tsx`

### 0.1 — Extended Design Tokens

The current token system (`--color-af-*`) is solid but needs **depth layers** and **glow tokens** for the immersive feel.

```css
/* New tokens to add to @theme */
--af-glow-primary: 0 0 30px rgba(195, 192, 255, 0.15);
--af-glow-intense: 0 0 60px rgba(124, 58, 237, 0.25), 0 0 120px rgba(124, 58, 237, 0.08);
--af-glow-teal: 0 0 40px rgba(45, 212, 191, 0.2);
--af-glow-danger: 0 0 30px rgba(255, 100, 100, 0.2);

/* Glassmorphism layers */
--af-glass-subtle: rgba(18, 18, 30, 0.4);
--af-glass-medium: rgba(18, 18, 30, 0.65);
--af-glass-heavy: rgba(18, 18, 30, 0.85);
--af-glass-border: rgba(195, 192, 255, 0.08);
--af-glass-border-hover: rgba(195, 192, 255, 0.18);
--af-glass-blur: 20px;

/* Depth elevation scale (replaces static shadows) */
--af-elevation-1: 0 2px 8px rgba(0,0,0,0.3), 0 0 1px rgba(195,192,255,0.05);
--af-elevation-2: 0 8px 32px rgba(0,0,0,0.4), 0 0 1px rgba(195,192,255,0.08);
--af-elevation-3: 0 24px 80px rgba(0,0,0,0.5), 0 0 1px rgba(195,192,255,0.12);

/* Motion curves — more expressive */
--af-spring: cubic-bezier(0.175, 0.885, 0.32, 1.275);
--af-smooth: cubic-bezier(0.25, 0.46, 0.45, 0.94);
--af-snap: cubic-bezier(0.68, -0.55, 0.265, 1.55);
```

### 0.2 — Glassmorphism Primitive: `af-glass`

Replace the current `af-card` utility with a layered glassmorphism system:

| Class | Use case | Visual |
|---|---|---|
| `af-glass` | Default panels (sidebar, modals) | Subtle blur + translucent bg |
| `af-glass-elevated` | Floating elements (tooltips, popups) | Stronger blur + glow border |
| `af-glass-interactive` | Cards, buttons (hover = glow intensifies) | Border glow on hover |
| `af-glass-void` | Background sections | Near-transparent, max blur |

### 0.3 — Fractal Background Canvas (★ Signature Element)

> **Replaces**: Current `AsciiField.tsx` (keep as fallback for reduced-motion)

Create `src/components/fx/FractalCanvas.tsx` — a full-screen WebGL/Canvas fractal that:

- Renders a **recursive fractal pattern** (Julia set / Mandelbrot variant) in the brand color palette (indigo → violet → teal)
- **Reacts to scroll position**: the fractal zooms / morphs as the user scrolls down
- Uses `requestAnimationFrame` at 30fps with `will-change: transform`
- Has subtle **mouse parallax** (shifts 2-3px based on cursor position)
- Fades opacity based on content density (full opacity on landing, 20% on inner pages)
- Falls back to the existing `AsciiField` for `prefers-reduced-motion`

Implementation approach:
```
Canvas → Fragment shader (GLSL via 2D context, no heavy WebGL library)
OR
Canvas 2D → Iterative Julia set with color mapping
```

> [!TIP]
> The fractal should feel like looking into the "neural substrate" of the platform. Think: organic, alive, slowly breathing.

### 0.4 — Motion System Upgrade

Current state: basic `af-fade-in` and `af-stagger-in`. Needs:

| Animation | Trigger | Implementation |
|---|---|---|
| `af-reveal` | Element enters viewport | `IntersectionObserver` + CSS `@keyframes` |
| `af-parallax-float` | Scroll position | `transform: translateY(calc(var(--scroll-progress) * -20px))` |
| `af-morph-in` | Page transition | Scale 0.95 → 1 + blur 4px → 0 + opacity 0 → 1 |
| `af-glow-pulse` | Status indicator | Subtle shadow oscillation |
| `af-edge-flow` | Graph edge during execution | Dashed stroke animation |
| `af-shimmer` | Loading skeleton | Moving gradient highlight |

New hook: `useScrollProgress()` — returns normalized `0..1` scroll position for scroll-linked animations.

### 0.5 — Typography Polish

Current fonts (Space Grotesk + JetBrains Mono) are strong. Enhancements:

- Add **variable font weight** for Space Grotesk (currently only bold/regular)
- Introduce a **display weight** for hero sections: `font-weight: 800; letter-spacing: -0.04em`
- Section kickers: animate underline on scroll-in
- Code blocks: add line numbers + syntax-aware highlight glow

---

## Phase 1 — Landing Page: The First Breath

> **Priority**: 🔴 HIGH — first impression, brand statement
> **Effort**: ~3-4 days
> **Files**: `src/app/page.tsx`, `globals.css`, new FX components

### Current State Analysis

The landing page ([page.tsx](file:///Users/nicolas/Documents/workspace/AgentForge/frontend/src/app/page.tsx)) has good bones:
- ✅ Hero section with search bar
- ✅ Advantages accordion
- ✅ Core features grid
- ✅ Benchmark bars
- ✅ Products grid
- ✅ CTA footer

**What's missing**: scroll-driven life, visual depth, immersive feeling, spatial narrative.

### 1.1 — Hero: Full-Screen Fractal Portal

```
┌────────────────────────────────────────────────────┐
│  [FractalCanvas at 100% opacity, slowly morphing]  │
│                                                    │
│         ╭──────────────────────────╮               │
│         │  Ask AgentForge anything │  ← floating   │
│         ╰──────────────────────────╯    glass bar   │
│                                                    │
│        Build, red-team &                           │
│        ship *secure* agents                        │
│        ↕ subtle text parallax                      │
│                                                    │
│  [Get Started]  [Open Agents]                      │
│                                                    │
│  ━━━ Scroll to explore ━━━  ← animated arrow      │
└────────────────────────────────────────────────────┘
```

Changes:
- Search bar: **glassmorphic floating** with subtle `box-shadow` glow on focus
- H1 text: add `af-reveal` on load with staggered word reveal (each word fades in 100ms apart)
- CTA buttons: replace flat buttons with **glass buttons with inner light** — hover reveals a gradient sweep
- Scroll indicator: animate with a breathing opacity cycle + chevron bounce
- Background fractal: at maximum zoom/detail here, creating a sense of "entering" the system

### 1.2 — Advantages Section: Bento Grid Reveal

Replace the current accordion with a **bento-grid layout** that reveals on scroll:

```
┌──────────────────┬──────────────┐
│                  │   Security   │
│   Orchestration  │  ┌─────────┐ │
│   (large card)   │  │ metrics │ │
│   with animated  │  │  pulse  │ │
│   graph preview  │  └─────────┘ │
├─────────┬────────┼──────────────┤
│ Fine-   │ HITL   │  Sandboxes   │
│ tuning  │ live   │  with code   │
│         │ demo   │  preview     │
└─────────┴────────┴──────────────┘
```

Each card:
- Enters with `af-reveal` (slides up + fades in) when 20% visible
- Has a glassmorphic background with border glow on hover
- Contains a **mini animated illustration** (not placeholder gradient blocks):
  - Orchestration: tiny animated node graph with pulse edges
  - Security: circular score gauge with sweep animation
  - Fine-tuning: GPU utilization meter
  - HITL: pulsing human approval icon

### 1.3 — Benchmarks Section: Animated Progress Rings

Replace flat progress bars with **circular gauge rings** that animate when they scroll into view:

```
 ╭───╮  ╭───╮  ╭───╮  ╭───╮
 │94%│  │1.2│  │99 │  │$2 │
 │   │  │ s │  │.2%│  │.40│
 ╰───╯  ╰───╯  ╰───╯  ╰───╯
Security Latency  Reliability Cost
```

Each ring:
- SVG `<circle>` with `stroke-dasharray` animation
- Glow halo appears as ring fills
- Number counts up from 0 with easing

### 1.4 — Products Section: Hover-Reveal Cards

Replace static gradient boxes with **interactive preview cards**:
- Default state: glass card with icon + title
- Hover: card "opens" — scales slightly, reveals a preview illustration or mini-demo
- Each card has a unique animated accent (particles, code stream, shield pulse)

### 1.5 — CTA Section: Fractal Convergence

The final CTA should feel like the fractal "converges" here:
- Fractal canvas zooms into a single bright point behind the CTA
- "START NOW" button with **glow breathing** animation
- Particle drift effect around the button

### 1.6 — Footer: Glass Bar

Current footer is functional but flat. Enhance:
- Full-width glassmorphic strip
- Subtle gradient line separator at top
- Links animate color on hover with a 200ms transition
- Add subtle version badge: `v0.1.0-research`

---

## Phase 2 — Agent Builder: The Forge Experience

> **Priority**: 🔴 HIGH — core product differentiator
> **Effort**: ~4-5 days
> **Files**: `src/app/forge/page.tsx`, `src/app/agents/[id]/builder/page.tsx`, `src/components/builder/*`

### Current State

The Forge page (55KB) is feature-rich but visually utilitarian:
- ✅ Sidebar with conversations
- ✅ Tab system
- ✅ Slash command palette
- ✅ Design mode for AI-generated agents
- ✅ Streaming with waveform indicators

The Builder page uses `@xyflow/react` for the visual graph editor.

**What's missing**: the builder should feel like a **laboratory workbench** — tactile, precise, dramatic.

### 2.1 — Graph Canvas: Neon Neural Network

Transform the ReactFlow graph into a living neural network:

#### Node Design
```
    ╭──────────────────────────╮
    │ ◉ LLM                   │ ← type-colored left border glow
    │                          │
    │  🧠 classify             │ ← icon + label
    │  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─   │
    │  gpt-4o · temp 0.7      │ ← config preview (condensed)
    │                          │
    │  ● ─── ● ─── ●          │ ← connection handles with glow
    ╰──────────────────────────╯
```

- Each node type has a **unique glow color** (use existing `--af-node-*` palette)
- Selected node gets a **pulsing glow border** + shadow halo
- Nodes animate in with `af-morph-in` when added
- Drag creates a **trailing ghost** (0.3 opacity shadow follows)

#### Edge Design
- Edges: **animated dashed gradient** stroke (indigo → teal)
- On hover: edge thickens + label appears (condition text)
- During execution: **particle flow animation** along the edge (dots travel from source to target)
- Conditional edges: small diamond indicator at decision point

#### Canvas Background
- Replace default dots with a subtle **hexagonal grid** (evokes circuit board / neural mesh)
- Grid lines glow softly in brand indigo
- Add a vignette effect (edges of canvas darken) for focus

### 2.2 — Inspector Panel: Glassmorphic Sidebar

Current [InspectorPanel.tsx](file:///Users/nicolas/Documents/workspace/AgentForge/frontend/src/components/builder/InspectorPanel.tsx) is a clean form. Upgrade to:

- **Glassmorphic container** with `af-glass-elevated`
- **Panel slides in** from right with spring animation
- Node type header: colored gradient strip at top
- Form fields: **floating labels** that animate up when focused
- System prompt textarea: add a **character count ring** (circular progress around the word count)
- Temperature slider: replace number input with a **visual slider** with gradient track (blue-cold → red-hot)

### 2.3 — Design Mode: AI Architect Experience

The ForgeDesignMode component gets an immersive upgrade:

- Prompt input: **full-width glassmorphic card** with animated border while generating
- During generation: the card background shows a **fractal morph animation** (processing)
- Node preview: render as **miniature animated graph** (not just chips) using a simplified ReactFlow canvas
- "Create & Open Builder" button: **dramatic glow pulse** + scale animation

### 2.4 — Conversation Sidebar

- Cards: glassmorphic with type-colored left accent
- Active conversation: **neon glow indicator** instead of simple border
- Collapse animation: sidebar smoothly scales to icon-only with spring easing
- Add **conversation search** with filter highlight

---

## Phase 3 — Real-Time Execution: Living Flow

> **Priority**: 🟠 HIGH — the "wow" moment of the platform
> **Effort**: ~3-4 days
> **Files**: `src/components/execution/*`, `src/components/agent/*`, `src/hooks/useAgentActivity.ts`

### 3.1 — Execution Timeline: Cinematic Replay

Replace the current [ExecutionTimeline.tsx](file:///Users/nicolas/Documents/workspace/AgentForge/frontend/src/components/execution/ExecutionTimeline.tsx) with a **cinematic, animated timeline**:

```
  ◉ ─────────── ◉ ─────────── ◉ ─────────── ◉
  │             │              │              │
  Trigger      LLM call       Tool call      Complete
  ↓             ↓              ↓              ↓
  [input]      [thinking]     [web_search]   [✓ 1.2s]

  ════════════════════════════════════════════
       ▲ progress bar fills in real-time ▲
```

- Each node **pulses with glow** when it's the active step
- Connections between nodes show **particle travel** animation
- Content bubbles **slide in** as each step completes
- Progress bar: gradient fill with a **trailing glow** effect
- Duration badges: animate count-up

### 3.2 — Live Graph Execution Overlay

When an agent executes, the builder graph comes alive:

- Active node: **breathing glow** + scale pulse (1 → 1.03 → 1)
- Processing: node border becomes an animated **conic gradient** spinner
- Completed node: brief **flash** + checkmark overlay
- Failed node: red pulse + shake animation
- Edge carrying data: **glowing dots** travel along the edge path

### 3.3 — Agent Activity Toasts: Redesign

Current [AgentToastStack.tsx](file:///Users/nicolas/Documents/workspace/AgentForge/frontend/src/components/agent/AgentToastStack.tsx) is functional. Upgrade:

- Toast container: **glassmorphic pill** with type-colored left accent
- Entry animation: slide up + scale in with spring easing
- Exit: slide down + fade out
- Active toast has a **shimmer** highlight sweep
- Stack: perspective transform (cards behind appear smaller + shifted)
- Add **mini progress ring** per toast that fills as step completes

### 3.4 — Interrupt Modal: Critical Decision UI

Current [InterruptPopup.tsx](file:///Users/nicolas/Documents/workspace/AgentForge/frontend/src/components/execution/InterruptPopup.tsx) needs drama:

- Full-screen **frosted glass overlay** with red-tinted warning glow
- Modal card: **glassmorphic** with animated danger border (alternating glow)
- Decision buttons: large, clear, with color-coded glow (green = approve, red = reject)
- Add a **countdown indicator** if timeout is configured
- Sound-optional: subtle notification chime via `useAmbientSound`

---

## Phase 4 — Chat & Conversation: The Dialogue Canvas

> **Priority**: 🟡 MEDIUM-HIGH
> **Effort**: ~2-3 days
> **Files**: `src/components/chat/*`, `src/app/chat/page.tsx`

### 4.1 — Chat Slide-Over: Glass Theater

Current [ChatSlideOver.tsx](file:///Users/nicolas/Documents/workspace/AgentForge/frontend/src/components/chat/ChatSlideOver.tsx) improvements:

- Panel: replace `bg-af-surface-void/95` with **deep glassmorphism** — `af-glass-heavy` with extra blur
- Backdrop: add a **radial gradient overlay** centered on the panel (creates "spotlight" effect)
- Panel entry: spring animation with slight rotation (rotate3d subtle tilt)

### 4.2 — Message Bubbles: Living Text

- User messages: **gradient background** (brand primary → secondary) instead of flat color
- Assistant messages: glassmorphic card with subtle border glow
- **Text reveal animation**: characters appear with a typewriter-like cascade (for non-streaming messages loaded from history)
- Streaming cursor `▌`: replace with a **waveform icon** that morphs into the cursor (already partially done)
- Code blocks: **syntax-highlighted** with copy button + line numbers + glassmorphic wrapper
- Failed messages: red glow pulse on the error border

### 4.3 — Agent Step Chips: Inline Activity Feed

Current [AgentStepChips.tsx](file:///Users/nicolas/Documents/workspace/AgentForge/frontend/src/components/agent/AgentStepChips.tsx) — enhance:

- Each chip: glassmorphic pill with type-colored icon
- Expandable: click to reveal step details (input/output preview)
- Entry animation: cascade in from left with 50ms stagger
- Add **duration indicator** per step (tiny progress ring)

### 4.4 — Input Area: Focus Spotlight

- Input border: on focus, emit a **soft glow halo** that expands outward
- Character count: show as a fading progress arc around the send button
- Suggestions: **floating glass chips** that hover above the input with parallax
- Voice input button: add a **waveform visualization** (circular) when recording

---

## Phase 5 — Dashboard & Inner Pages: Mission Control

> **Priority**: 🟡 MEDIUM
> **Effort**: ~3-4 days
> **Files**: `src/app/dashboard/page.tsx`, `src/app/agents/page.tsx`, `src/components/layout/ToolShell.tsx`

### 5.1 — Sidebar: Neon Navigation

Current [ToolShell.tsx](file:///Users/nicolas/Documents/workspace/AgentForge/frontend/src/components/layout/ToolShell.tsx) sidebar:

- **Glassmorphic background** with reduced opacity
- Active item: **neon glow indicator** (animated left border that "breathes")
- Hover: subtle **gradient reveal** from left
- Icons: add subtle **glow on active** state
- Version badge at top: style as a glass pill with gradient text
- "+ New Agent" button: **pulsing glow CTA** that draws attention
- Add **collapse/expand** with a smooth width transition + icon-only mode

### 5.2 — Dashboard: Stat Orbs

Current [StatCard](file:///Users/nicolas/Documents/workspace/AgentForge/frontend/src/app/dashboard/page.tsx) components — transform into **glassmorphic stat orbs**:

- Background: `af-glass-interactive` with type-colored accent gradient
- Number: **count-up animation** on mount (0 → actual value in 1s with easing)
- Icon: replace Material Symbols with **animated SVG micro-illustrations**
  - Agents: tiny robot that blinks
  - Executions: play icon that pulses
  - Latency: stopwatch that ticks
  - Security: shield that shimmers
- Hover: card lifts with enhanced glow + shadow depth

### 5.3 — Agents List: Fleet Grid

Current agents list is a vertical table. Transform into:

```
┌───────────┬───────────┬───────────┐
│  Agent 1  │  Agent 2  │  Agent 3  │
│  [status] │  [status] │  [status] │
│  health ● │  health ● │  health ● │
│  [chat]   │  [chat]   │  [chat]   │
└───────────┴───────────┴───────────┘
```

- Each card: glassmorphic with **node-type accent gradient** based on primary node type
- Health score: render as a **small radial gauge** (SVG arc)
- Status badge: **pulsing dot** (green = active, amber = paused)
- Card hover: **tilt effect** (perspective transform based on mouse position) + shadow deepen
- Grid entry: staggered `af-reveal` from bottom

### 5.4 — Recent Executions: Animated Table

- Row hover: glassmorphic highlight with gradient sweep
- Status icons: **animated** (running = spin, complete = checkmark draw, failed = shake)
- Duration: **mini sparkline** showing execution time in context of others
- Add **time-relative badge** with live update (`2m ago` → updates every 30s)

### 5.5 — Command Palette: Spotlight Polish

Current [CommandPalette.tsx](file:///Users/nicolas/Documents/workspace/AgentForge/frontend/src/components/ui/CommandPalette.tsx) is solid. Enhancements:

- Backdrop: **stronger blur** + dark gradient
- Results: add **fuzzy match highlighting** (matched characters in accent color)
- Agent results: show **mini health bar** inline
- Navigation items: add **keyboard shortcut hints** where applicable
- Entry animation: scale from 0.9 + opacity with spring curve

---

## Phase 6 — Micro-Interactions & Polish Layer

> **Priority**: 🟢 REFINEMENT — the difference between good and exceptional
> **Effort**: ~2 days
> **Files**: Various, mostly CSS + new hooks

### 6.1 — Cursor Trail Effect

On the landing page only, add a **subtle cursor trail** — fading indigo dots that follow the cursor with delay. Creates a "constellation" feeling of interacting with a neural network.

Implementation: `src/components/fx/CursorTrail.tsx` — `pointermove` event, ring buffer of positions, canvas overlay.

### 6.2 — Page Transitions

Between route changes, add:
- Exit: current content fades out + scales to 0.98 (150ms)
- Enter: new content fades in from scale 0.98 → 1 (250ms with spring)

Implementation: wrap `{children}` in layout with `AnimatePresence`-like logic using CSS transitions + `usePathname()` key.

### 6.3 — Skeleton Loading States

Replace all `animate-pulse` skeleton placeholders with **shimmer loading states**:

```css
.af-skeleton {
  background: linear-gradient(
    90deg,
    var(--color-af-surface-container) 25%,
    var(--color-af-surface-high) 50%,
    var(--color-af-surface-container) 75%
  );
  background-size: 200% 100%;
  animation: af-shimmer 1.5s ease-in-out infinite;
}
```

### 6.4 — Button Feedback

All interactive buttons get:
- **Press**: scale to 0.97 with quick ease (50ms)
- **Release**: spring back to 1.0 (200ms with overshoot)
- **Primary CTA buttons**: add a **gradient sweep** on hover (light passes across the button)
- **Ghost buttons**: border glow intensifies on hover

### 6.5 — Toast Notifications

Current [NotificationCenter.tsx](file:///Users/nicolas/Documents/workspace/AgentForge/frontend/src/components/layout/NotificationCenter.tsx) — enhance with:
- Glassmorphic toast container
- Type-colored left accent stripe
- Entry: slide in from right + scale up from 0.9
- Auto-dismiss progress bar at bottom
- Stack perspective (further toasts appear smaller)

### 6.6 — Scroll Progress Indicator

Add a thin gradient line at the top of the viewport (below header) that fills left→right as the user scrolls. Landing page only.

```css
.af-scroll-progress {
  height: 2px;
  background: linear-gradient(90deg, #4F46E5, #7C3AED, #2DD4BF);
  transform-origin: left;
  transform: scaleX(var(--scroll-progress, 0));
}
```

---

## Component Inventory & Gap Analysis

### Existing Components → Enhancement Map

| Component | File | Enhancement |
|---|---|---|
| `AuroraBackground` | [AuroraBackground.tsx](file:///Users/nicolas/Documents/workspace/AgentForge/frontend/src/components/layout/AuroraBackground.tsx) | Keep + layer fractal canvas beneath |
| `AsciiField` | [AsciiField.tsx](file:///Users/nicolas/Documents/workspace/AgentForge/frontend/src/components/layout/AsciiField.tsx) | Replace with FractalCanvas, keep as reduced-motion fallback |
| `AppHeader` | [AppHeader.tsx](file:///Users/nicolas/Documents/workspace/AgentForge/frontend/src/components/layout/AppHeader.tsx) | Add scroll-based glass intensification |
| `ToolShell` | [ToolShell.tsx](file:///Users/nicolas/Documents/workspace/AgentForge/frontend/src/components/layout/ToolShell.tsx) | Full glassmorphism + neon nav |
| `StatCard` | Dashboard `page.tsx` (inline) | Extract → `GlassStat` component |
| `InspectorPanel` | [InspectorPanel.tsx](file:///Users/nicolas/Documents/workspace/AgentForge/frontend/src/components/builder/InspectorPanel.tsx) | Glassmorphic + animated fields |
| `ExecutionTimeline` | [ExecutionTimeline.tsx](file:///Users/nicolas/Documents/workspace/AgentForge/frontend/src/components/execution/ExecutionTimeline.tsx) | Cinematic timeline |
| `AgentToastStack` | [AgentToastStack.tsx](file:///Users/nicolas/Documents/workspace/AgentForge/frontend/src/components/agent/AgentToastStack.tsx) | Glass pills + spring animations |
| `ChatSlideOver` | [ChatSlideOver.tsx](file:///Users/nicolas/Documents/workspace/AgentForge/frontend/src/components/chat/ChatSlideOver.tsx) | Deep glass theater |
| `CommandPalette` | [CommandPalette.tsx](file:///Users/nicolas/Documents/workspace/AgentForge/frontend/src/components/ui/CommandPalette.tsx) | Spotlight + fuzzy highlight |
| `InterruptPopup` | [InterruptPopup.tsx](file:///Users/nicolas/Documents/workspace/AgentForge/frontend/src/components/execution/InterruptPopup.tsx) | Dramatic decision UI |

### New Components to Create

| Component | Path | Purpose |
|---|---|---|
| `FractalCanvas` | `src/components/fx/FractalCanvas.tsx` | Scroll-linked fractal background |
| `CursorTrail` | `src/components/fx/CursorTrail.tsx` | Landing page cursor particle trail |
| `ScrollReveal` | `src/components/fx/ScrollReveal.tsx` | IntersectionObserver reveal wrapper |
| `GlassStat` | `src/components/ui/GlassStat.tsx` | Extracted glassmorphic stat card |
| `CircularGauge` | `src/components/ui/CircularGauge.tsx` | SVG circular progress indicator |
| `CountUp` | `src/components/ui/CountUp.tsx` | Animated number count-up |
| `ParticleEdge` | `src/components/builder/ParticleEdge.tsx` | Animated graph edge with particles |
| `GlowNode` | `src/components/builder/GlowNode.tsx` | Enhanced graph node with glow |
| `ScrollProgress` | `src/components/layout/ScrollProgress.tsx` | Top scroll progress bar |

### New Hooks

| Hook | Path | Purpose |
|---|---|---|
| `useScrollProgress` | `src/hooks/useScrollProgress.ts` | Returns 0-1 scroll position |
| `useScrollReveal` | `src/hooks/useScrollReveal.ts` | IntersectionObserver for reveal trigger |
| `useCountUp` | `src/hooks/useCountUp.ts` | Animated number from 0 to target |
| `useTilt` | `src/hooks/useTilt.ts` | Mouse-position-based 3D tilt |
| `useReducedMotion` | `src/hooks/useReducedMotion.ts` | Respects `prefers-reduced-motion` |

---

## Technical Architecture Notes

### Performance Guardrails

> [!WARNING]
> Immersive effects must never compromise performance. These rules are non-negotiable:

1. **Fractal canvas**: offscreen canvas + `requestAnimationFrame` throttled to 30fps. Transfer frame to visible canvas via `transferToImageBitmap` or `drawImage`. Pause when tab is not visible (`document.visibilityState`).

2. **Scroll-linked animations**: use CSS `scroll-timeline` where supported, fallback to passive scroll listeners with `requestAnimationFrame` throttle. Never trigger layout in scroll handlers.

3. **Intersection Observer**: create a single shared observer for all `ScrollReveal` components, not one per element.

4. **CSS containment**: add `contain: layout paint style` on heavy glass containers to prevent repaint cascading.

5. **`will-change`**: only on elements actively animating. Remove after animation ends.

6. **No third-party animation libraries** (Framer Motion, GSAP). Pure CSS + minimal JS keeps the bundle lean. The existing deps (`@xyflow/react`, `recharts`) are sufficient.

### Accessibility Guarantees

> [!IMPORTANT]
> Every visual enhancement must respect accessibility:

- All `prefers-reduced-motion` → disable fractal, cursor trail, parallax. Use simple fades only.
- Glass backgrounds must maintain **WCAG 2.1 AA contrast** (4.5:1 minimum on text). Test with the existing light/dark themes.
- Interactive glow effects must not be the only indicator — always pair with text or icon state changes.
- Fractal canvas: `aria-hidden="true"`, not interactive.
- All animations: `prefers-reduced-motion` query blocks (already in `globals.css` — extend to new keyframes).

### Dependency Strategy

No new npm dependencies. Everything is implemented with:
- **Canvas 2D API** (fractals, cursor trail)
- **CSS custom properties** + `@keyframes` (glassmorphism, glow, shimmer)
- **IntersectionObserver** (scroll reveals)
- **SVG** (circular gauges, enhanced edges)
- **Existing @xyflow/react** (custom node/edge components)

### File Organization

```
src/
├── components/
│   ├── fx/                      ← NEW: visual effects
│   │   ├── FractalCanvas.tsx
│   │   ├── CursorTrail.tsx
│   │   └── ScrollReveal.tsx
│   ├── ui/
│   │   ├── GlassStat.tsx        ← NEW
│   │   ├── CircularGauge.tsx    ← NEW
│   │   ├── CountUp.tsx          ← NEW
│   │   ├── CommandPalette.tsx   ← ENHANCED
│   │   └── ...
│   ├── builder/
│   │   ├── GlowNode.tsx         ← NEW
│   │   ├── ParticleEdge.tsx     ← NEW
│   │   ├── InspectorPanel.tsx   ← ENHANCED
│   │   └── ...
│   ├── layout/
│   │   ├── ScrollProgress.tsx   ← NEW
│   │   └── ... (all enhanced)
│   └── ...
├── hooks/
│   ├── useScrollProgress.ts     ← NEW
│   ├── useScrollReveal.ts       ← NEW
│   ├── useCountUp.ts            ← NEW
│   ├── useTilt.ts               ← NEW
│   ├── useReducedMotion.ts      ← NEW
│   └── ...
└── app/
    ├── globals.css              ← EXTENDED (tokens + glass + shimmer)
    └── ...
```

---

## Priority Matrix

| Phase | Priority | Effort | Impact | Dependencies |
|---|---|---|---|---|
| Phase 0 — Design System | 🔴 Critical | 2-3d | Foundation | None |
| Phase 1 — Landing Page | 🔴 High | 3-4d | First impression | Phase 0 |
| Phase 2 — Agent Builder | 🔴 High | 4-5d | Core product | Phase 0 |
| Phase 3 — Execution Flow | 🟠 High | 3-4d | Wow factor | Phase 0, Phase 2 |
| Phase 4 — Chat/Conversation | 🟡 Medium-High | 2-3d | Daily UX | Phase 0 |
| Phase 5 — Dashboard/Inner | 🟡 Medium | 3-4d | Polish | Phase 0 |
| Phase 6 — Micro-interactions | 🟢 Refinement | 2d | Excellence | All previous |

**Total estimated effort**: ~20-25 days of focused implementation

---

> [!NOTE]
> This roadmap is designed as a **progressive enhancement** — each phase builds on Phase 0's foundation but can be implemented independently. The platform remains fully functional throughout the transformation. Start with Phase 0, then tackle Phase 1 and Phase 2 in parallel for maximum impact.
