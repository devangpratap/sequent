import { useState, useCallback } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { python } from '@codemirror/lang-python'
import { EditorView } from '@codemirror/view'

const API_BASE = '/api'

const EXAMPLES = [
  {
    label: 'off-by-one',
    color: 'var(--accent-3)',
    code: `def binary_search(arr, target):
    low = 0
    high = len(arr) - 1
    while low < high:  # BUG: should be <=
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1`,
  },
  {
    label: 'none deref',
    color: '#e0af68',
    code: `def find_max(arr):
    max_val = arr[0]  # BUG: no None/empty check
    for i in range(1, len(arr)):
        if arr[i] > max_val:
            max_val = arr[i]
    return max_val`,
  },
  {
    label: 'correct',
    color: 'var(--accent-2)',
    code: `def binary_search(arr, target):
    if arr is None or len(arr) == 0:
        return -1
    low = 0
    high = len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1`,
  },
]

const editorTheme = EditorView.theme({
  '&': { backgroundColor: 'var(--bg-deep)' },
  '.cm-content': { caretColor: 'var(--accent-4)' },
  '.cm-cursor': { borderLeftColor: 'var(--accent-4)' },
  '&.cm-focused .cm-selectionBackground, .cm-selectionBackground': {
    backgroundColor: 'rgba(187, 154, 247, 0.15)',
  },
})

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function scoreToColor(score) {
  // Gradient: low = cool blue/green, high = hot red/orange
  if (score < 0.3) {
    const t = score / 0.3
    return { r: Math.round(30 + t * 50), g: Math.round(180 - t * 80), b: Math.round(220 - t * 120) }
  } else if (score < 0.6) {
    const t = (score - 0.3) / 0.3
    return { r: Math.round(80 + t * 175), g: Math.round(100 + t * 50), b: Math.round(100 - t * 80) }
  } else {
    const t = (score - 0.6) / 0.4
    return { r: 255, g: Math.round(150 - t * 120), b: Math.round(20 - t * 20) }
  }
}

export default function Playground() {
  const [code, setCode] = useState(EXAMPLES[0].code)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [stage, setStage] = useState(null)

  const analyze = useCallback(async () => {
    if (!code.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)

    setStage('gnn')
    await sleep(400)
    setStage('z3')

    try {
      const res = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, function_name: '' }),
      })

      if (!res.ok) throw new Error(`Server error: ${res.status}`)

      const data = await res.json()
      setStage(data.repair ? 'repair' : 'done')
      await sleep(300)
      setStage('done')
      setResult(data)
    } catch (err) {
      setError(err.message)
      setStage(null)
    } finally {
      setLoading(false)
    }
  }, [code])

  return (
    <div style={{ maxWidth: '72rem', margin: '0 auto', padding: '2rem 1.5rem' }}>
      {/* Examples */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>examples:</span>
        {EXAMPLES.map((ex, i) => (
          <button
            key={i}
            onClick={() => { setCode(ex.code); setResult(null); setError(null); }}
            style={{
              fontSize: '0.75rem', padding: '0.3rem 0.75rem',
              border: '1px solid var(--border)', background: 'transparent',
              color: ex.color, cursor: 'pointer', fontFamily: 'inherit',
              transition: 'border-color 0.15s',
              textShadow: '0 0 5px rgba(196,101,58,0.3)',
            }}
          >
            [ {ex.label} ]
          </button>
        ))}
      </div>

      {/* Labels + verify row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '0.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', textShadow: '0 0 5px rgba(196,101,58,0.3)' }}>input</span>
          <button
            onClick={analyze}
            disabled={loading}
            style={{
              padding: '0.4rem 1rem', fontSize: '0.75rem', fontFamily: 'inherit',
              border: loading ? '1px solid var(--border)' : '1px solid var(--accent-4)',
              color: loading ? 'var(--text-muted)' : 'var(--accent-4)',
              background: 'transparent', cursor: loading ? 'wait' : 'pointer',
              transition: 'all 0.15s',
              textShadow: '0 0 5px rgba(196,101,58,0.3)',
            }}
          >
            {loading ? '[ analyzing... ]' : '[ verify ]'}
          </button>
        </div>
        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', display: 'flex', alignItems: 'center', textShadow: '0 0 5px rgba(196,101,58,0.3)' }}>analysis</span>
      </div>

      {/* Main Grid — both boxes start at the same line */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
        {/* Editor */}
        <div style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)', minHeight: '450px' }}>
          <CodeMirror
            value={code}
            onChange={setCode}
            extensions={[python(), editorTheme]}
            basicSetup={{ lineNumbers: true, highlightActiveLineGutter: true, foldGutter: false }}
            height="100%"
            minHeight="450px"
          />
        </div>

        {/* Results */}
        <div style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)', minHeight: '450px', overflowY: 'auto', padding: '1.25rem' }}>
            {loading && <PipelineStages stage={stage} />}

            {error && (
              <div style={{ padding: '1rem', border: '1px solid rgba(247,118,142,0.3)', background: 'rgba(247,118,142,0.05)', color: 'var(--accent-3)', fontSize: '0.8rem' }}>
                {error}
              </div>
            )}

            {result && <ResultPanel result={result} />}

            {!result && !loading && !error && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '380px' }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '2.5rem', marginBottom: '1rem', color: 'var(--text-muted)', opacity: 0.2 }}>{'{ }'}</div>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>paste python, click verify</p>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.7rem', marginTop: '0.5rem', opacity: 0.5 }}>GNN proposes, Z3 disposes</p>
                </div>
              </div>
            )}
        </div>
      </div>

      {/* Heatmap — full width below */}
      {result && result.node_scores && (
        <div style={{ marginTop: '2rem' }}>
          <HeatmapPanel result={result} code={code} />
        </div>
      )}
    </div>
  )
}

