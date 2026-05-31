import { useNavigate } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'

const ASCII_LOGO = `                           _
 ___ ___ __ _ _  _ ___ _ _| |_
(_-</ -_) _\` | || / -_) ' \\  _|
/__/\\___\\__, |\\_,_\\___|_||_\\__|
           |_|                  `

const GLITCH_CHARS = '░▒▓█▄▀▐▌╳╱╲'

function GlitchAscii() {
  const [text, setText] = useState(ASCII_LOGO)
  const [scanLine, setScanLine] = useState(-1)
  const original = useRef(ASCII_LOGO)

  useEffect(() => {
    const tick = () => {
      const chars = original.current.split('')
      // Pick 4-8 random non-space positions to glitch
      const count = 4 + Math.floor(Math.random() * 5)
      const indices = []
      for (let n = 0; n < count; n++) {
        let idx
        let tries = 0
        do {
          idx = Math.floor(Math.random() * chars.length)
          tries++
        } while ((chars[idx] === ' ' || chars[idx] === '\n') && tries < 20)
        if (tries < 20) indices.push(idx)
      }
      indices.forEach(idx => {
        chars[idx] = GLITCH_CHARS[Math.floor(Math.random() * GLITCH_CHARS.length)]
      })
      setText(chars.join(''))

      // Flash a white scan line across a random row
      const lines = original.current.split('\n')
      const randomRow = Math.floor(Math.random() * lines.length)
      setScanLine(randomRow)

      // Snap back after brief flash
      setTimeout(() => {
        setText(original.current)
        setScanLine(-1)
      }, 100)
    }

    const interval = setInterval(tick, 1800 + Math.random() * 1200)
    return () => clearInterval(interval)
  }, [])

  const lines = text.split('\n')

  return (
    <pre className="hero-ascii" style={{ position: 'relative', overflow: 'hidden' }}>
      {lines.map((line, i) => (
        <div
          key={i}
          style={{
            position: 'relative',
            background: scanLine === i ? 'rgba(255,255,255,0.12)' : 'transparent',
            boxShadow: scanLine === i ? '0 0 12px rgba(255,255,255,0.15)' : 'none',
            transition: 'none',
          }}
        >
          {line}
        </div>
      ))}
    </pre>
  )
}

const TERMINAL_LINES = [
  { type: 'cmd', text: '$ sequent verify auth.py' },
  { type: 'blank' },
  { type: 'pass', text: '  ✓ verify login()          ·················· PASS' },
  { type: 'pass', text: '  ✓ verify hash_password()  ·················· PASS' },
  { type: 'fail', text: '  ✗ verify token_refresh()  ·················· FAIL' },
  { type: 'blank' },
  { type: 'muted', text: '    counterexample found:' },
  { type: 'muted', text: '      token_refresh(exp=0, iat=-1)' },
  { type: 'muted', text: '      → expected: TokenError' },
  { type: 'fail-dim', text: '      → got:      Token(exp=0)' },
  { type: 'blank' },
  { type: 'purple', text: '    neural confidence: 0.94' },
  { type: 'cyan', text: '    symbolic proof:    incomplete (2/3 branches)' },
  { type: 'blank' },
  { type: 'muted', text: '  3 functions | 2 passed | 1 failed | 1.2s' },
]

const FEATURES = [
  {
    name: 'neurosymbolic verification',
    desc: 'GATv2 graph neural network reads your AST. Z3 SMT solver proves properties. neural proposes, formal disposes.',
  },
  {
    name: 'counterexample generation',
    desc: "when verification fails, sequent doesn't just say \"wrong\" — it gives you the exact inputs that break your function.",
  },
  {
    name: 'auto-repair',
    desc: 'detects the bug class, generates a fix, re-verifies the patch through Z3. if the proof passes, the repair ships.',
  },
  {
    name: '7 bug classes',
    desc: 'off-by-one, boundary errors, wrong operators, None derefs, integer overflow, missing returns, wrong initializations.',
  },
  {
    name: 'proof certificates',
    desc: 'export a JSON certificate with every property checked, every counterexample found. CI-friendly exit codes.',
  },
]

const CODE_LEFT = `def divide(a: int,
           b: int) -> float:
    return a / b`

const CODE_RIGHT = `✓ divide()
  precondition: b != 0
  postcondition: ∀a,b.
    result * b ≈ a
  status: VERIFIED
  proof: complete (SMT)`

const COLOR_MAP = {
  cmd: 'var(--text-primary)',
  pass: 'var(--accent-2)',
  fail: 'var(--accent-3)',
  'fail-dim': 'var(--accent-3)',
  muted: 'var(--text-muted)',
  purple: 'var(--accent-4)',
  cyan: 'var(--accent-5)',
}

