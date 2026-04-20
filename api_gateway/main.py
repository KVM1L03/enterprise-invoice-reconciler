"""FastAPI gateway — triggers Temporal batch reconciliation workflows."""

import asyncio
import logging
import os
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from functools import partial
from pathlib import Path

import httpx
from cachetools import TTLCache
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langfuse import Langfuse, get_client
from langfuse.api.core.api_error import ApiError
from pydantic import ValidationError
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.service import RPCError

from shared.schemas import FinOpsDailyPoint

logger = logging.getLogger(__name__)

INVOICES_DIR = Path(__file__).resolve().parent.parent / "mock_data" / "invoices"
TASK_QUEUE = "invoice-reconciliation-queue"
TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")

_telemetry_cache: TTLCache[int, list[FinOpsDailyPoint]] = TTLCache(maxsize=8, ttl=60)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Connect to Temporal and Langfuse once at startup, close on shutdown."""
    client = await Client.connect(TEMPORAL_ADDRESS)
    app.state.temporal_client = client
    logger.info("Temporal client connected (%s)", TEMPORAL_ADDRESS)

    langfuse_client = get_client()
    app.state.langfuse = langfuse_client
    logger.info("Langfuse client initialised")

    yield

    langfuse_client.shutdown()


app = FastAPI(title="Enterprise Invoice Reconciler", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/reconcile-batch", status_code=202)
async def reconcile_batch(request: Request) -> dict:
    """Fire-and-forget: start a batch reconciliation workflow."""
    invoice_files = sorted(INVOICES_DIR.glob("*.pdf"))

    if not invoice_files:
        raise HTTPException(
            status_code=404,
            detail="No PDF invoice files found in mock_data/invoices/",
        )

    # Pass ABSOLUTE PATHS (strings), not file contents — keeps Temporal
    # Event History small and lets the Activity do the I/O.
    file_paths: list[str] = [str(p) for p in invoice_files]

    workflow_id = f"batch-{uuid.uuid4()}"
    client: Client = request.app.state.temporal_client

    await client.start_workflow(
        "BatchReconciliationWorkflow",
        args=[file_paths],
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )

    logger.info(
        "Started workflow %s with %d PDF invoices", workflow_id, len(file_paths)
    )
    return {"message": "Batch processing started", "workflow_id": workflow_id}


@app.post("/upload-invoices", status_code=201)
async def upload_invoices(files: list[UploadFile] = File(...)) -> dict:
    """Save one or more uploaded PDF invoices to mock_data/invoices/."""
    INVOICES_DIR.mkdir(parents=True, exist_ok=True)

    saved: list[str] = []
    for file in files:
        filename = Path(file.filename or "unnamed.pdf").name

        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"Only PDF files allowed, got: {filename}",
            )

        content = await file.read()
        target = INVOICES_DIR / filename
        await asyncio.to_thread(target.write_bytes, content)
        saved.append(filename)
        logger.info("Saved uploaded file: %s (%d bytes)", filename, len(content))

    return {
        "message": f"Uploaded {len(saved)} file(s)",
        "count": len(saved),
        "files": saved,
    }


@app.get("/status/{workflow_id}")
async def get_workflow_status(workflow_id: str, request: Request) -> dict:
    """Poll the status of a batch reconciliation workflow."""
    client: Client = request.app.state.temporal_client
    handle = client.get_workflow_handle(workflow_id)

    try:
        desc = await handle.describe()
    except RPCError as exc:
        logger.error("Workflow %s not found: %s", workflow_id, exc)
        raise HTTPException(
            status_code=404,
            detail=f"Workflow '{workflow_id}' not found",
        ) from exc

    if desc.status == WorkflowExecutionStatus.COMPLETED:
        result = await handle.result()
        return {"status": "COMPLETED", "result": result}

    if desc.status == WorkflowExecutionStatus.FAILED:
        return {
            "status": "FAILED",
            "message": "The workflow encountered a critical non-recoverable error.",
        }

    return {"status": desc.status.name}


@app.get("/telemetry/finops")
async def get_finops_telemetry(
    request: Request,
    days: int = Query(default=7, ge=1, le=90),
) -> list[dict[str, object]]:
    """Aggregate LLM cost and invoice volume from Langfuse traces.

    Returns one FinOpsDailyPoint per day for the last *days* days.
    Results are cached in-memory for 60 seconds.
    """
    # TODO: Add auth before exposing publicly.
    if days in _telemetry_cache:
        cached = _telemetry_cache[days]
        return [p.model_dump(by_alias=True) for p in cached]

    langfuse: Langfuse = request.app.state.langfuse
    today = date.today()
    from_date = today - timedelta(days=days - 1)

    # Pre-fill every day with zeros so the chart has no gaps.
    cost_by_day: dict[str, float] = defaultdict(float)
    invoices_by_day: dict[str, set[str]] = defaultdict(set)
    for i in range(days):
        d = from_date + timedelta(days=i)
        cost_by_day[d.isoformat()] = 0.0
        invoices_by_day[d.isoformat()] = set()

    # Fetch traces from Langfuse for the requested window (SDK v4 public API).
    page = 1
    window_start = datetime(
        from_date.year,
        from_date.month,
        from_date.day,
        tzinfo=timezone.utc,
    )
    window_end = datetime(
        today.year,
        today.month,
        today.day,
        23,
        59,
        59,
        tzinfo=timezone.utc,
    )
    while True:
        try:
            list_traces = partial(
                langfuse.api.trace.list,
                name="invoice_reconciliation",
                from_timestamp=window_start,
                to_timestamp=window_end,
                page=page,
                limit=100,
            )
            traces_response = await asyncio.to_thread(list_traces)
        except (ApiError, httpx.HTTPError, OSError, ValidationError):
            logger.exception("Failed to fetch Langfuse traces (page %d)", page)
            break

        traces = traces_response.data
        if not traces:
            break

        for trace in traces:
            if trace.timestamp is None:
                continue
            day_key = trace.timestamp.date().isoformat()
            if day_key not in cost_by_day:
                continue
            total_cost = getattr(trace, "total_cost", None) or 0.0
            cost_by_day[day_key] += float(total_cost)
            invoices_by_day[day_key].add(trace.id)

        if len(traces) < 100:
            break
        page += 1

    points = [
        FinOpsDailyPoint(
            date=day,
            api_cost_usd=round(cost_by_day[day], 4),
            invoices_processed=len(invoices_by_day[day]),
        )
        for day in sorted(cost_by_day)
    ]

    _telemetry_cache[days] = points
    return [p.model_dump(by_alias=True) for p in points]
