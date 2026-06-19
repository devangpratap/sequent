#!/usr/bin/env python3
"""
Sequent CLI — Neural Formal Verification from the terminal.

Usage:
    sequent check file.py                  Analyze all functions in a file
    sequent check file.py -f func_name     Analyze a specific function
    sequent check file.py --json           Output raw JSON
    sequent check file.py --cert out.json  Export proof certificate
"""

import argparse
import ast
import json
import os
import sys
import textwrap
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verifier.neurosymbolic import SequentEngine


# Terminal colors — deep purple + orange accent
class C:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[38;5;135m'       # deep purple
    PURPLE_BOLD = '\033[1;38;5;135m'
    PURPLE_DIM = '\033[38;5;97m'    # muted purple
    ORANGE = '\033[38;5;208m'       # accent orange
    ORANGE_BOLD = '\033[1;38;5;208m'
    CYAN = '\033[96m'
    GRAY = '\033[90m'
    WHITE = '\033[97m'
    BG_PURPLE = '\033[48;5;53m'


LOGO = f"""{C.PURPLE_BOLD}
                             _
   ___ ___ __ _ _  _ ___ _ _| |_
  (_-</ -_) _` | || / -_) ' \\  _|
  /__/\\___\\__, |\\_,_\\___|_||_\\__|
             |_|
{C.RESET}{C.PURPLE_DIM}  Neural Formal Verification Engine{C.RESET}
"""


def extract_js_functions(source: str) -> list[tuple[str, str]]:
    """Extract (name, source) pairs for JS/TS functions using regex."""
    import re
    functions = []
    lines = source.split('\n')

    # Match function declarations and arrow functions
    func_re = re.compile(
        r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\("
    )
    arrow_re = re.compile(
        r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(.*?\)\s*=>"
    )

    i = 0
    while i < len(lines):
        m = func_re.match(lines[i]) or arrow_re.match(lines[i])
        if m:
            name = m.group(1)
            start = i
            # Find the end of the function by tracking braces
            brace_count = 0
            found_open = False
            end = i
            for j in range(i, len(lines)):
                for ch in lines[j]:
                    if ch == '{':
                        brace_count += 1
                        found_open = True
                    elif ch == '}':
                        brace_count -= 1
                if found_open and brace_count <= 0:
                    end = j
                    break
            else:
                end = len(lines) - 1

            func_source = '\n'.join(lines[start:end + 1])
            functions.append((name, func_source))
            i = end + 1
        else:
            i += 1

    return functions


def extract_functions(source: str) -> list[tuple[str, str]]:
    """Extract (name, source) pairs for all top-level functions."""
    tree = ast.parse(source)
    functions = []
    lines = source.split('\n')
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef):
            # Get source lines for this function
            start = node.lineno - 1
            end = node.end_lineno
            func_source = '\n'.join(lines[start:end])
            functions.append((node.name, func_source))
    return functions


def print_result(result, verbose=False):
    """Pretty-print a SequentResult."""
    is_buggy = result.consensus_buggy

    # Verdict
    if is_buggy:
        icon = f"{C.ORANGE_BOLD}✗ BUG DETECTED{C.RESET}"
    else:
        icon = f"{C.GREEN}✓ VERIFIED{C.RESET}"

    print(f"\n  {C.WHITE}{C.BOLD}{result.function_name or 'function'}{C.RESET}  {icon}  {C.GRAY}({result.total_time_ms:.0f}ms){C.RESET}")
    print(f"  {C.PURPLE_DIM}{'─' * 60}{C.RESET}")

    # GNN
    if result.gnn_prediction:
        gnn = result.gnn_prediction
        conf_color = C.ORANGE if gnn.buggy_confidence > 0.7 else C.YELLOW if gnn.buggy_confidence > 0.5 else C.GREEN
        print(f"  {C.PURPLE_BOLD}GNN{C.RESET}  {'Buggy' if gnn.is_buggy else 'Clean'} "
              f"({conf_color}{gnn.buggy_confidence:.1%}{C.RESET})  "
              f"{C.GRAY}{gnn.inference_time_ms:.0f}ms{C.RESET}")
        if gnn.bug_lines:
            print(f"       {C.ORANGE}⚑ Suspect lines: {gnn.bug_lines}{C.RESET}")

    # Z3
    if result.verification:
        v = result.verification
        z3_icon = f"{C.ORANGE}✗{C.RESET}" if v.has_bugs else f"{C.GREEN}✓{C.RESET}"
        print(f"  {C.PURPLE_BOLD}Z3 {C.RESET}  {z3_icon} {v.overall_result.value}  "
              f"{C.GRAY}{v.total_time_ms:.1f}ms{C.RESET}")

        for check in v.checks:
            if check.result.value == 'verified':
                sym = f"{C.GREEN}✓{C.RESET}"
            elif check.result.value == 'counterexample':
                sym = f"{C.ORANGE}✗{C.RESET}"
            else:
                sym = f"{C.PURPLE_DIM}?{C.RESET}"
            print(f"       {sym} {C.PURPLE_DIM}{check.property_name}{C.RESET}: {check.description}")
            if check.counterexample:
                print(f"         {C.ORANGE}↳ counterexample: {json.dumps(check.counterexample)}{C.RESET}")

    # Consensus
    print(f"  {C.PURPLE_DIM}{'─' * 60}{C.RESET}")
    print(f"  {C.PURPLE_BOLD}Consensus:{C.RESET} {result.consensus_description}")

    # Repair
    if result.repair:
        verified_tag = f"{C.GREEN}[re-verified ✓]{C.RESET}" if result.repair.verified else f"{C.PURPLE_DIM}[unverified]{C.RESET}"
        print(f"\n  {C.ORANGE_BOLD}⚡ REPAIR{C.RESET} {result.repair.repair_description} {verified_tag}")
        if result.repair.repaired_code and verbose:
            print(f"\n{C.PURPLE_DIM}  Fixed code:{C.RESET}")
            for line in result.repair.repaired_code.split('\n'):
                print(f"    {C.GREEN}{line}{C.RESET}")

    print()


def generate_certificate(results: list, filepath: str, source_file: str):
    """Export proof certificate as JSON."""
    from verifier.z3_engine import VerificationResult

    cert = {
        "sequent_version": "0.2.0",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_file": os.path.abspath(source_file),
        "summary": {
            "total_functions": len(results),
            "verified": sum(1 for r in results if not r.consensus_buggy),
            "bugs_found": sum(1 for r in results if r.consensus_buggy),
        },
        "functions": [],
    }

    for r in results:
        func_cert = {
            "name": r.function_name,
            "verdict": "buggy" if r.consensus_buggy else "verified",
            "consensus": r.consensus_description,
            "time_ms": round(r.total_time_ms, 1),
        }

        if r.gnn_prediction:
            func_cert["gnn"] = {
                "prediction": "buggy" if r.gnn_prediction.is_buggy else "clean",
                "confidence": round(r.gnn_prediction.buggy_confidence, 4),
                "suspect_lines": r.gnn_prediction.bug_lines,
            }

        if r.verification:
            func_cert["z3"] = {
                "result": r.verification.overall_result.value,
                "properties_checked": len(r.verification.checks),
                "properties_verified": sum(
                    1 for c in r.verification.checks
                    if c.result == VerificationResult.VERIFIED
                ),
                "counterexamples": [
                    {
                        "property": c.property_name,
                        "description": c.description,
                        "line": c.line,
                        "counterexample": c.counterexample,
                    }
                    for c in r.verification.counterexamples
                ],
            }

        if r.repair:
            func_cert["repair"] = {
                "description": r.repair.repair_description,
                "verified": r.repair.verified,
                "repaired_code": r.repair.repaired_code,
            }

        cert["functions"].append(func_cert)

    with open(filepath, 'w') as f:
        json.dump(cert, f, indent=2)

    return cert


def main():
    parser = argparse.ArgumentParser(
        prog='sequent',
        description='Sequent — Neural Formal Verification Engine',
    )
    sub = parser.add_subparsers(dest='command')

    check_parser = sub.add_parser('check', help='Analyze a Python/JS/TS file')
    check_parser.add_argument('file', help='Python, JavaScript, or TypeScript file to analyze')
    check_parser.add_argument('-f', '--function', help='Analyze only this function')
    check_parser.add_argument('--json', action='store_true', help='Output raw JSON')
    check_parser.add_argument('--cert', metavar='FILE', help='Export proof certificate to FILE')
    check_parser.add_argument('-v', '--verbose', action='store_true', help='Show repaired code')
    check_parser.add_argument('--no-gnn', action='store_true', help='Z3-only mode (skip GNN)')
    check_parser.add_argument('--no-learn', action='store_true', help='Disable self-learning data collection')

    # Self-learning commands
    learn_parser = sub.add_parser('learn', help='Run self-learning cycle (fine-tune GNN on accumulated experience)')
    learn_parser.add_argument('--epochs', type=int, default=30, help='Fine-tuning epochs (default: 30)')
    learn_parser.add_argument('--lr', type=float, default=0.0001, help='Learning rate (default: 0.0001)')
    learn_parser.add_argument('--min-samples', type=int, default=50, help='Minimum samples to proceed (default: 50)')
    learn_parser.add_argument('--force', action='store_true', help='Learn even with fewer than min-samples')
    learn_parser.add_argument('--rollback', action='store_true', help='Rollback to previous model version')

    exp_parser = sub.add_parser('experience', help='View self-learning experience stats')
    exp_parser.add_argument('--export', metavar='FILE', help='Export experience as training JSON')
    exp_parser.add_argument('--clear', action='store_true', help='Clear all stored experience')

    # Watch command
    watch_parser = sub.add_parser('watch', help='Watch files/directories and re-analyze on change')
    watch_parser.add_argument('paths', nargs='+', help='Files or directories to watch')
    watch_parser.add_argument('--interval', type=float, default=1.0, help='Poll interval in seconds (default: 1.0)')

    # Badge command
    badge_parser = sub.add_parser('badge', help='Generate SVG verification badge')
    badge_parser.add_argument('file', help='Python file to analyze')
    badge_parser.add_argument('-o', '--output', metavar='FILE', default='sequent-badge.svg',
                              help='Output SVG file (default: sequent-badge.svg)')
    badge_parser.add_argument('--no-gnn', action='store_true', help='Z3-only mode')

    # LSP command
    lsp_parser = sub.add_parser('lsp', help='Start LSP server for editor integration')
    lsp_parser.add_argument('--tcp', action='store_true', help='Run in TCP mode')
    lsp_parser.add_argument('--port', type=int, default=2087, help='TCP port (default: 2087)')
    lsp_parser.add_argument('--host', default='127.0.0.1', help='TCP host (default: 127.0.0.1)')

    args = parser.parse_args()

    if not args.command:
        print(LOGO)
        parser.print_help()
        return

    if args.command == 'check':
        if not os.path.exists(args.file):
            print(f"{C.ORANGE}Error: File not found: {args.file}{C.RESET}")
            sys.exit(1)

        with open(args.file) as f:
            source = f.read()

        if not args.json:
            print(LOGO)

        # Detect language from file extension
        ext = os.path.splitext(args.file)[1].lower()
        is_js = ext in ('.js', '.ts', '.jsx', '.tsx', '.mjs', '.cjs')

        if is_js:
            functions = extract_js_functions(source)
        else:
            try:
                functions = extract_functions(source)
            except SyntaxError as e:
                print(f"{C.ORANGE}Syntax error in {args.file}: {e}{C.RESET}")
                sys.exit(1)

        if not functions:
            print(f"{C.PURPLE_DIM}No functions found in {args.file}{C.RESET}")
            sys.exit(0)

        if args.function:
            functions = [(n, s) for n, s in functions if n == args.function]
            if not functions:
                print(f"{C.ORANGE}Function '{args.function}' not found{C.RESET}")
                sys.exit(1)

        # Load engine
        model_path = None if args.no_gnn else os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'checkpoints', 'best_model.pt'
        )
        engine = SequentEngine(model_path=model_path, self_learn=not args.no_learn)

        lang_label = 'JS/TS' if is_js else 'Python'
        if not args.json:
            print(f"  {C.PURPLE_DIM}Analyzing {len(functions)} function(s) in {C.WHITE}{args.file}{C.RESET}")
            print(f"  {C.PURPLE_DIM}Language: {C.PURPLE}{lang_label}{C.RESET}")
            print(f"  {C.PURPLE_DIM}Engine: {C.PURPLE}{'GNN + Z3' if engine.model else 'Z3 only'}{C.RESET}")
            print(f"  {C.PURPLE_DIM}Device: {C.PURPLE}{engine.device}{C.RESET}")

        # Analyze
        results = []
        for name, func_source in functions:
            if is_js:
                result = engine.analyze_js(func_source, name)
            else:
                result = engine.analyze(func_source, name)
            results.append(result)

            if not args.json:
                print_result(result, verbose=args.verbose)

        # Summary
        if not args.json and len(results) > 1:
            verified = sum(1 for r in results if not r.consensus_buggy)
            buggy = sum(1 for r in results if r.consensus_buggy)
            total_time = sum(r.total_time_ms for r in results)
            print(f"  {C.PURPLE_DIM}{'━' * 60}{C.RESET}")
            print(f"  {C.PURPLE_BOLD}Summary{C.RESET}  {C.GREEN}✓ {verified} verified{C.RESET}  "
                  f"{C.ORANGE}✗ {buggy} bugs{C.RESET}  "
                  f"{C.GRAY}({total_time:.0f}ms){C.RESET}\n")

        # JSON output
        if args.json:
            output = [r.summary for r in results]
            print(json.dumps(output, indent=2))

        # Proof certificate
        if args.cert:
            cert = generate_certificate(results, args.cert, args.file)
            if not args.json:
                print(f"  {C.PURPLE}📜 Proof certificate → {C.WHITE}{args.cert}{C.RESET}\n")

        # Self-learning status
        if not args.json and not args.no_learn and engine.experience_store:
            stats = engine.experience_store.get_stats()
            if stats["total"] > 0:
                print(f"  {C.PURPLE_DIM}Self-learning: {stats['total']} samples collected "
                      f"({stats['since_last_learn']} since last cycle){C.RESET}")
                if engine.experience_store.should_learn():
                    print(f"  {C.PURPLE}Ready for learning cycle! Run: {C.WHITE}sequent learn{C.RESET}\n")

        # Exit code: 1 if any bugs found
        sys.exit(1 if any(r.consensus_buggy for r in results) else 0)

    elif args.command == 'learn':
        print(LOGO)
        from verifier.self_learn import ExperienceStore, OnlineLearner

        store = ExperienceStore()
        stats = store.get_stats()

        if args.rollback:
            model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'checkpoints', 'best_model.pt')
            learner = OnlineLearner(checkpoint_path=model_path, experience_store=store)
            if learner.rollback():
                print(f"  {C.GREEN}Rolled back to previous model version{C.RESET}\n")
            else:
                print(f"  {C.ORANGE}No previous model version found{C.RESET}\n")
            return

        print(f"  {C.PURPLE_BOLD}Self-Learning Cycle{C.RESET}")
        print(f"  {C.PURPLE_DIM}{'─' * 50}{C.RESET}")
        print(f"  {C.WHITE}Experience samples:{C.RESET}  {stats['total']}")
        print(f"  {C.WHITE}Since last cycle:{C.RESET}    {stats['since_last_learn']}")
        print(f"  {C.WHITE}GNN accuracy:{C.RESET}        {stats['gnn_accuracy']:.1%}")
        print(f"  {C.WHITE}Learning cycles:{C.RESET}     {stats['learn_cycles']}")
        print()

        min_samples = 1 if args.force else args.min_samples
        if stats['since_last_learn'] < min_samples:
            print(f"  {C.ORANGE}Not enough new samples ({stats['since_last_learn']}/{min_samples}).{C.RESET}")
            print(f"  {C.PURPLE_DIM}Use --force to learn anyway, or analyze more files first.{C.RESET}\n")
            return

        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'checkpoints', 'best_model.pt')
        learner = OnlineLearner(checkpoint_path=model_path, experience_store=store)

        print(f"  {C.PURPLE}Fine-tuning GNN on {stats['since_last_learn']} new samples...{C.RESET}")
        print(f"  {C.PURPLE_DIM}Epochs: {args.epochs} | LR: {args.lr} | EWC: enabled{C.RESET}")
        print()

        result = learner.fine_tune(epochs=args.epochs, lr=args.lr, min_samples=min_samples)

        if "error" in result:
            print(f"  {C.ORANGE}Error: {result['error']}{C.RESET}\n")
            return

        # Print training progress
        for h in result.get("history", []):
            val_str = f" | Val F1: {h['val_f1']:.3f}" if 'val_f1' in h else ""
            print(f"  {C.GRAY}Epoch {h['epoch']:3d} | Train F1: {h['train_f1']:.3f}{val_str}{C.RESET}")

        print(f"\n  {C.PURPLE_DIM}{'─' * 50}{C.RESET}")

        if result["improved"]:
            print(f"  {C.GREEN}Model improved!{C.RESET}")
            print(f"  {C.WHITE}Baseline F1:{C.RESET}  {result['baseline_f1']:.3f}" if result['baseline_f1'] else "")
            print(f"  {C.WHITE}New F1:{C.RESET}       {result['final_f1']:.3f}")
            print(f"  {C.WHITE}Saved to:{C.RESET}     {result['model_saved']}")
            print(f"  {C.PURPLE_DIM}Previous model backed up (use --rollback to restore){C.RESET}")
        else:
            print(f"  {C.ORANGE}No improvement — model unchanged{C.RESET}")
            print(f"  {C.PURPLE_DIM}{result.get('rollback_reason', '')}{C.RESET}")
        print()

    elif args.command == 'experience':
        from verifier.self_learn import ExperienceStore

        store = ExperienceStore()

        if args.clear:
            import shutil
            shutil.rmtree(store.store_dir, ignore_errors=True)
            print(f"{C.GREEN}Experience cleared.{C.RESET}")
            return

        if args.export:
            dataset = store.export_dataset()
            with open(args.export, 'w') as f:
                json.dump(dataset, f, indent=2)
            print(f"{C.GREEN}Exported {len(dataset)} samples to {args.export}{C.RESET}")
            return

        stats = store.get_stats()
        print(LOGO)
        print(f"  {C.PURPLE_BOLD}Experience Store{C.RESET}")
        print(f"  {C.PURPLE_DIM}{'─' * 50}{C.RESET}")
        print(f"  {C.WHITE}Total samples:{C.RESET}      {stats['total']}")
        print(f"  {C.WHITE}Buggy:{C.RESET}              {stats['buggy']}")
        print(f"  {C.WHITE}Clean:{C.RESET}              {stats['clean']}")
        print(f"  {C.WHITE}GNN accuracy:{C.RESET}       {stats['gnn_accuracy']:.1%}")
        print(f"  {C.WHITE}Since last learn:{C.RESET}   {stats['since_last_learn']}")
        print(f"  {C.WHITE}Learning cycles:{C.RESET}    {stats['learn_cycles']}")
        print(f"  {C.WHITE}Store path:{C.RESET}         {store.store_dir}")

        if store.should_learn():
            print(f"\n  {C.PURPLE}Ready for self-learning! Run: {C.WHITE}sequent learn{C.RESET}")
        print()

    elif args.command == 'watch':
        print(LOGO)
        from verifier.watcher import FileWatcher, IncrementalAnalyzer, _cli_on_result

        print(f"  {C.PURPLE_BOLD}Watch Mode{C.RESET}")
        print(f"  {C.PURPLE_DIM}Watching: {', '.join(args.paths)}{C.RESET}")
        print(f"  {C.PURPLE_DIM}Poll interval: {args.interval}s | Press Ctrl+C to stop{C.RESET}\n")

        watcher = FileWatcher(
            paths=args.paths,
            poll_interval=args.interval,
            on_result=_cli_on_result,
        )
        try:
            watcher.watch()
        except KeyboardInterrupt:
            print(f"\n  {C.PURPLE_DIM}Watch stopped.{C.RESET}\n")

    elif args.command == 'badge':
        from verifier.badges import generate_summary_badge, generate_badge, save_badge

        if not os.path.exists(args.file):
            print(f"{C.ORANGE}Error: File not found: {args.file}{C.RESET}")
            sys.exit(1)

        with open(args.file) as f:
            source = f.read()

        try:
            functions = extract_functions(source)
        except SyntaxError as e:
            print(f"{C.ORANGE}Syntax error in {args.file}: {e}{C.RESET}")
            sys.exit(1)

        model_path = None if args.no_gnn else os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'checkpoints', 'best_model.pt'
        )
        engine = SequentEngine(model_path=model_path, self_learn=False)

        verified = 0
        buggy = 0
        total_time = 0.0

        for name, func_source in functions:
            result = engine.analyze(func_source, name)
            total_time += result.total_time_ms
            if result.consensus_buggy:
                buggy += 1
            else:
                verified += 1

        svg = generate_summary_badge(verified=verified, buggy=buggy, total_time_ms=total_time)
        save_badge(svg, args.output)
        print(f"{C.GREEN}Badge saved to {args.output}{C.RESET}")
        print(f"  {C.PURPLE_DIM}{verified} verified, {buggy} bugs ({total_time:.0f}ms){C.RESET}")

    elif args.command == 'lsp':
        from lsp_server import serve_tcp, SequentLSPServer

        if args.tcp:
            serve_tcp(host=args.host, port=args.port)
        else:
            server = SequentLSPServer()
            server.serve()


if __name__ == '__main__':
    main()
