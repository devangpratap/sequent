import { useNavigate } from 'react-router-dom'
import { useEffect, useRef, useState, useMemo } from 'react'

const ASCII_LOGO = [
  '  \u2554\u2550\u2557\u2554\u2550\u2557\u2554\u2550\u2557 \u2566 \u2566\u2554\u2550\u2557\u2554\u2557\u2554\u2554\u2566\u2557',
  '  \u255A\u2550\u2557\u2551\u2563 \u2551\u2550\u256C\u2557\u2551 \u2551\u2551\u2563 \u2551\u2551\u2551 \u2551',
  '  \u255A\u2550\u255D\u255A\u2550\u255D\u255A\u2550\u255D\u255A\u255A\u2550\u255D\u255A\u2550\u255D\u255D\u255A\u255D \u2569',
]

const TERMINAL_LINES = [
  { type: 'cmd', text: '$ sequent verify auth.py' },
  { type: 'blank' },
  { type: 'pass', text: '  \u2713 verify login()          \u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7 PASS' },
  { type: 'pass', text: '  \u2713 verify hash_password()  \u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7 PASS' },
  { type: 'fail', text: '  \u2717 verify token_refresh()  \u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7 FAIL' },
  { type: 'blank' },
  { type: 'muted', text: '    counterexample found:' },
  { type: 'muted', text: '      token_refresh(exp=0, iat=-1)' },
  { type: 'muted', text: '      \u2192 expected: TokenError' },
  { type: 'fail-dim', text: '      \u2192 got:      Token(exp=0)' },
  { type: 'blank' },
  { type: 'purple', text: '    neural confidence: 0.94' },
  { type: 'cyan', text: '    symbolic proof:    incomplete (2/3 branches)' },
  { type: 'blank' },
  { type: 'muted', text: '  3 functions | 2 passed | 1 failed | 1.2s' },
]

const FEATURES = [
  {
    name: 'neurosymbolic verification',
    desc: 'combines neural pattern recognition with symbolic proof engines. learns from your codebase, proves against formal specs.',
  },
  {
    name: 'counterexample generation',
    desc: "when verification fails, sequent doesn't just say \"wrong\" \u2014 it gives you the exact inputs that break your function.",
  },
  {
    name: 'incremental analysis',
    desc: 'only re-verifies functions that changed. watches your files. runs in <2s on most codebases.',
  },
  {
    name: 'python-native',
    desc: 'no DSLs. no annotations. write normal python. sequent infers types, contracts, and invariants automatically.',
  },
]

const COLOR_MAP = {
  cmd: 'var(--text-primary)',
  pass: 'var(--accent-2)',
  fail: 'var(--accent-3)',
  'fail-dim': 'var(--accent-3)',
  muted: 'var(--text-muted)',
  purple: 'var(--accent-4)',
  cyan: 'var(--accent-5)',
}

// Proof symbols that drift in the background
const PROOF_SYMBOLS = [
  '\u2200', '\u2203', '\u22A2', '\u22A8', '\u00AC', '\u2227', '\u2228', '\u2192',
  '\u2194', '\u2261', '\u22A5', '\u22A4', '\u03BB', '\u0393', '\u22A6', '\u2208',
  '\u2209', '\u2282', '\u2205',
]

function DriftingSymbols() {
  const symbols = useRef(null)

  if (!symbols.current) {
    symbols.current = Array.from({ length: 50 }, (_, i) => ({
      id: i,
      char: PROOF_SYMBOLS[Math.floor(Math.random() * PROOF_SYMBOLS.length)],
      left: Math.random() * 100,
      top: Math.random() * 100,
      size: 12 + Math.random() * 8,
      duration: 60 + Math.random() * 60,
      delay: Math.random() * -60,
      opacity: 0.03 + Math.random() * 0.03,
    }))
  }

  return (
    <div className="drifting-symbols" aria-hidden="true">
      {symbols.current.map(s => (
        <span
          key={s.id}
          className="drift-symbol"
          style={{
            left: `${s.left}%`,
            top: `${s.top}%`,
            fontSize: `${s.size}px`,
            animationDuration: `${s.duration}s`,
            animationDelay: `${s.delay}s`,
            opacity: s.opacity,
          }}
        >
          {s.char}
        </span>
      ))}
    </div>
  )
}

