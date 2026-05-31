# Prova — Website Design Document
## Neural Formal Verification Engine

---

## Reference Aesthetic

The target look is **NvChad / LazyVim / AstroNvim docs sites** — utility-first,
terminal-native, no corporate fluff. Think: a README that became a website.

Key references:
- nvchad.com — dark bg, terminal screenshots, minimal nav, monospace everywhere
- lazyvim.github.io — docs-first, no hero BS, straight to the point
- docs.astronvim.com — clean sidebar, code blocks as the main content
- charm.sh — CLI tools with beautiful branding (bubbletea, glow, vhs)
- starship.rs — cross-shell prompt site, ASCII-heavy, gorgeous dark theme

---

## Identity — Logo

```
  ╔═╗╔═╗╔═╗ ╦ ╦╔═╗╔╗╔╔╦╗
  ╚═╗║╣ ║═╬╗║ ║║╣ ║║║ ║
  ╚═╝╚═╝╚═╝╚╚═╝╚═╝╝╚╝ ╩
  neural formal verification engine
```

Double-line box-drawing characters. Clean, sharp, terminal-native.

Render in `<pre>` with gradient color
(CSS `background: linear-gradient(90deg, var(--accent-4), var(--accent-5))` +
`-webkit-background-clip: text` + `-webkit-text-fill-color: transparent`).
Purple -> cyan gradient reinforces the neuro/symbolic duality.

---

## Color Palette

Steal from terminal color schemes. Base palette inspired by **Tokyo Night / Catppuccin Mocha**.

| Token            | Hex       | Usage                          |
|------------------|-----------|--------------------------------|
| `--bg-deep`      | `#0a0e14` | Page background                |
| `--bg-surface`   | `#11151c` | Card/panel backgrounds         |
| `--bg-elevated`  | `#1a1e2e` | Hover states, active elements  |
| `--border`       | `#2a2e3e` | Subtle borders, dividers       |
| `--text-primary` | `#c8d3f5` | Body text                      |
| `--text-muted`   | `#636da6` | Secondary text, comments       |
| `--accent-1`     | `#7aa2f7` | Primary accent (links, focus)  |
| `--accent-2`     | `#9ece6a` | Success, verified, pass        |
| `--accent-3`     | `#f7768e` | Error, failed, counterexample  |
| `--accent-4`     | `#bb9af7` | Purple highlights, neural      |
| `--accent-5`     | `#7dcfff` | Cyan highlights, symbolic      |

The two-tone accent split matters:
- **Purple (`--accent-4`)** = neural / learned / probabilistic
- **Cyan (`--accent-5`)** = symbolic / formal / deterministic
- This duality should be a recurring visual motif across the site

---

## Typography

| Role       | Font                  | Weight   | Size      |
|------------|-----------------------|----------|-----------|
| Monospace  | JetBrains Mono / Berkeley Mono | 400-700  | 14-16px   |
| Headings   | JetBrains Mono        | 700      | 24-48px   |
| Body       | Inter                 | 400      | 16px      |
| Code       | JetBrains Mono        | 400      | 14px      |

Body text CAN be monospace too if you want full terminal commitment.
If mixing, only use Inter for paragraph-length explanations. Everything else mono.

---

## Layout — Page Structure

### 1. Hero (above the fold)

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│     ╔═╗╔═╗╔═╗ ╦ ╦╔═╗╔╗╔╔╦╗                            │
│     ╚═╗║╣ ║═╬╗║ ║║╣ ║║║ ║                              │
│     ╚═╝╚═╝╚═╝╚╚═╝╚═╝╝╚╝ ╩                             │
│     neural formal verification engine                   │
│                                                         │
│     neurosymbolic python debugger that proves           │
│     your code correct — or finds the counterexample     │
│                                                         │
│     $ pip install sequent                               │
│     $ sequent verify main.py                            │
│                                                         │
│     [ GitHub ]  [ Docs ]  [ Get Started ]               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

- Logo with purple->cyan gradient (`-webkit-background-clip: text`)
- One-liner tagline in `--text-muted`
- Install command in a fake terminal prompt (`$` prefix, copy button)
- CTA buttons styled as terminal commands, not rounded pills
- NO hero image. NO illustration. The logo IS the visual.

### 2. Terminal Demo

A fake terminal window showing Prova in action. Not a screenshot — an actual
styled `<div>` that looks like a terminal:

```
┌─ sequent ─────────────────────────────────── ● ○ ○ ─┐
│ $ sequent verify auth.py                             │
│                                                    │
│ ✓ verify login()          .............. PASS      │
│ ✓ verify hash_password()  .............. PASS      │
│ ✗ verify token_refresh()  .............. FAIL      │
│                                                    │
│   counterexample found:                            │
│     token_refresh(exp=0, iat=-1)                   │
│     → expected: TokenError                         │
│     → got: Token(exp=0)                            │
│                                                    │
│   neural confidence: 0.94                          │
│   symbolic proof:    incomplete (2/3 branches)     │
│                                                    │
│ 3 functions verified | 2 passed | 1 failed         │
│ time: 1.2s                                         │
└────────────────────────────────────────────────────┘
```

