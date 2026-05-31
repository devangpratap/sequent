"""
FastAPI backend for Sequent.

Endpoints:
- POST /analyze — run full neurosymbolic pipeline on code
- GET /health — health check
- GET /model/info — model metadata
"""

import os
import sys
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verifier.neurosymbolic import SequentEngine

app = FastAPI(
    title="Sequent",
    description="Neural Formal Verification Engine — GNN proposes, Z3 disposes",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load engine once at startup
MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'checkpoints', 'best_model.pt'
)

engine = None


@app.on_event("startup")
async def startup():
    global engine
    if os.path.exists(MODEL_PATH):
        engine = SequentEngine(model_path=MODEL_PATH)
        print(f"Sequent engine loaded (model: {MODEL_PATH})")
    else:
        engine = SequentEngine()
        print("Warning: No model found, running Z3-only mode")


class AnalyzeRequest(BaseModel):
    code: str = Field(..., description="Python function source code to analyze")
    function_name: str = Field(default="", description="Optional function name")


class GNNResult(BaseModel):
    buggy: bool
    confidence: float
    bug_lines: list[int]
    inference_ms: float


class Z3Check(BaseModel):
    property_name: str
    result: str
    description: str
    line: int | None = None
    counterexample: dict | None = None
    time_ms: float


class Z3Result(BaseModel):
    result: str
    checks: list[Z3Check]
    bugs_found: int
    time_ms: float


class RepairInfo(BaseModel):
    applied: bool
    description: str
    repaired_code: str | None = None
    verified: bool


class AttentionEdge(BaseModel):
    src_line: int
    dst_line: int
    weight: float


class AnalyzeResponse(BaseModel):
    function_name: str
    is_buggy: bool
    consensus: str
    total_time_ms: float
    gnn: GNNResult | None = None
    z3: Z3Result | None = None
    repair: RepairInfo | None = None
    node_scores: list[float] | None = None
    node_lines: list[int] | None = None
    attention: list[AttentionEdge] | None = None


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not loaded")

    if not request.code.strip():
        raise HTTPException(status_code=400, detail="Code cannot be empty")

    result = engine.analyze(request.code, request.function_name)

    # Build response
    response = AnalyzeResponse(
        function_name=result.function_name,
        is_buggy=result.consensus_buggy,
        consensus=result.consensus_description,
        total_time_ms=round(result.total_time_ms, 1),
    )

    if result.gnn_prediction:
        response.gnn = GNNResult(
            buggy=result.gnn_prediction.is_buggy,
            confidence=round(result.gnn_prediction.buggy_confidence, 4),
            bug_lines=result.gnn_prediction.bug_lines,
            inference_ms=round(result.gnn_prediction.inference_time_ms, 1),
        )
        response.node_scores = [round(s, 4) for s in result.gnn_prediction.node_scores]
        if result.gnn_prediction.attention_edges:
            response.attention = [
                AttentionEdge(**e) for e in result.gnn_prediction.attention_edges
            ]
        # Get node lines from the graph
        from model.ast_to_graph import code_to_graph
        graph = code_to_graph(request.code.strip())
        if graph:
            response.node_lines = graph['node_lines']

    if result.verification:
        z3_checks = []
        for check in result.verification.checks:
            z3_checks.append(Z3Check(
                property_name=check.property_name,
                result=check.result.value,
                description=check.description,
                line=check.line,
                counterexample=check.counterexample,
                time_ms=round(check.time_ms, 2),
            ))
        response.z3 = Z3Result(
            result=result.verification.overall_result.value,
            checks=z3_checks,
            bugs_found=len(result.verification.counterexamples),
            time_ms=round(result.verification.total_time_ms, 1),
        )

    if result.repair:
        response.repair = RepairInfo(
            applied=True,
            description=result.repair.repair_description,
            repaired_code=result.repair.repaired_code,
            verified=result.repair.verified,
        )

    return response


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model_loaded": engine is not None and engine.model is not None,
        "device": str(engine.device) if engine else "none",
    }


@app.get("/model/info")
async def model_info():
    if not engine or not engine.model:
        return {"status": "no model loaded"}

    total_params = sum(p.numel() for p in engine.model.parameters())
    return {
        "total_parameters": total_params,
        "device": str(engine.device),
        "model_path": MODEL_PATH,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