function PipelineStages({ stage }) {
  const stages = [
    { id: 'gnn', label: 'GNN inference', color: 'var(--accent-4)' },
    { id: 'z3', label: 'Z3 verification', color: 'var(--accent-5)' },
    { id: 'repair', label: 'auto-repair', color: '#e0af68' },
    { id: 'done', label: 'complete', color: 'var(--accent-2)' },
  ]

  const currentIdx = stages.findIndex(s => s.id === stage)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginBottom: '1rem' }}>
      {stages.map((s, i) => {
        const isActive = s.id === stage
        const isDone = i < currentIdx
        const isPending = !isActive && !isDone

        return (
          <div
            key={s.id}
            style={{
              display: 'flex', alignItems: 'center', gap: '0.5rem',
              padding: '0.5rem 0.75rem', fontSize: '0.8rem',
              border: isActive ? `1px solid ${s.color}` : isDone ? '1px solid rgba(158,206,106,0.2)' : '1px solid transparent',
              color: isActive ? s.color : isDone ? 'var(--accent-2)' : 'var(--text-muted)',
              opacity: isPending ? 0.3 : 1,
              transition: 'all 0.2s',
            }}
          >
            <span>{isDone ? '✓' : isActive ? '▸' : '·'}</span>
            <span>{s.label}</span>
            {isActive && <span style={{ marginLeft: 'auto', animation: 'blink 1s step-end infinite' }}>█</span>}
          </div>
        )
      })}
    </div>
  )
}

