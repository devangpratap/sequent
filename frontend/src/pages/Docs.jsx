const SECTIONS = [
  {
    id: 'install',
    title: 'installation',
    content: [
      { type: 'text', value: 'sequent requires Python 3.9+ and a working Z3 installation.' },
      {
        type: 'terminal',
        lines: [
          '$ pip install sequent',
          '$ sequent --version',
          'sequent v0.1.0 (GATv2 10M params, Z3 4.12)',
        ],
      },
      { type: 'text', value: 'For development:' },
      {
        type: 'terminal',
        lines: [
          '$ git clone https://github.com/devangpratapsingh/sequent',
          '$ cd sequent',
          '$ pip install -e ".[dev]"',
        ],
      },
    ],
  },
  {
    id: 'cli',
    title: 'CLI usage',
    content: [
      { type: 'text', value: 'Verify a single file:' },
      {
        type: 'terminal',
        lines: [
          '$ sequent check main.py',
          '',
          '  \u2713 binary_search()    \u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7 PASS',
          '  \u2717 find_max()         \u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7 FAIL',
          '',
          '    counterexample: find_max(arr=[])',
          '    \u2192 IndexError: list index out of range',
        ],
      },
      { type: 'text', value: 'Verify a specific function:' },
      {
        type: 'terminal',
        lines: ['$ sequent check main.py --function binary_search'],
      },
      { type: 'text', value: 'Auto-repair detected bugs:' },
      {
        type: 'terminal',
        lines: [
          '$ sequent check main.py --repair',
          '',
          '  \u2717 find_max()         \u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7 FAIL',
          '  \u26A1 repair: added None/empty guard',
          '  \u2713 re-verified        \u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7\u00B7 PASS',
        ],
      },
      { type: 'text', value: 'Export a proof certificate:' },
      {
        type: 'terminal',
        lines: [
          '$ sequent check main.py --cert report.json',
          '$ cat report.json | jq .summary',
        ],
      },
    ],
  },
  {
    id: 'github-action',
    title: 'GitHub Action',
    content: [
      { type: 'text', value: 'Add to .github/workflows/sequent.yml:' },
      {
        type: 'code',
        lang: 'yaml',
        value: `name: Sequent Verification
on: [push, pull_request]

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install sequent
      - run: sequent check src/ --ci --cert sequent-report.json
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: sequent-report
          path: sequent-report.json`,
      },
      { type: 'text', value: 'The --ci flag uses exit code 1 on any failure, suitable for CI gates.' },
    ],
  },
  {
    id: 'architecture',
    title: 'architecture',
    content: [
      { type: 'text', value: 'Sequent uses a neurosymbolic verification pipeline:' },
      {
        type: 'diagram',
        lines: [
          '\u250C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510    \u250C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510    \u250C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510',
          '\u2502  Python AST  \u2502\u2500\u2500\u2500\u25B8\u2502  GATv2 (10M)  \u2502\u2500\u2500\u2500\u25B8\u2502  Bug Score   \u2502',
          '\u2502  Parser      \u2502    \u2502  8-head GAT   \u2502    \u2502  per node    \u2502',
          '\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518    \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518    \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u252C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518',
          '                                               \u2502',
          '                                               \u25BC',
          '\u250C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510    \u250C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510    \u250C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510',
          '\u2502  Property    \u2502\u2500\u2500\u2500\u25B8\u2502  Z3 SMT       \u2502\u2500\u2500\u2500\u25B8\u2502  Proof /     \u2502',
          '\u2502  Extractor   \u2502    \u2502  Solver       \u2502    \u2502  Counterex.  \u2502',
          '\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518    \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518    \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u252C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518',
          '                                               \u2502',
          '                                               \u25BC',
          '                                        \u250C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510',
          '                                        \u2502  Consensus   \u2502',
          '                                        \u2502  Vote        \u2502',
          '                                        \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518',
        ],
      },
      { type: 'text', value: '1. AST Parser converts Python source into a typed graph with 91 node types.' },
      { type: 'text', value: '2. GATv2 with 8 attention heads and 256 hidden channels classifies each node\'s bug probability.' },
      { type: 'text', value: '3. Z3 SMT Solver checks 8 property classes: bounds, None safety, return completeness, type consistency, overflow, comparison, initialization, loop termination.' },
      { type: 'text', value: '4. Consensus merges neural predictions with formal proofs \u2014 neural proposes, formal disposes.' },
    ],
  },
  {
    id: 'bug-types',
    title: 'supported bug types',
    content: [
      {
        type: 'table',
        headers: ['bug type', 'description', 'example'],
        rows: [
          ['off_by_one', 'Loop bounds off by 1', 'while i < n vs while i <= n'],
          ['boundary_error', 'Array/index out of bounds', 'arr[len(arr)] instead of arr[len(arr)-1]'],
          ['wrong_operator', 'Incorrect comparison/arithmetic', '+ instead of -, < instead of <='],
          ['none_deref', 'Missing null/None checks', 'arr[0] without checking if arr is None'],
          ['integer_overflow', 'Unchecked arithmetic overflow', 'a + b without overflow guard'],
          ['missing_return', 'Missing return in branch', 'Function path returns None implicitly'],
          ['wrong_init', 'Incorrect variable initialization', 'max_val = 0 instead of arr[0]'],
        ],
      },
    ],
  },
  {
    id: 'benchmarks',
    title: 'benchmarks',
    content: [
      { type: 'text', value: 'Trained on 11,099 synthetic mutations from 164 seed functions across 12 categories.' },
      {
        type: 'table',
        headers: ['metric', 'value'],
        rows: [
          ['accuracy', '80.6%'],
          ['precision', '92.8%'],
          ['recall', '~72%'],
          ['F1 score', '82.5%'],
          ['model params', '10M'],
          ['inference time', '<50ms per function'],
          ['training data', '11,099 samples (7 bug types)'],
          ['seed functions', '164 across 12 categories'],
        ],
      },
      { type: 'text', value: 'Seed-level train/test split ensures no data leakage between training and evaluation.' },
    ],
  },
  {
    id: 'api',
    title: 'web API',
    content: [
      { type: 'text', value: 'The web API exposes a single endpoint for analysis:' },
      {
        type: 'code',
        lang: 'bash',
        value: `curl -X POST http://localhost:8000/api/analyze \\
  -H "Content-Type: application/json" \\
  -d '{"code": "def f(x): return x + 1", "function_name": "f"}'`,
      },
      { type: 'text', value: 'Response includes GNN predictions, Z3 verification results, counterexamples, and optional auto-repair.' },
    ],
  },
]