- PASS = green (`--accent-2`)
- FAIL = red (`--accent-3`)
- "neural confidence" = purple (`--accent-4`)
- "symbolic proof" = cyan (`--accent-5`)
- Typing animation that plays through the output line by line
- Terminal chrome: dots in top-right (not left — match nvchad style), tab title

### 3. Features Section

NO feature cards with icons. Use a vertical list with ASCII section dividers:

```
── features ──────────────────────────────────────────

▸ neurosymbolic verification
  combines neural pattern recognition with symbolic proof engines.
  learns from your codebase, proves against formal specs.

▸ counterexample generation
  when verification fails, sequent doesn't just say "wrong" —
  it gives you the exact inputs that break your function.

▸ incremental analysis
  only re-verifies functions that changed. watches your files.
  runs in <2s on most codebases.

▸ python-native
  no DSLs. no annotations. write normal python.
  sequent infers types, contracts, and invariants automatically.
```

- Monospace everything
- `▸` as bullet points (or `>`, `*`, `-`)
- Section header styled like a terminal divider `── name ───────`
- Descriptions in `--text-muted`, feature names in `--text-primary`
- Subtle hover: feature name shifts to `--accent-1`

### 4. Code Example

Side-by-side or stacked: your Python code on the left, Prova's analysis on the right.
Use actual syntax highlighting (Shiki with tokyo-night theme).

```
┌─ your code ──────────────────┐  ┌─ sequent output ──────────────┐
│                              │  │                                │
│ def divide(a: int,           │  │ ✓ divide()                    │
│            b: int) -> float: │  │   precondition: b != 0        │
│     return a / b             │  │   postcondition: ∀a,b.        │
│                              │  │     result * b ≈ a            │
│                              │  │   status: VERIFIED             │
│                              │  │   proof: complete (SMT)        │
│                              │  │                                │
└──────────────────────────────┘  └────────────────────────────────┘
```

- BOTH panels are ONE component — a single `display: grid; grid-template-columns: 1fr 1fr`
  container with NO gap in vertical alignment. They share the same top and bottom edge.
- Do NOT use two separate floating divs. One wrapper, two children, `align-items: stretch`.
- The code content inside each panel is `vertical-align: top` / `align-self: start`
  so text starts at the top of both — the panels themselves are equal height, the
  content just fills from top down naturally.
- Box-drawing characters in the ASCII mockup above — in real HTML use
  `--bg-surface` backgrounds with 1px `--border` borders, no actual box chars.
- Mathematical symbols (∀, ≈, ∈) in the proof output add credibility

### 5. Install / Get Started

```
── quickstart ────────────────────────────────────────

  $ pip install sequent
  $ cd your-project
  $ sequent init
  $ sequent verify

  that's it.
```

Dead simple. Fake terminal block. Copy button on hover.

### 6. Footer

Minimal. One line.

```
  sequent · MIT · github · docs · built by devang
```

---

## Component Styling

### Buttons
- Border-only, monospace text, no border-radius (square corners = terminal)
- Hover: fill with `--bg-elevated`, text shifts to `--accent-1`
- Style: `[ Get Started ]` not `Get Started` — bracket aesthetic

### Code Blocks
- Background: `--bg-surface`
- Border: 1px `--border`
- Top bar with filename tab and colored dots
- Syntax highlighting: Shiki with `tokyo-night` theme
- Copy button (top-right, appears on hover, monospace "copy" text)

### Links
- Color: `--accent-1`
- No underline by default
- Hover: underline + slight glow (`text-shadow: 0 0 8px var(--accent-1)`)

### Dividers
```
── section name ──────────────────────────────────
```
- Box-drawing character `─` repeated
- Section name in `--text-muted`
- Full width of content area

---

## Background, Margins & Ambient Decor

The background should NOT be a flat dead color. It needs life — but quiet life.
Think: the texture of a terminal that's been running all night.

### Full-page background: Drifting ASCII field

A full-viewport `<canvas>` or absolutely-positioned `<pre>` layer behind all content.
Filled with faintly visible, slowly drifting characters. NOT the Matrix rain — subtler.

