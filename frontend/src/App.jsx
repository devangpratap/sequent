import { useState, useCallback } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { python } from '@codemirror/lang-python'
import { EditorView } from '@codemirror/view'

const API_BASE = '/api'

const EXAMPLE_BUGGY = `def binary_search(arr, target):
    low = 0
    high = len(arr) - 1
    while low < high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1`

const EXAMPLE_CORRECT = `def binary_search(arr, target):
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
    return -1`

const EXAMPLE_NONE = `def find_max(arr):
    max_val = arr[0]
    for i in range(1, len(arr)):
        if arr[i] > max_val:
            max_val = arr[i]
    return max_val`

const darkTheme = EditorView.theme({
  '&': { backgroundColor: '#12121a' },
  '.cm-content': { caretColor: '#4f8fff' },
  '.cm-cursor': { borderLeftColor: '#4f8fff' },
  '&.cm-focused .cm-selectionBackground, .cm-selectionBackground': {
    backgroundColor: 'rgba(79, 143, 255, 0.2)',
  },
})

function App() {
  const [code, setCode] = useState(EXAMPLE_BUGGY)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [stage, setStage] = useState(null) // 'gnn' | 'z3' | 'repair' | 'done'

  const analyze = useCallback(async () => {
    if (!code.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)

    // Animate stages
    setStage('gnn')
    await sleep(400)
    setStage('z3')

    try {
      const res = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, function_name: '' }),
      })

      if (!res.ok) {
        throw new Error(`Server error: ${res.status}`)
      }

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

  const getLineHeatmap = useCallback(() => {
    if (!result?.node_scores || !result?.node_lines) return {}
    const lineScores = {}
    result.node_lines.forEach((line, i) => {
      if (line > 0) {
        lineScores[line] = Math.max(lineScores[line] || 0, result.node_scores[i])
      }
    })
    return lineScores
  }, [result])

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-[#2a2a3e] px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#4f8fff] to-[#a855f7] flex items-center justify-center font-bold text-sm">P</div>
            <h1 className="text-xl font-semibold tracking-tight">Prova</h1>
            <span className="text-xs text-[#555570] border border-[#2a2a3e] rounded px-2 py-0.5">v0.1</span>
          </div>
          <p className="text-sm text-[#8888a0]">Neural Formal Verification Engine</p>
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto w-full p-6">
        {/* Example buttons + Verify */}
        <div className="flex items-center gap-2 mb-4">
          <span className="text-xs text-[#8888a0] mr-2">examples:</span>
          <button onClick={() => { setCode(EXAMPLE_BUGGY); setResult(null); }} className="text-xs px-3 py-1.5 bg-[#1a1a2e] border border-[#2a2a3e] text-[#ff4f6f] hover:border-[#ff4f6f] transition-colors">[ off-by-one ]</button>
          <button onClick={() => { setCode(EXAMPLE_NONE); setResult(null); }} className="text-xs px-3 py-1.5 bg-[#1a1a2e] border border-[#2a2a3e] text-[#ffc84f] hover:border-[#ffc84f] transition-colors">[ none deref ]</button>
          <button onClick={() => { setCode(EXAMPLE_CORRECT); setResult(null); }} className="text-xs px-3 py-1.5 bg-[#1a1a2e] border border-[#2a2a3e] text-[#00e88f] hover:border-[#00e88f] transition-colors">[ correct ]</button>
          <button
            onClick={analyze}
            disabled={loading}
            className={`text-xs px-4 py-1.5 ml-auto font-medium transition-all ${
              loading
                ? 'bg-[#2a2a3e] text-[#555570] cursor-wait border border-[#2a2a3e]'
                : 'border border-[var(--accent-4)] text-[var(--accent-4)] hover:bg-[rgba(187,154,247,0.08)]'
            }`}
            style={{ fontFamily: 'inherit' }}
          >
            {loading ? '[ verifying... ]' : '[ verify ]'}
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          {/* Left: Code Editor */}
          <div className="flex flex-col">
            <h2 className="text-xs text-[#8888a0] uppercase tracking-wider mb-3">input</h2>

            <div className="border border-[#2a2a3e] overflow-hidden flex-1 min-h-[400px]">
              <CodeMirror
                value={code}
                onChange={setCode}
                extensions={[python(), darkTheme]}
                basicSetup={{
                  lineNumbers: true,
                  highlightActiveLineGutter: true,
                  foldGutter: false,
                }}
                height="100%"
                minHeight="400px"
              />
            </div>
          </div>

          {/* Right: Results */}
          <div className="flex flex-col">
            <h2 className="text-xs text-[#8888a0] uppercase tracking-wider mb-3">analysis</h2>

            {/* Pipeline stages */}
            {loading && <PipelineStages stage={stage} />}

            {error && (
              <div className="p-4 rounded-lg bg-[#ff4f6f]/10 border border-[#ff4f6f]/30 text-[#ff4f6f] text-sm">
                {error}
              </div>
            )}

            {result && <ResultPanel result={result} lineHeatmap={getLineHeatmap()} />}

            {!result && !loading && !error && (
              <div className="flex-1 flex items-center justify-center border border-dashed border-[#2a2a3e] rounded-lg">
                <div className="text-center">
                  <div className="text-4xl mb-3 opacity-20">&#123; &#125;</div>
                  <p className="text-[#555570] text-sm">Paste a Python function and click Verify</p>
                  <p className="text-[#3a3a50] text-xs mt-1">GNN proposes, Z3 disposes</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Heatmap visualization */}
        {result && result.node_scores && (
          <div className="mt-6 animate-slide-up" style={{ animationDelay: '0.3s', opacity: 0 }}>
            <HeatmapPanel result={result} code={code} />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-[#2a2a3e] px-6 py-3 mt-auto">
        <div className="max-w-7xl mx-auto flex justify-between text-xs text-[#555570]">
          <span>Prova — Neurosymbolic Verification</span>
          <span>GNN + Z3 SMT Solver</span>
        </div>
      </footer>
    </div>
  )
}

function PipelineStages({ stage }) {
  const stages = [
    { id: 'gnn', label: 'GNN Inference', desc: 'Graph neural network analyzing AST...' },
    { id: 'z3', label: 'Z3 Verification', desc: 'SMT solver checking properties...' },
    { id: 'repair', label: 'Auto-Repair', desc: 'Generating and verifying fix...' },
    { id: 'done', label: 'Complete', desc: 'Analysis complete' },
  ]

  const currentIdx = stages.findIndex(s => s.id === stage)

  return (
    <div className="space-y-2 mb-4">
      {stages.map((s, i) => {
        const isActive = s.id === stage
        const isDone = i < currentIdx
        const isPending = i > currentIdx

        return (
          <div key={s.id} className={`flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all ${
            isActive ? 'bg-[#4f8fff]/10 border border-[#4f8fff]/30' :
            isDone ? 'bg-[#00e88f]/5 border border-[#00e88f]/20' :
            'bg-[#1a1a2e]/50 border border-transparent'
          }`}>
            <div className={`w-5 h-5 rounded-full flex items-center justify-center text-xs ${
              isDone ? 'bg-[#00e88f] text-black' :
              isActive ? 'bg-[#4f8fff] text-white animate-pulse' :
              'bg-[#2a2a3e] text-[#555570]'
            }`}>
              {isDone ? '\u2713' : i + 1}
            </div>
            <div>
              <p className={`text-sm font-medium ${isActive ? 'text-[#4f8fff]' : isDone ? 'text-[#00e88f]' : 'text-[#555570]'}`}>{s.label}</p>
              {isActive && <p className="text-xs text-[#8888a0] mt-0.5">{s.desc}</p>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function ResultPanel({ result, lineHeatmap }) {
  const isBuggy = result.is_buggy

  return (
    <div className="space-y-4 animate-slide-up">
      {/* Verdict */}
      <div className={`p-4 rounded-lg border ${
        isBuggy
          ? 'bg-[#ff4f6f]/10 border-[#ff4f6f]/30'
          : 'bg-[#00e88f]/10 border-[#00e88f]/30'
      }`}>
        <div className="flex items-center gap-2 mb-2">
          <span className="text-lg">{isBuggy ? '\u26A0' : '\u2713'}</span>
          <span className={`font-semibold ${isBuggy ? 'text-[#ff4f6f]' : 'text-[#00e88f]'}`}>
            {isBuggy ? 'Bug Detected' : 'Verified Correct'}
          </span>
          <span className="text-xs text-[#8888a0] ml-auto">{result.total_time_ms}ms</span>
        </div>
        <p className="text-sm text-[#ccccdd]">{result.consensus}</p>
      </div>

      {/* GNN Results */}
      {result.gnn && (
        <div className="p-4 rounded-lg bg-[#1a1a2e] border border-[#2a2a3e]">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-[#a855f7]/20 text-[#a855f7]">GNN</span>
            <span className="text-sm font-medium">Neural Bug Predictor</span>
            <span className="text-xs text-[#555570] ml-auto">{result.gnn.inference_ms}ms</span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Stat label="Prediction" value={result.gnn.buggy ? 'Buggy' : 'Clean'} color={result.gnn.buggy ? '#ff4f6f' : '#00e88f'} />
            <Stat label="Confidence" value={`${(result.gnn.confidence * 100).toFixed(1)}%`} color="#4f8fff" />
            {result.gnn.bug_lines.length > 0 && (
              <Stat label="Suspect Lines" value={result.gnn.bug_lines.join(', ')} color="#ffc84f" />
            )}
          </div>
        </div>
      )}

      {/* Z3 Results */}
      {result.z3 && (
        <div className="p-4 rounded-lg bg-[#1a1a2e] border border-[#2a2a3e]">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-[#4f8fff]/20 text-[#4f8fff]">Z3</span>
            <span className="text-sm font-medium">Formal Verification</span>
            <span className="text-xs text-[#555570] ml-auto">{result.z3.time_ms}ms</span>
          </div>
          <div className="space-y-2">
            {result.z3.checks.map((check, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                <span className={`mt-0.5 text-xs ${
                  check.result === 'verified' ? 'text-[#00e88f]' :
                  check.result === 'counterexample' ? 'text-[#ff4f6f]' : 'text-[#ffc84f]'
                }`}>
                  {check.result === 'verified' ? '\u2713' : check.result === 'counterexample' ? '\u2717' : '?'}
                </span>
                <div className="flex-1">
                  <span className="font-mono text-xs text-[#8888a0]">{check.property_name}</span>
                  <p className="text-[#ccccdd] text-xs mt-0.5">{check.description}</p>
                  {check.counterexample && (
                    <pre className="mt-1 text-xs font-mono bg-[#0a0a0f] rounded px-2 py-1 text-[#ff4f6f]">
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
        <div className="p-4 rounded-lg bg-[#1a1a2e] border border-[#2a2a3e]">
          <div className="flex items-center gap-2 mb-3">
            <span className={`text-xs font-mono px-2 py-0.5 rounded ${
              result.repair.verified
                ? 'bg-[#00e88f]/20 text-[#00e88f]'
                : 'bg-[#ffc84f]/20 text-[#ffc84f]'
            }`}>REPAIR</span>
            <span className="text-sm font-medium">Auto-Repair</span>
            {result.repair.verified && <span className="text-xs text-[#00e88f] ml-auto">Re-verified</span>}
          </div>
          <p className="text-sm text-[#ccccdd] mb-2">{result.repair.description}</p>
          {result.repair.repaired_code && (
            <div className="rounded-lg overflow-hidden border border-[#2a2a3e]">
              <div className="px-3 py-1.5 bg-[#0a0a0f] text-xs text-[#00e88f] font-mono">Fixed code</div>
              <CodeMirror
                value={result.repair.repaired_code}
                extensions={[python(), darkTheme]}
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

  return (
    <div className="p-4 rounded-lg bg-[#1a1a2e] border border-[#2a2a3e]">
      <h3 className="text-sm font-medium text-[#8888a0] uppercase tracking-wider mb-3">GNN Confidence Heatmap</h3>
      <p className="text-xs text-[#555570] mb-3">Node-level bug probability overlaid on source code. Redder = higher suspicion.</p>
      <div className="font-mono text-xs rounded-lg overflow-hidden bg-[#0a0a0f] p-3">
        {lines.map((line, i) => {
          const lineNum = i + 1
          const score = lineScores[lineNum] || 0
          const r = Math.round(score * 255)
          const g = Math.round((1 - score) * 40)
          const b = Math.round((1 - score) * 60)
          const bgOpacity = Math.max(score * 0.4, 0)

          return (
            <div
              key={i}
              className="flex items-center gap-3 py-0.5 px-2 rounded"
              style={{ backgroundColor: score > 0.1 ? `rgba(${r}, ${g}, ${b}, ${bgOpacity})` : 'transparent' }}
            >
              <span className="text-[#555570] w-6 text-right select-none">{lineNum}</span>
              <span className="flex-1 whitespace-pre">{line || ' '}</span>
              {score > 0.1 && (
                <span className="w-16 text-right" style={{ color: `rgb(${r}, ${Math.max(g, 100)}, ${Math.max(b, 100)})` }}>
                  {(score * 100).toFixed(1)}%
                </span>
              )}
              {score > 0.1 && (
                <div className="w-16 h-1.5 rounded-full bg-[#2a2a3e] overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${score * 100}%`,
                      backgroundColor: `rgb(${r}, ${Math.max(g, 80)}, ${Math.max(b, 80)})`,
                    }}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function Stat({ label, value, color }) {
  return (
    <div className="bg-[#0a0a0f] rounded-lg p-3">
      <p className="text-xs text-[#555570] mb-1">{label}</p>
      <p className="text-sm font-semibold font-mono" style={{ color }}>{value}</p>
    </div>
  )
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

export default App