// Line numbers in left margin
function LineNumbers() {
  const [count, setCount] = useState(80)

  useEffect(() => {
    const update = () => {
      const h = document.documentElement.scrollHeight
      setCount(Math.ceil(h / 20))
    }
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])

  return (
    <div className="line-numbers" aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <div key={i}>{i + 1}</div>
      ))}
    </div>
  )
}

// Vim statusline
function StatusLine() {
  const [ln, setLn] = useState(1)

  useEffect(() => {
    const onScroll = () => {
      const scrollPct = window.scrollY / (document.documentElement.scrollHeight - window.innerHeight || 1)
      setLn(Math.max(1, Math.round(scrollPct * 400)))
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <div className="vim-statusline" aria-hidden="true">
      -- NORMAL --  sequent.md  {ln}:1  {'\u22A2'}
    </div>
  )
}

// Terminal demo with typing animation
function TerminalDemo() {
  const [visibleLines, setVisibleLines] = useState(0)
  const ref = useRef(null)
  const animated = useRef(false)

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !animated.current) {
          animated.current = true
          let i = 0
          const interval = setInterval(() => {
            i++
            setVisibleLines(i)
            if (i >= TERMINAL_LINES.length) clearInterval(interval)
          }, 80)
        }
      },
      { threshold: 0.3 }
    )
    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [])

  return (
    <div ref={ref} className="terminal-window">
      <div className="terminal-titlebar">
        <span className="terminal-title">sequent</span>
        <div className="terminal-dots">
          <span className="dot dot-red" />
          <span className="dot dot-yellow" />
          <span className="dot dot-green" />
        </div>
      </div>
      <div className="terminal-body">
        {TERMINAL_LINES.slice(0, visibleLines).map((line, i) => {
          if (line.type === 'blank') return <div key={i} className="terminal-blank" />
          return (
            <div
              key={i}
              className="terminal-line"
              style={{
                color: COLOR_MAP[line.type],
                opacity: line.type === 'fail-dim' ? 0.7 : 1,
              }}
            >
              {line.text}
            </div>
          )
        })}
        {visibleLines < TERMINAL_LINES.length && (
          <span className="cursor-blink" />
        )}
      </div>
    </div>
  )
}

// Section divider component
function SectionDivider({ label }) {
  const dashes = '\u2500'.repeat(50)
  return (
    <div className="section-divider">
      {'\u2500\u2500'} {label} {dashes}
    </div>
  )
}

// Code example with fake syntax highlighting
function CodeExample() {
  return (
    <div className="code-split">
      <div className="code-panel">
        <div className="code-panel-header">your code</div>
        <pre className="code-panel-body code-python">
          <span className="syn-keyword">def</span>{' '}
          <span className="syn-function">divide</span>
          {'('}
          <span className="syn-param">a</span>
          {': '}
          <span className="syn-type">int</span>
          {',\n           '}
          <span className="syn-param">b</span>
          {': '}
          <span className="syn-type">int</span>
          {') -> '}
          <span className="syn-type">float</span>
          {':\n    '}
          <span className="syn-keyword">return</span>
          {' a / b'}
        </pre>
      </div>
      <div className="code-panel">
        <div className="code-panel-header">sequent output</div>
        <pre className="code-panel-body code-output">
          <span className="syn-pass">{'\u2713'} divide()</span>
          {'\n  '}
          <span className="syn-label">precondition:</span>
          {' b != 0'}
          {'\n  '}
          <span className="syn-label">postcondition:</span>
          {' \u2200a,b.'}
          {'\n    result * b \u2248 a'}
          {'\n  '}
          <span className="syn-label">status:</span>
          {' '}
          <span className="syn-verified">VERIFIED</span>
          {'\n  '}
          <span className="syn-label">proof:</span>
          {' '}
          <span className="syn-symbolic">complete (SMT)</span>
        </pre>
      </div>
    </div>
  )
}

