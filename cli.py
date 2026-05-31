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
        "sequent_version": "0.1.0",
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

    check_parser = sub.add_parser('check', help='Analyze a Python file')
    check_parser.add_argument('file', help='Python file to analyze')
    check_parser.add_argument('-f', '--function', help='Analyze only this function')
    check_parser.add_argument('--json', action='store_true', help='Output raw JSON')
    check_parser.add_argument('--cert', metavar='FILE', help='Export proof certificate to FILE')
    check_parser.add_argument('-v', '--verbose', action='store_true', help='Show repaired code')
    check_parser.add_argument('--no-gnn', action='store_true', help='Z3-only mode (skip GNN)')

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

        # Extract functions
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
        engine = SequentEngine(model_path=model_path)

        if not args.json:
            print(f"  {C.PURPLE_DIM}Analyzing {len(functions)} function(s) in {C.WHITE}{args.file}{C.RESET}")
            print(f"  {C.PURPLE_DIM}Engine: {C.PURPLE}{'GNN + Z3' if engine.model else 'Z3 only'}{C.RESET}")
            print(f"  {C.PURPLE_DIM}Device: {C.PURPLE}{engine.device}{C.RESET}")

        # Analyze
        results = []
        for name, func_source in functions:
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

        # Exit code: 1 if any bugs found
        sys.exit(1 if any(r.consensus_buggy for r in results) else 0)


if __name__ == '__main__':
    main()