export default function Docs() {
  return (
    <div style={{ maxWidth: '52rem', margin: '0 auto', padding: '3rem 1.5rem' }}>
      <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
        <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '0.03em', marginBottom: '0.5rem', textShadow: '0 0 5px rgba(196,101,58,0.35), 0 0 14px rgba(196,101,58,0.15)' }}>
          documentation
        </div>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          {'─'.repeat(50)}
        </div>
      </div>

      {/* TOC */}
      <div style={{ marginBottom: '3rem', border: '1px solid var(--border)', background: 'var(--bg-surface)', padding: '1.25rem' }}>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '0.75rem' }}>contents</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          {SECTIONS.map((s, i) => (
            <a
              key={s.id}
              href={`#${s.id}`}
              style={{ fontSize: '0.85rem', color: 'var(--accent-5)', textDecoration: 'none', textShadow: 'none', transition: 'color 0.15s' }}
            >
              {String(i + 1).padStart(2, '0')}. {s.title}
            </a>
          ))}
        </div>
      </div>

      {/* Sections */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4rem' }}>
        {SECTIONS.map(section => (
          <div key={section.id} id={section.id}>
            <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '0.02em', marginBottom: '0.4rem', textShadow: '0 0 5px rgba(196,101,58,0.35), 0 0 14px rgba(196,101,58,0.15)' }}>
                {section.title}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {'─'.repeat(40)}
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {section.content.map((block, i) => (
                <ContentBlock key={i} block={block} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ContentBlock({ block }) {
  if (block.type === 'text') {
    return <p style={{ fontSize: '0.875rem', color: 'var(--text-primary)', lineHeight: 1.7 }}>{block.value}</p>
  }

  if (block.type === 'terminal') {
    return (
      <div style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
        <div style={{ padding: '0.35rem 0.75rem', borderBottom: '1px solid var(--border)', fontSize: '0.7rem', color: 'var(--text-muted)' }}>terminal</div>
        <div style={{ padding: '0.75rem 1rem', fontSize: '0.8rem', lineHeight: 1.8 }}>
          {block.lines.map((line, i) => {
            if (!line) return <div key={i} style={{ height: '0.5rem' }} />
            const isCmd = line.startsWith('$')
            const isPass = line.includes('\u2713') || line.includes('PASS')
            const isFail = line.includes('\u2717') || line.includes('FAIL')
            const isRepair = line.includes('\u26A1')
            let color = 'var(--text-muted)'
            if (isCmd) color = 'var(--text-primary)'
            else if (isPass) color = 'var(--accent-2)'
            else if (isFail) color = 'var(--accent-3)'
            else if (isRepair) color = '#e0af68'
            return <div key={i} style={{ color }}>{line}</div>
          })}
        </div>
      </div>
    )
  }

  if (block.type === 'code') {
    return (
      <div style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
        <div style={{ padding: '0.35rem 0.75rem', borderBottom: '1px solid var(--border)', fontSize: '0.7rem', color: 'var(--text-muted)' }}>{block.lang}</div>
        <pre style={{ padding: '0.75rem 1rem', fontSize: '0.8rem', lineHeight: 1.7, color: 'var(--text-primary)', overflowX: 'auto', margin: 0 }}>
          {block.value}
        </pre>
      </div>
    )
  }

  if (block.type === 'diagram') {
    return (
      <div style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)', padding: '1.25rem', fontSize: '0.75rem', lineHeight: 1.6, overflowX: 'auto' }}>
        {block.lines.map((line, i) => (
          <div key={i} style={{ color: 'var(--accent-4)', whiteSpace: 'pre' }}>{line}</div>
        ))}
      </div>
    )
  }

  if (block.type === 'table') {
    return (
      <div style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)', overflowX: 'auto' }}>
        <table style={{ width: '100%', fontSize: '0.825rem', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {block.headers.map((h, i) => (
                <th key={i} style={{ textAlign: 'left', padding: '0.6rem 0.75rem', color: 'var(--text-muted)', fontWeight: 'normal', textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {block.rows.map((row, i) => (
              <tr key={i} style={{ borderBottom: i < block.rows.length - 1 ? '1px solid var(--border)' : 'none' }}>
                {row.map((cell, j) => (
                  <td key={j} style={{ padding: '0.5rem 0.75rem', color: j === 0 ? 'var(--accent-5)' : 'var(--text-primary)' }}>
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  return null
}
