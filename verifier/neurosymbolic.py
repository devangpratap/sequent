"""
Neurosymbolic Verification Loop for Sequent.

The core pipeline:
1. GNN PROPOSES: predict if code is buggy + locate bug nodes
2. Z3 DISPOSES: verify the proposal with formal proof/counterexample
3. AUTO-REPAIR: apply targeted fix based on bug class
4. RE-VERIFY: confirm the fix is correct

GNN proposes, Z3 disposes. Best of both worlds.
"""

import ast
import copy
import os
import sys
import textwrap
import time
from dataclasses import dataclass, field
from typing import Optional

import torch
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.ast_to_graph import code_to_graph, ASTGraphBuilder, NUM_NODE_TYPES
from model.gnn import SequentGNN
from verifier.z3_engine import Z3Verifier, VerificationReport, VerificationResult


@dataclass
class GNNPrediction:
    is_buggy: bool
    buggy_confidence: float
    bug_lines: list[int] = field(default_factory=list)  # lines with high bug probability
    node_scores: list[float] = field(default_factory=list)  # per-node bug scores
    attention_edges: list = field(default_factory=list)  # top attention edges for visualization
    inference_time_ms: float = 0.0


@dataclass
class RepairResult:
    original_code: str
    repaired_code: str
    repair_description: str
    repair_line: int
    verified: bool = False


@dataclass
class SequentResult:
    """Full result of the neurosymbolic pipeline."""
    code: str
    function_name: str

    # GNN stage
    gnn_prediction: Optional[GNNPrediction] = None

    # Z3 stage
    verification: Optional[VerificationReport] = None

    # Repair stage
    repair: Optional[RepairResult] = None

    # Re-verification stage
    post_repair_verification: Optional[VerificationReport] = None

    # Consensus
    consensus_buggy: bool = False
    consensus_description: str = ""
    total_time_ms: float = 0.0

    @property
    def summary(self) -> dict:
        result = {
            "function": self.function_name,
            "is_buggy": self.consensus_buggy,
            "description": self.consensus_description,
            "total_time_ms": round(self.total_time_ms, 1),
        }
        if self.gnn_prediction:
            result["gnn"] = {
                "buggy": self.gnn_prediction.is_buggy,
                "confidence": round(self.gnn_prediction.buggy_confidence, 3),
                "bug_lines": self.gnn_prediction.bug_lines,
                "inference_ms": round(self.gnn_prediction.inference_time_ms, 1),
            }
            if self.gnn_prediction.attention_edges:
                result["gnn"]["attention"] = self.gnn_prediction.attention_edges
        if self.verification:
            result["z3"] = {
                "result": self.verification.overall_result.value,
                "checks": len(self.verification.checks),
                "bugs_found": len(self.verification.counterexamples),
                "time_ms": round(self.verification.total_time_ms, 1),
            }
        if self.repair:
            result["repair"] = {
                "applied": True,
                "description": self.repair.repair_description,
                "verified": self.repair.verified,
            }
            if self.post_repair_verification:
                result["repair"]["remaining_issues"] = len(self.post_repair_verification.counterexamples)
        return result