// ── Canvas background: dot grid with mouse proximity glow ──
function DotGrid() {
  const canvasRef = useRef(null)
  const mouse = useRef({ clientX: -1000, clientY: -1000 })

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    let animId

    const SPACING = 35
    const DOT_RADIUS = 1
    const GLOW_RADIUS = 180
    const BASE_OPACITY = 0.06

    const resize = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
    }
    resize()
    window.addEventListener('resize', resize)

    const onMouseMove = (e) => {
      mouse.current.clientX = e.clientX
      mouse.current.clientY = e.clientY
    }
    window.addEventListener('mousemove', onMouseMove)

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      const mx = mouse.current.clientX
      const my = mouse.current.clientY

      const cols = Math.ceil(canvas.width / SPACING) + 1
      const rows = Math.ceil(canvas.height / SPACING) + 1

      for (let row = 0; row < rows; row++) {
        const y = row * SPACING
        for (let col = 0; col < cols; col++) {
          const x = col * SPACING

          const dx = x - mx
          const dy = y - my

          const dist = Math.sqrt(dx * dx + dy * dy)

          let opacity = BASE_OPACITY
          let radius = DOT_RADIUS
          let r = 99, g = 109, b = 166 // base muted blue

          if (dist < GLOW_RADIUS) {
            const t = 1 - dist / GLOW_RADIUS
            const ease = t * t
            opacity = BASE_OPACITY + ease * 0.5
            radius = DOT_RADIUS + ease * 1.5
            // Blend toward rusty orange as proximity increases
            r = Math.round(99 + (196 - 99) * ease)
            g = Math.round(109 + (101 - 109) * ease)
            b = Math.round(166 + (58 - 166) * ease)
          }

          ctx.beginPath()
          ctx.arc(x, y, radius, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${opacity})`
          ctx.fill()
        }
      }

      animId = requestAnimationFrame(draw)
    }
    draw()

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', resize)
      window.removeEventListener('mousemove', onMouseMove)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{
        position: 'fixed',
        inset: 0,
        pointerEvents: 'none',
        zIndex: 0,
      }}
    />
  )
}

// ── Line numbers in left margin ──
function LineNumbers() {
  const [count, setCount] = useState(80)

  useEffect(() => {
    const update = () => {
      const h = document.documentElement.scrollHeight
      const lineH = 20
      setCount(Math.ceil(h / lineH))
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

// ── Vim statusline ──
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
      -- NORMAL --  sequent.md  {ln}:1  ⊢
    </div>
  )
}

// ── Terminal demo with typing animation ──
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

export default function Landing() {
  const navigate = useNavigate()
  const [copied, setCopied] = useState(false)

  return (
    <>
      <DotGrid />
      <LineNumbers />
      <StatusLine />

      <div className="landing-container">
        {/* ── Hero ── */}
        <section className="hero">
          <GlitchAscii />
          <p className="hero-subtitle">neural formal verification engine</p>
          <p className="hero-tagline">
            neurosymbolic python debugger that proves<br />
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
              {copied ? 'copied!' : 'copy'}
            </button>
          </div>

          <div className="hero-actions">
            <button onClick={() => navigate('/playground')} className="btn btn-primary">
              [ Playground ]
            </button>
            <button onClick={() => navigate('/docs')} className="btn btn-secondary">
              [ Docs ]
            </button>
            <a
              href="https://github.com/devangpratapsingh/sequent"
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-secondary"
            >
              [ GitHub ]
            </a>
          </div>
        </section>

        {/* ── Terminal Demo ── */}
        <section className="section">
          <TerminalDemo />
        </section>

        {/* ── Features ── */}
        <section className="section">
          <div className="section-heading">features</div>
          <div className="features-list">
            {FEATURES.map((f, i) => (
              <div key={i} className="feature-item">
                <div className="feature-name">▸ {f.name}</div>
                <div className="feature-desc">{f.desc}</div>
              </div>
            ))}
          </div>
        </section>

        {/* ── Code Example ── */}
        <section className="section">
          <div className="section-heading">example</div>
          <div className="code-split">
            <div className="code-panel">
              <div className="code-panel-header">your code</div>
              <pre className="code-panel-body code-python">{CODE_LEFT}</pre>
            </div>
            <div className="code-panel">
              <div className="code-panel-header">sequent output</div>
              <pre className="code-panel-body code-output">{CODE_RIGHT}</pre>
            </div>
          </div>
        </section>

        {/* ── Quickstart ── */}
        <section className="section">
          <div className="section-heading">quickstart</div>
          <div className="quickstart-block">
            <div><span className="prompt">$ </span>pip install sequent</div>
            <div><span className="prompt">$ </span>cd your-project</div>
            <div><span className="prompt">$ </span>sequent verify main.py</div>
            <div className="quickstart-end">that's it.</div>
          </div>
        </section>

        {/* ── How it works ── */}
        <section className="section">
          <div className="section-heading">how it works</div>
          <div className="arch-grid">
            <div className="arch-card">
              <div className="arch-label" style={{ color: 'var(--accent-4)' }}>GATv2</div>
              <div className="arch-desc">graph attention network reads your Python AST</div>
            </div>
            <div className="arch-card">
              <div className="arch-label" style={{ color: 'var(--accent-5)' }}>Z3</div>
              <div className="arch-desc">SMT solver formally verifies 8 property classes</div>
            </div>
            <div className="arch-card">
              <div className="arch-label" style={{ color: 'var(--accent-2)' }}>Consensus</div>
              <div className="arch-desc">neurosymbolic vote merges neural + symbolic</div>
            </div>
          </div>
        </section>
      </div>
    </>
  )
}
