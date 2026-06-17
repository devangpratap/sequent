import { useNavigate } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'

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

        {/* Quickstart */}
        <section className="section">
          <SectionDivider label="quickstart" />
          <QuickstartBlock />
        </section>
      </div>
    </>
  )
}