function ResultPanel({ result }) {
  const isBuggy = result.is_buggy

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Verdict */}
      <div style={{
        padding: '1.25rem',
        border: `1px solid ${isBuggy ? 'rgba(247,118,142,0.3)' : 'rgba(158,206,106,0.3)'}`,
        background: isBuggy ? 'rgba(247,118,142,0.05)' : 'rgba(158,206,106,0.05)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
          <span style={{ fontSize: '1rem', fontWeight: 700, color: isBuggy ? 'var(--accent-3)' : 'var(--accent-2)' }}>
            {isBuggy ? '✗ BUG DETECTED' : '✓ VERIFIED CORRECT'}
          </span>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{result.total_time_ms}ms</span>
        </div>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-primary)', lineHeight: 1.5 }}>{result.consensus}</p>
      </div>

      {/* GNN */}
      {result.gnn && (
        <div style={{ padding: '1.25rem', border: '1px solid var(--border)', background: 'var(--bg-deep)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.5rem', border: '1px solid rgba(187,154,247,0.3)', color: 'var(--accent-4)' }}>GNN</span>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>neural bug predictor</span>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>{result.gnn.inference_ms}ms</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            <Stat label="prediction" value={result.gnn.buggy ? 'BUGGY' : 'CLEAN'} color={result.gnn.buggy ? 'var(--accent-3)' : 'var(--accent-2)'} />
            <Stat label="confidence" value={`${(result.gnn.confidence * 100).toFixed(1)}%`} color="var(--accent-4)" />
            {result.gnn.bug_lines?.length > 0 && (
              <Stat label="suspect lines" value={result.gnn.bug_lines.join(', ')} color="#e0af68" />
            )}
          </div>
        </div>
      )}

      {/* Z3 */}
      {result.z3 && (
        <div style={{ padding: '1.25rem', border: '1px solid var(--border)', background: 'var(--bg-deep)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.5rem', border: '1px solid rgba(125,207,255,0.3)', color: 'var(--accent-5)' }}>Z3</span>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>formal verification</span>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>{result.z3.time_ms}ms</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {result.z3.checks.map((check, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
                <span style={{
                  marginTop: '0.15rem', fontSize: '0.8rem',
                  color: check.result === 'verified' ? 'var(--accent-2)' : check.result === 'counterexample' ? 'var(--accent-3)' : '#e0af68',
                }}>
                  {check.result === 'verified' ? '✓' : check.result === 'counterexample' ? '✗' : '?'}
                </span>
                <div style={{ flex: 1 }}>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{check.property_name}</span>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-primary)', marginTop: '0.2rem' }}>{check.description}</p>
                  {check.counterexample && (
                    <pre style={{
                      marginTop: '0.4rem', fontSize: '0.7rem',
                      background: 'var(--bg-surface)', border: '1px solid var(--border)',
                      padding: '0.4rem 0.6rem', color: 'var(--accent-3)', margin: '0.4rem 0 0 0',
                    }}>
                      {JSON.stringify(check.counterexample)}
                    </pre>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Repair */}
      {result.repair && (
        <div style={{ padding: '1.25rem', border: '1px solid var(--border)', background: 'var(--bg-deep)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <span style={{
              fontSize: '0.7rem', padding: '0.15rem 0.5rem',
              border: result.repair.verified ? '1px solid rgba(158,206,106,0.3)' : '1px solid rgba(224,175,104,0.3)',
              color: result.repair.verified ? 'var(--accent-2)' : '#e0af68',
            }}>REPAIR</span>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>auto-repair</span>
            {result.repair.verified && <span style={{ fontSize: '0.7rem', color: 'var(--accent-2)', marginLeft: 'auto' }}>re-verified ✓</span>}
          </div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-primary)', marginBottom: '0.75rem' }}>{result.repair.description}</p>
          {result.repair.repaired_code && (
            <div style={{ border: '1px solid var(--border)' }}>
              <div style={{ padding: '0.3rem 0.75rem', background: 'var(--bg-surface)', fontSize: '0.7rem', color: 'var(--accent-2)', borderBottom: '1px solid var(--border)' }}>fixed code</div>
              <CodeMirror
                value={result.repair.repaired_code}
                extensions={[python(), editorTheme]}
                editable={false}
                basicSetup={{ lineNumbers: true, foldGutter: false }}
                maxHeight="200px"
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function HeatmapPanel({ result, code }) {
  const lines = code.split('\n')
  const lineScores = {}
  if (result.node_lines && result.node_scores) {
    result.node_lines.forEach((line, i) => {
      if (line > 0) {
        lineScores[line] = Math.max(lineScores[line] || 0, result.node_scores[i])
      }
    })
  }

  const maxScore = Math.max(...Object.values(lineScores), 0.01)

  return (
    <div style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1rem 1.25rem', borderBottom: '1px solid var(--border)' }}>
        <div>
          <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.25rem', textShadow: '0 0 5px rgba(196,101,58,0.35), 0 0 14px rgba(196,101,58,0.15)' }}>
            GNN Confidence Heatmap
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            node-level bug probability overlaid on source — warmer = higher suspicion
          </div>
        </div>
        {/* Legend */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>0%</span>
          <div style={{
            width: '8rem', height: '0.5rem',
            background: 'linear-gradient(90deg, rgba(30,180,220,0.6), rgba(80,100,100,0.6), rgba(255,150,20,0.8), rgba(255,30,0,0.9))',
            borderRadius: '2px',
          }} />
          <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>100%</span>
        </div>
      </div>

      {/* Code lines */}
      <div style={{ padding: '0.75rem 0', fontSize: '0.8rem' }}>
        {lines.map((line, i) => {
          const lineNum = i + 1
          const score = lineScores[lineNum] || 0
          const { r, g, b } = scoreToColor(score)
          const intensity = score / maxScore

          return (
            <div
              key={i}
              style={{
                display: 'flex', alignItems: 'center',
                padding: '0.3rem 1.25rem',
                background: score > 0.05 ? `rgba(${r}, ${g}, ${b}, ${Math.min(intensity * 0.2, 0.25)})` : 'transparent',
                borderLeft: score > 0.3 ? `3px solid rgba(${r}, ${g}, ${b}, 0.8)` : '3px solid transparent',
                transition: 'background 0.2s',
              }}
            >
              {/* Line number */}
              <span style={{ width: '2rem', textAlign: 'right', color: 'var(--text-muted)', fontSize: '0.7rem', userSelect: 'none', marginRight: '1rem', flexShrink: 0 }}>
                {lineNum}
              </span>

              {/* Code */}
              <span style={{ flex: 1, whiteSpace: 'pre', fontFamily: 'inherit' }}>
                {line || ' '}
              </span>

              {/* Score bar + percentage */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0, width: '7rem', justifyContent: 'flex-end' }}>
                {score > 0.05 && (
                  <>
                    <div style={{ width: '3.5rem', height: '0.4rem', background: 'var(--bg-deep)', borderRadius: '2px', overflow: 'hidden' }}>
                      <div style={{
                        height: '100%', borderRadius: '2px',
                        width: `${Math.min(score * 100, 100)}%`,
                        background: `rgb(${r}, ${g}, ${b})`,
                        transition: 'width 0.3s',
                      }} />
                    </div>
                    <span style={{ fontSize: '0.65rem', color: `rgb(${r}, ${Math.max(g, 80)}, ${Math.max(b, 80)})`, width: '2.5rem', textAlign: 'right' }}>
                      {(score * 100).toFixed(0)}%
                    </span>
                  </>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function Stat({ label, value, color }) {
  return (
    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', padding: '0.75rem' }}>
      <p style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginBottom: '0.3rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</p>
      <p style={{ fontSize: '0.9rem', fontWeight: 700, color }}>{value}</p>
    </div>
  )
}