class SequentEngine:
    """Main neurosymbolic verification engine."""

    def __init__(self, model_path: Optional[str] = None, self_learn: bool = True):
        self.device = torch.device(
            'cuda' if torch.cuda.is_available() else
            'mps' if torch.backends.mps.is_available() else 'cpu'
        )
        self.model = None
        self.verifier = Z3Verifier(timeout_ms=5000)

        # Self-learning: collect experience from every analysis run
        self.experience_store = None
        if self_learn:
            try:
                from verifier.self_learn import ExperienceStore
                self.experience_store = ExperienceStore()
            except Exception:
                pass  # graceful degradation

        if model_path:
            self.load_model(model_path)

    def load_model(self, model_path: str):
        """Load trained GNN model from checkpoint."""
        checkpoint = torch.load(model_path, map_location=self.device, weights_only=True)
        config = checkpoint['config']

        self.model = SequentGNN(
            in_channels=config['in_channels'],
            hidden_channels=config['hidden_channels'],
            num_heads=config['num_heads'],
            dropout=config['dropout'],
            num_edge_types=config.get('num_edge_types', 3),
            edge_embed_dim=config.get('edge_embed_dim', 16),
        ).to(self.device)

        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()

    def analyze(self, code: str, function_name: str = "") -> SequentResult:
        """Run the full neurosymbolic pipeline on a function."""
        code = textwrap.dedent(code).strip()
        result = SequentResult(code=code, function_name=function_name)
        t0 = time.time()

        # Stage 1: GNN prediction
        if self.model is not None:
            result.gnn_prediction = self._gnn_predict(code)

        # Stage 2: Z3 verification
        result.verification = self.verifier.verify(code, function_name)

        # Stage 3: Consensus — both must agree
        gnn_says_buggy = result.gnn_prediction.is_buggy if result.gnn_prediction else False
        z3_says_buggy = result.verification.has_bugs

        if gnn_says_buggy and z3_says_buggy:
            result.consensus_buggy = True
            result.consensus_description = (
                f"BUG CONFIRMED: GNN detected bug (confidence: "
                f"{result.gnn_prediction.buggy_confidence:.1%}) and Z3 produced "
                f"a formal counterexample. Lines: {result.gnn_prediction.bug_lines}"
            )
        elif z3_says_buggy and not gnn_says_buggy:
            result.consensus_buggy = True
            result.consensus_description = (
                "BUG FOUND by Z3 (GNN missed it). Formal counterexample proves the bug exists."
            )
        elif gnn_says_buggy and not z3_says_buggy:
            gnn_conf = result.gnn_prediction.buggy_confidence
            if gnn_conf > 0.85:
                # High-confidence GNN prediction — Z3 may lack coverage for this bug class
                result.consensus_buggy = False
                result.consensus_description = (
                    f"WARNING: GNN flagged bug with high confidence ({gnn_conf:.1%}) "
                    f"but Z3 could not confirm. Bug class may be outside Z3's scope. "
                    f"Lines: {result.gnn_prediction.bug_lines}"
                )
            else:
                result.consensus_buggy = False
                result.consensus_description = (
                    f"GNN flagged potential bug (confidence: {gnn_conf:.1%}) "
                    f"but Z3 could not confirm. "
                    f"Likely false positive or bug class outside Z3's scope."
                )
        else:
            result.consensus_buggy = False
            result.consensus_description = "VERIFIED: Both GNN and Z3 agree — no bugs detected."

        # Stage 4: Auto-repair if buggy
        if result.consensus_buggy:
            repair = self._attempt_repair(code, result)
            if repair:
                result.repair = repair
                # Re-verify the repair
                result.post_repair_verification = self.verifier.verify(
                    repair.repaired_code, function_name
                )
                repair.verified = not result.post_repair_verification.has_bugs

        result.total_time_ms = (time.time() - t0) * 1000

        # Stage 5: Collect experience for self-learning
        if self.experience_store is not None:
            try:
                from verifier.self_learn import collect_experience
                collect_experience(result, self.experience_store)
            except Exception:
                pass  # never let self-learning break the main pipeline

        return result

    @torch.no_grad()
    def _gnn_predict(self, code: str) -> GNNPrediction:
        """Run GNN inference on code."""
        t0 = time.time()

        graph = code_to_graph(code, bug_line=None, is_buggy=False)
        if graph is None:
            return GNNPrediction(
                is_buggy=False, buggy_confidence=0.0,
                inference_time_ms=(time.time() - t0) * 1000
            )

        x = graph['x'].to(self.device)
        edge_index = graph['edge_index'].to(self.device)
        edge_type = graph['edge_type'].to(self.device) if 'edge_type' in graph else None

        graph_pred, node_pred, _, _ = self.model(x, edge_index, edge_type=edge_type)

        buggy_prob = graph_pred.item()
        node_scores = node_pred.squeeze().cpu().numpy().tolist()
        if isinstance(node_scores, float):
            node_scores = [node_scores]

        # Find lines with high bug probability
        node_lines = graph['node_lines']
        bug_lines = []
        threshold = 0.5
        for i, (score, line) in enumerate(zip(node_scores, node_lines)):
            if score > threshold and line > 0 and line not in bug_lines:
                bug_lines.append(line)

        # Sort by score (highest first)
        line_scores = {}
        for score, line in zip(node_scores, node_lines):
            if line > 0:
                line_scores[line] = max(line_scores.get(line, 0), score)
        bug_lines = sorted(line_scores.keys(), key=lambda l: line_scores[l], reverse=True)
        bug_lines = [l for l in bug_lines if line_scores[l] > threshold]

        # Extract top attention edges for interpretability
        attention_edges = []
        attn_data = self.model.get_attention_weights()
        if attn_data is not None:
            attn_edge_index, alpha = attn_data
            # alpha shape: [num_edges, heads] or [num_edges, 1]
            avg_alpha = alpha.mean(dim=-1) if alpha.dim() > 1 else alpha.squeeze()
            top_k = min(10, avg_alpha.size(0))
            top_indices = avg_alpha.topk(top_k).indices
            for idx in top_indices:
                src, dst = attn_edge_index[0, idx].item(), attn_edge_index[1, idx].item()
                src_line = node_lines[src] if src < len(node_lines) else 0
                dst_line = node_lines[dst] if dst < len(node_lines) else 0
                attention_edges.append({
                    "src_line": src_line,
                    "dst_line": dst_line,
                    "weight": round(avg_alpha[idx].item(), 4),
                })

        return GNNPrediction(
            is_buggy=buggy_prob > 0.5,
            buggy_confidence=buggy_prob,
            bug_lines=bug_lines[:5],  # Top 5 suspicious lines
            node_scores=node_scores,
            attention_edges=attention_edges,
            inference_time_ms=(time.time() - t0) * 1000,
        )

    def _attempt_repair(self, code: str, result: SequentResult) -> Optional[RepairResult]:
        """Attempt to auto-repair based on Z3 counterexamples and GNN predictions."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return None

        # Determine repair strategy based on Z3 findings
        for check in result.verification.counterexamples:
            if check.property_name == "none_safety":
                return self._repair_none_safety(code, check)
            elif check.property_name == "division_safety":
                return self._repair_division_safety(code, check)
            elif check.property_name == "overflow_safety":
                return self._repair_overflow(code, check)
            elif check.property_name == "range_bound_check":
                return self._repair_off_by_one(code, check)
            elif check.property_name == "return_completeness":
                return self._repair_missing_return(code, check)
            elif check.property_name == "operator_consistency":
                return self._repair_wrong_operator(code, check)
            elif check.property_name == "recursion_base_case":
                return self._repair_recursion_base_case(code, check)
            elif check.property_name == "loop_termination":
                return RepairResult(
                    original_code=code,
                    repaired_code=code,
                    repair_description="Potential infinite loop detected — manual review recommended",
                    repair_line=check.line or 0,
                )
            elif check.property_name == "index_bounds":
                return self._repair_index_bounds(code, check)

        return None

    def _repair_none_safety(self, code: str, check) -> Optional[RepairResult]:
        """Add None check guard at the top of the function."""
        try:
            tree = ast.parse(code)
            func_def = None
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_def = node
                    break

            if not func_def:
                return None

            param = check.counterexample.get("param", "")
            if not param:
                return None

            # Create: if param is None: return None
            guard = ast.parse(f"if {param} is None:\n    return None").body[0]
            ast.fix_missing_locations(guard)

            func_def.body.insert(0, guard)
            ast.fix_missing_locations(tree)
            repaired = ast.unparse(tree)

            return RepairResult(
                original_code=code,
                repaired_code=repaired,
                repair_description=f"Added None guard for parameter '{param}'",
                repair_line=func_def.lineno,
            )
        except Exception:
            return None

    def _repair_division_safety(self, code: str, check) -> Optional[RepairResult]:
        """Add zero-division guard."""
        try:
            tree = ast.parse(code)
            func_def = None
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_def = node
                    break

            if not func_def:
                return None

            divisor = list(check.counterexample.keys())[0] if check.counterexample else None
            if not divisor:
                return None

            guard = ast.parse(f"if {divisor} == 0:\n    return None").body[0]
            ast.fix_missing_locations(guard)
            func_def.body.insert(0, guard)
            ast.fix_missing_locations(tree)
            repaired = ast.unparse(tree)

            return RepairResult(
                original_code=code,
                repaired_code=repaired,
                repair_description=f"Added zero-division guard for '{divisor}'",
                repair_line=func_def.lineno,
            )
        except Exception:
            return None

    def _repair_overflow(self, code: str, check) -> Optional[RepairResult]:
        """Add overflow protection."""
        # For now, return description of what should be done
        return RepairResult(
            original_code=code,
            repaired_code=code,  # Complex repair — flag for manual fix
            repair_description="Integer overflow detected — manual review recommended",
            repair_line=check.line or 0,
        )

    def _repair_off_by_one(self, code: str, check) -> Optional[RepairResult]:
        """Fix off-by-one in range bounds."""
        try:
            tree = ast.parse(code)

            class RangeFixer(ast.NodeTransformer):
                def __init__(self):
                    self.fixed = False

                def visit_Call(self, node):
                    self.generic_visit(node)
                    if self.fixed:
                        return node
                    if isinstance(node.func, ast.Name) and node.func.id == 'range':
                        if len(node.args) >= 2:
                            end_arg = node.args[-1]
                            if isinstance(end_arg, ast.BinOp) and isinstance(end_arg.right, ast.Constant):
                                if isinstance(end_arg.right.value, int) and end_arg.right.value > 1:
                                    end_arg.right.value = 1
                                    self.fixed = True
                    return node

            fixer = RangeFixer()
            fixed_tree = fixer.visit(tree)
            if fixer.fixed:
                ast.fix_missing_locations(fixed_tree)
                repaired = ast.unparse(fixed_tree)
                return RepairResult(
                    original_code=code,
                    repaired_code=repaired,
                    repair_description="Fixed off-by-one error in range bound",
                    repair_line=check.line or 0,
                )
        except Exception:
            pass

        return None

    def _repair_missing_return(self, code: str, check) -> Optional[RepairResult]:
        """When return completeness fails, add a default return at the end of the function.

        Uses AST inspection to infer the likely return type from existing return
        statements, then appends an appropriate default return.
        """
        try:
            tree = ast.parse(code)
            func_def = None
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_def = node
                    break

            if not func_def:
                return None

            # Collect return values from existing return statements to infer type
            return_values = []
            for node in ast.walk(func_def):
                if isinstance(node, ast.Return) and node.value is not None:
                    return_values.append(node.value)

            # Determine the default return value based on existing returns
            default_return = "None"
            if return_values:
                sample = return_values[0]
                if isinstance(sample, ast.Constant):
                    if isinstance(sample.value, bool):
                        default_return = "False"
                    elif isinstance(sample.value, int):
                        default_return = "0"
                    elif isinstance(sample.value, float):
                        default_return = "0.0"
                    elif isinstance(sample.value, str):
                        default_return = "''"
                elif isinstance(sample, ast.List):
                    default_return = "[]"
                elif isinstance(sample, ast.Dict):
                    default_return = "{}"
                elif isinstance(sample, ast.Tuple):
                    default_return = "()"

            # Add default return at the end of the function body
            default_stmt = ast.parse(f"return {default_return}").body[0]
            ast.fix_missing_locations(default_stmt)
            func_def.body.append(default_stmt)
            ast.fix_missing_locations(tree)
            repaired = ast.unparse(tree)

            return RepairResult(
                original_code=code,
                repaired_code=repaired,
                repair_description=f"Added default 'return {default_return}' for missing return path",
                repair_line=func_def.end_lineno or func_def.lineno,
            )
        except Exception:
            return None

    def _repair_wrong_operator(self, code: str, check) -> Optional[RepairResult]:
        """For operator consistency issues, swap the flagged operator.

        Supports swapping < to <=, > to >=, 'and' to 'or', and vice versa,
        based on the suggestion in the counterexample.
        """
        try:
            tree = ast.parse(code)
            target_line = check.line

            if not target_line:
                return None

            swap_map = {
                ast.Lt: ast.LtE,
                ast.LtE: ast.Lt,
                ast.Gt: ast.GtE,
                ast.GtE: ast.Gt,
                ast.And: ast.Or,
                ast.Or: ast.And,
            }

            class OperatorFixer(ast.NodeTransformer):
                def __init__(self):
                    self.fixed = False

                def visit_Compare(self, node):
                    self.generic_visit(node)
                    if self.fixed:
                        return node
                    if hasattr(node, 'lineno') and node.lineno == target_line:
                        new_ops = []
                        changed = False
                        for op in node.ops:
                            replacement = swap_map.get(type(op))
                            if replacement is not None:
                                new_ops.append(replacement())
                                changed = True
                            else:
                                new_ops.append(op)
                        if changed:
                            node.ops = new_ops
                            self.fixed = True
                    return node

                def visit_BoolOp(self, node):
                    self.generic_visit(node)
                    if self.fixed:
                        return node
                    if hasattr(node, 'lineno') and node.lineno == target_line:
                        replacement = swap_map.get(type(node.op))
                        if replacement is not None:
                            node.op = replacement()
                            self.fixed = True
                    return node

            fixer = OperatorFixer()
            fixed_tree = fixer.visit(tree)
            if fixer.fixed:
                ast.fix_missing_locations(fixed_tree)
                repaired = ast.unparse(fixed_tree)
                return RepairResult(
                    original_code=code,
                    repaired_code=repaired,
                    repair_description=f"Swapped operator at line {target_line} for consistency",
                    repair_line=target_line,
                )
        except Exception:
            return None

        return None

    def _repair_recursion_base_case(self, code: str, check) -> Optional[RepairResult]:
        """For missing recursion base case, add a guard based on parameter names.

        Inserts a base-case check like ``if n <= 0: return`` at the top of the
        recursive function, choosing the parameter and sentinel from conventions.
        """
        try:
            tree = ast.parse(code)
            func_def = None
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_def = node
                    break

            if not func_def:
                return None

            params = [arg.arg for arg in func_def.args.args]
            if not params:
                return None

            # Pick the most likely recursion-control parameter
            preferred = ['n', 'depth', 'count', 'k', 'num', 'level', 'size']
            chosen_param = None
            for name in preferred:
                if name in params:
                    chosen_param = name
                    break
            if chosen_param is None:
                chosen_param = params[0]

            # Determine return value from existing returns (prefer Constant returns)
            default_return = "None"
            for node in ast.walk(func_def):
                if isinstance(node, ast.Return) and node.value is not None:
                    val = node.value
                    if isinstance(val, ast.Constant):
                        if isinstance(val.value, bool):
                            default_return = "False"
                        elif isinstance(val.value, int):
                            default_return = "0"
                        elif isinstance(val.value, float):
                            default_return = "0.0"
                        elif isinstance(val.value, str):
                            default_return = "''"
                        break
                    elif isinstance(val, ast.List):
                        default_return = "[]"
                        break

            guard = ast.parse(f"if {chosen_param} <= 0:\n    return {default_return}").body[0]
            ast.fix_missing_locations(guard)
            func_def.body.insert(0, guard)
            ast.fix_missing_locations(tree)
            repaired = ast.unparse(tree)

            return RepairResult(
                original_code=code,
                repaired_code=repaired,
                repair_description=f"Added base case guard 'if {chosen_param} <= 0: return {default_return}'",
                repair_line=func_def.lineno,
            )
        except Exception:
            return None

    def _repair_index_bounds(self, code: str, check) -> Optional[RepairResult]:
        """Improved index-bounds repair: add a length guard at the top of the function."""
        try:
            tree = ast.parse(code)
            func_def = None
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_def = node
                    break

            if not func_def:
                return None

            # Find the array parameter that was flagged
            params = [arg.arg for arg in func_def.args.args]
            arr_param = None

            # Try to extract from the check description or counterexample
            desc = check.description or ""
            for p in params:
                if p in desc:
                    arr_param = p
                    break
            if arr_param is None and params:
                arr_param = params[0]

            if not arr_param:
                return None

            # Add a length guard: if not arr or len(arr) == 0: return None
            guard = ast.parse(
                f"if not {arr_param} or len({arr_param}) == 0:\n    return None"
            ).body[0]
            ast.fix_missing_locations(guard)
            func_def.body.insert(0, guard)
            ast.fix_missing_locations(tree)
            repaired = ast.unparse(tree)

            return RepairResult(
                original_code=code,
                repaired_code=repaired,
                repair_description=f"Added empty-collection guard for '{arr_param}'",
                repair_line=func_def.lineno,
            )
        except Exception:
            return None


def analyze_code(code: str, function_name: str = "", model_path: Optional[str] = None) -> SequentResult:
    """Convenience function for the full pipeline."""
    if model_path is None:
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'checkpoints', 'best_model.pt'
        )

    engine = SequentEngine(model_path=model_path)
    return engine.analyze(code, function_name)