// Quickstart block with copy button
function QuickstartBlock() {
  const [copied, setCopied] = useState(false)
  const commands = 'pip install sequent\ncd your-project\nsequent init\nsequent verify'

  return (
    <div className="quickstart-block">
      <button
        className="quickstart-copy-btn"
        onClick={() => {
          navigator.clipboard?.writeText(commands)
          setCopied(true)
          setTimeout(() => setCopied(false), 1500)
        }}
      >
        {copied ? 'copied' : 'copy'}
      </button>
      <div><span className="prompt">$ </span>pip install sequent</div>
      <div><span className="prompt">$ </span>cd your-project</div>
      <div><span className="prompt">$ </span>sequent init</div>
      <div><span className="prompt">$ </span>sequent verify</div>
      <div className="quickstart-end">that's it.</div>
    </div>
  )
}

// ── Attention Heatmap Demo ──────────────────────────────────
const DEMO_CODE = [
  'def binary_search(arr, target):',
  '    low = 0',
  '    high = len(arr) - 1',
  '    while low < high:  # BUG: should be <=',
  '        mid = (low + high) // 2',
  '        if arr[mid] == target:',
  '            return mid',
  '        elif arr[mid] < target:',
  '            low = mid + 1',
  '        else:',
  '            high = mid - 1',
  '    return -1',
]

// Simulated per-line bug probability from GNN node scores
const DEMO_LINE_SCORES = {
  1: 0.08,
  2: 0.05,
  3: 0.12,
  4: 0.87,  // the buggy line
  5: 0.31,
  6: 0.14,
  7: 0.06,
  8: 0.18,
  9: 0.10,
  10: 0.04,
  11: 0.09,
  12: 0.22,
}

// Simulated top attention edges (src_line -> dst_line with weight)
const DEMO_ATTENTION_EDGES = [
  { src_line: 4, dst_line: 3, weight: 0.92 },
  { src_line: 4, dst_line: 12, weight: 0.78 },
  { src_line: 5, dst_line: 4, weight: 0.65 },
  { src_line: 6, dst_line: 5, weight: 0.41 },
  { src_line: 12, dst_line: 4, weight: 0.55 },
]

const DEMO_CONFIDENCE = 0.94

function scoreToHeatColor(score) {
  // Tokyo Night palette gradient: green (safe) -> yellow (suspicious) -> red (buggy)
  if (score < 0.25) {
    // Green zone: accent-2 (#9ece6a)
    const t = score / 0.25
    return {
      r: Math.round(158 * t + 30 * (1 - t)),
      g: Math.round(206 * (1 - t * 0.3)),
      b: Math.round(106 * (1 - t * 0.5)),
    }
  } else if (score < 0.55) {
    // Yellow/amber zone
    const t = (score - 0.25) / 0.3
    return {
      r: Math.round(158 + t * 66),
      g: Math.round(175 - t * 55),
      b: Math.round(53 + t * 15),
    }
  } else {
    // Red zone: accent-3 (#f7768e)
    const t = (score - 0.55) / 0.45
    return {
      r: Math.round(224 + t * 23),
      g: Math.round(120 - t * 40),
      b: Math.round(68 + t * 74),
    }
  }
}