**Option A: Proof symbols drift (recommended)**
Random formal logic / math symbols float very slowly upward or drift diagonally:
```
  ∀  ∃  ⊢  ⊨  ¬  ∧  ∨  →  ↔  ≡  ⊥  ⊤  λ  Γ  ⊦  ∈  ∉  ⊂  ∅
```
- Rendered in `--text-muted` at ~0.03-0.06 opacity (barely visible)
- Font: JetBrains Mono, sizes between 12-20px, randomly placed
- Movement: CSS `@keyframes` translateY, 60-120s duration (glacially slow)
- Each symbol has a random start position, size, and speed
- ~40-60 symbols on screen at once, sparse, never overlapping content
- NO color — pure `--text-muted` at near-zero opacity
- This is wallpaper, not content. If you notice it, it's too loud.

**Option B: Binary / hex rain (lighter alternative)**
Columns of `0` and `1` or hex digits (`0-9 a-f`) at 0.02-0.04 opacity,
scrolling downward very slowly. Like Matrix but basically invisible —
just enough to give the background texture instead of being a void.

**Option C: Dot grid**
A fixed grid of `.` or `·` characters at 0.05 opacity, spaced 40-60px apart.
No animation at all — just gives the background a subtle graph-paper feel.
Cheap, zero performance cost, still looks intentional.

### Margin decor: Line numbers

In the left margin (left 40-60px of the viewport), render faint line numbers
counting up from 1, as if the entire page is one long source file:

```
   1
   2
   3
   4
   ...
  47
  48
```

- Color: `--text-muted` at 0.08 opacity
- Font: JetBrains Mono 12px
- Fixed position, scrolls WITH the page (not sticky)
- Lines spaced to match the body text line-height
- This is a very NvChad/IDE-native touch — makes the whole page feel like a buffer

### Right margin decor: Scrollbar gutter marks

In the right margin, optionally render faint marks that indicate where sections
are, like the minimap gutter in VS Code:

```
                                                          ┃ ← hero
                                                          ┃
                                                          ╏ ← demo
                                                          ╏
                                                          ┃ ← features
```

- Use `┃` (thick) for major sections and `╏` (thin) for subsections
- Color: `--accent-4` and `--accent-5` alternating at 0.1 opacity
- Optional — only if the page is long enough to warrant it

### Corner decor: Status line

Bottom-left or bottom-right of viewport, fixed position, a fake vim statusline:

```
  sequent.md  [+]  utf-8  unix  ln 1  col 1
```

or

```
  -- NORMAL --  sequent.md  1:1  ∀
```

- Color: `--text-muted` at 0.15 opacity, slightly more visible than bg decor
- Monospace, small (11-12px)
- Static — doesn't change, purely decorative
- Optional: update `ln` number based on scroll position for a fun detail

### Performance rules for all background elements

- Use CSS animations only, NOT JS requestAnimationFrame (unless canvas)
- If using canvas for the drifting symbols, cap at 30fps and use `will-change: transform`
- Total animated elements: <80 DOM nodes or one single canvas
- All decor layers get `pointer-events: none` so they never block clicks
- On mobile: disable the drifting animation entirely, keep only dot grid or nothing
- `prefers-reduced-motion` media query: disable ALL animations

---



| Element        | Animation                                    |
|----------------|----------------------------------------------|
| ASCII logo     | Fade in line-by-line on load (typewriter)     |
| Terminal demo  | Output types line-by-line with 50ms delay     |
| Feature items  | Fade in on scroll (stagger 100ms each)        |
| Code blocks    | None — static, instant. Code should feel solid|
| Cursor blink   | Blinking `█` cursor in terminal blocks        |
| CRT scanlines  | Optional: very faint horizontal lines over bg |

NO parallax. NO scroll hijacking. NO particle effects. This is a tool, not a showroom.

---

## Tech Stack (suggested)

| Layer      | Tool                           |
|------------|--------------------------------|
| Framework  | Astro or Next.js (static)      |
| Styling    | Tailwind CSS                   |
| Fonts      | JetBrains Mono (Google Fonts)  |
| Syntax     | Shiki (tokyo-night theme)      |
| Animation  | CSS only (or Framer Motion)    |
| Deploy     | Vercel or GitHub Pages         |

Astro is the better pick — it's what the Neovim config sites use (starship.rs vibes),
ships zero JS by default, and the content-heavy static approach fits perfectly.

---

## What NOT To Do

- No gradient mesh hero backgrounds
- No "trusted by 10,000 developers" social proof banners
- No testimonial carousels
- No animated SVG illustrations
- No hamburger menus (single page, no nav needed, or minimal top bar)
- No rounded corners on anything — square = terminal
- No light mode (this is a terminal tool, dark only)
- No emoji anywhere on the site
- No stock photography obviously

---

## Vibe Check

The site should feel like you `cat`'d a beautifully formatted README
in a tricked-out terminal. Every visitor should think:
"this person lives in the terminal and their tool does too."

If NvChad's site and Vercel's site had a baby that grew up using only tmux,
that's Prova's website.