function AttentionHeatmapDemo() {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)
  const [hoveredLine, setHoveredLine] = useState(null)

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setVisible(true)
      },
      { threshold: 0.2 }
    )
    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [])

  // Find attention edges connected to hovered line
  const activeEdges = useMemo(() => {
    if (hoveredLine === null) return []
    return DEMO_ATTENTION_EDGES.filter(
      e => e.src_line === hoveredLine || e.dst_line === hoveredLine
    )
  }, [hoveredLine])

  // Lines that are connected via attention to the hovered line
  const connectedLines = useMemo(() => {
    const set = new Set()
    activeEdges.forEach(e => {
      set.add(e.src_line)
      set.add(e.dst_line)
    })
    return set
  }, [activeEdges])

  const maxScore = Math.max(...Object.values(DEMO_LINE_SCORES))

  return (
    <div ref={ref} style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)', opacity: visible ? 1 : 0, transform: visible ? 'translateY(0)' : 'translateY(12px)', transition: 'opacity 0.5s, transform 0.5s' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1rem 1.25rem', borderBottom: '1px solid var(--border)' }}>
        <div>
          <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
            <span style={{ color: 'var(--accent-4)' }}>GNN</span> Attention Heatmap
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            per-line bug probability with attention edge flow
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {/* Legend */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <span style={{ fontSize: '0.6rem', color: 'var(--accent-2)' }}>safe</span>
            <div style={{
              width: '6rem', height: '0.4rem',
              background: 'linear-gradient(90deg, rgba(158,206,106,0.7), rgba(224,175,104,0.7), rgba(247,118,142,0.9))',
              borderRadius: '2px',
            }} />
            <span style={{ fontSize: '0.6rem', color: 'var(--accent-3)' }}>buggy</span>
          </div>
          {/* Confidence badge */}
          <div style={{
            padding: '0.2rem 0.6rem',
            border: '1px solid rgba(187,154,247,0.4)',
            fontSize: '0.7rem',
            color: 'var(--accent-4)',
          }}>
            {(DEMO_CONFIDENCE * 100).toFixed(0)}% conf
          </div>
        </div>
      </div>

      {/* Code lines with heatmap */}
      <div style={{ padding: '0.5rem 0', fontSize: '0.78rem', position: 'relative' }}>
        {DEMO_CODE.map((line, i) => {
          const lineNum = i + 1
          const score = DEMO_LINE_SCORES[lineNum] || 0
          const { r, g, b } = scoreToHeatColor(score)
          const intensity = score / maxScore
          const isHovered = hoveredLine === lineNum
          const isConnected = connectedLines.has(lineNum) && !isHovered

          return (
            <div
              key={i}
              onMouseEnter={() => setHoveredLine(lineNum)}
              onMouseLeave={() => setHoveredLine(null)}
              style={{
                display: 'flex', alignItems: 'center',
                padding: '0.3rem 1.25rem',
                background: isHovered
                  ? `rgba(${r}, ${g}, ${b}, 0.25)`
                  : isConnected
                  ? 'rgba(187, 154, 247, 0.08)'
                  : score > 0.05
                  ? `rgba(${r}, ${g}, ${b}, ${Math.min(intensity * 0.18, 0.22)})`
                  : 'transparent',
                borderLeft: score > 0.3
                  ? `3px solid rgba(${r}, ${g}, ${b}, 0.8)`
                  : isConnected
                  ? '3px solid rgba(187, 154, 247, 0.4)'
                  : '3px solid transparent',
                cursor: 'default',
                transition: 'background 0.15s, border-color 0.15s',
              }}
            >
              {/* Line number */}
              <span style={{
                width: '1.75rem', textAlign: 'right',
                color: isHovered ? 'var(--accent-4)' : 'var(--text-muted)',
                fontSize: '0.65rem', userSelect: 'none', marginRight: '0.75rem', flexShrink: 0,
                fontWeight: isHovered ? 700 : 400,
              }}>
                {lineNum}
              </span>

              {/* Code text */}
              <span style={{ flex: 1, whiteSpace: 'pre', fontFamily: 'inherit' }}>
                {line || ' '}
              </span>

              {/* Attention arrows for this line */}
              {isHovered && activeEdges.length > 0 && (
                <span style={{
                  fontSize: '0.6rem', color: 'var(--accent-4)', marginRight: '0.5rem',
                  opacity: 0.8, flexShrink: 0,
                }}>
                  {activeEdges.map((e, j) => {
                    const otherLine = e.src_line === lineNum ? e.dst_line : e.src_line
                    const dir = e.src_line === lineNum ? '\u2192' : '\u2190'
                    return (
                      <span key={j} style={{ marginLeft: j > 0 ? '0.4rem' : 0 }}>
                        {dir}L{otherLine}
                        <span style={{ color: 'var(--accent-5)', marginLeft: '2px' }}>
                          ({(e.weight * 100).toFixed(0)}%)
                        </span>
                      </span>
                    )
                  })}
                </span>
              )}

              {/* Score bar + percentage */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexShrink: 0, width: '6.5rem', justifyContent: 'flex-end' }}>
                {score > 0.05 && (
                  <>
                    <div style={{
                      width: '3rem', height: '0.35rem',
                      background: 'var(--bg-deep)', borderRadius: '2px', overflow: 'hidden',
                    }}>
                      <div style={{
                        height: '100%', borderRadius: '2px',
                        width: `${Math.min(score * 100, 100)}%`,
                        background: `rgb(${r}, ${g}, ${b})`,
                        transition: 'width 0.3s',
                      }} />
                    </div>
                    <span style={{
                      fontSize: '0.6rem',
                      color: `rgb(${r}, ${Math.max(g, 80)}, ${Math.max(b, 80)})`,
                      width: '2.2rem', textAlign: 'right',
                      fontWeight: score > 0.5 ? 700 : 400,
                    }}>
                      {(score * 100).toFixed(0)}%
                    </span>
                  </>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Attention edge summary footer */}
      <div style={{
        padding: '0.75rem 1.25rem',
        borderTop: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        fontSize: '0.65rem', color: 'var(--text-muted)',
      }}>
        <div>
          <span style={{ color: 'var(--accent-4)' }}>neural</span>{' '}
          {DEMO_ATTENTION_EDGES.length} attention edges{' \u00B7 '}
          <span style={{ color: 'var(--accent-5)' }}>symbolic</span>{' '}
          counterexample: binary_search([1,2,3], 3)
        </div>
        <div style={{ color: 'var(--text-muted)', opacity: 0.6 }}>
          hover lines to see attention flow
        </div>
      </div>
    </div>
  )
}

export default function Landing() {
  const navigate = useNavigate()
  const [copied, setCopied] = useState(false)

  return (
    <>
      <DriftingSymbols />
      <LineNumbers />
      <StatusLine />

      <div className="landing-container">
        {/* Hero */}
        <section className="hero">
          <pre className="hero-ascii hero-logo-gradient" aria-label="Sequent">
            {ASCII_LOGO.join('\n')}
          </pre>
          <p className="hero-subtitle">neural formal verification engine</p>
          <p className="hero-tagline">
            neurosymbolic python debugger that proves
            <br />
            your code correct — or finds the counterexample
          </p>

          <div className="hero-install">
            <span className="prompt">$ </span>
            <span>pip install sequent</span>
            <button
              className="copy-btn"
              onClick={() => {
                navigator.clipboard?.writeText('pip install sequent')
                setCopied(true)
                setTimeout(() => setCopied(false), 1500)
              }}
              style={copied ? { opacity: 1, color: 'var(--accent-2)' } : {}}
            >
              {copied ? 'copied' : 'copy'}
            </button>
          </div>

          <div className="hero-actions">
            <a
              href="https://github.com/devangpratapsingh/sequent"
              target="_blank"
              rel="noopener noreferrer"
              className="btn"
            >
              [ GitHub ]
            </a>
            <button onClick={() => navigate('/docs')} className="btn">
              [ Docs ]
            </button>
            <button onClick={() => navigate('/playground')} className="btn btn-primary">
              [ Get Started ]
            </button>
          </div>
        </section>

        {/* Terminal Demo */}
        <section className="section">
          <TerminalDemo />
        </section>

        {/* Features */}
        <section className="section">
          <SectionDivider label="features" />
          <div className="features-list">
            {FEATURES.map((f, i) => (
              <div key={i} className="feature-item">
                <div className="feature-name">&gt; {f.name}</div>
                <div className="feature-desc">{f.desc}</div>
              </div>
            ))}
          </div>
        </section>

        {/* Code Example */}
        <section className="section">
          <SectionDivider label="example" />
          <CodeExample />
        </section>

        {/* Attention Heatmap */}
        <section className="section">
          <SectionDivider label="attention heatmap" />
          <AttentionHeatmapDemo />
        </section>

        {/* Quickstart */}
        <section className="section">
          <SectionDivider label="quickstart" />
          <QuickstartBlock />
        </section>
      </div>
    </>
  )
}
