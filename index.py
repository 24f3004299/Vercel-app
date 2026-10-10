```python
import json
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Vercel requires a top-level FastAPI instance named "app"
app = FastAPI(
    title="eShopCo Telemetry API",
    version="1.0.0",
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Locate telemetry.jsonl in the same directory as index.py
DATA_FILE = Path(__file__).parent / "telemetry.jsonl"


class MetricsRequest(BaseModel):
    regions: list[str]
    threshold_ms: float = 180.0


def load_records():
    """Load either a JSON array or newline-delimited JSON records."""
    try:
        content = DATA_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Telemetry data file not found",
        )

    if not content:
        raise HTTPException(
            status_code=500,
            detail="Telemetry data file is empty",
        )

    try:
        # Your supplied data is a JSON array.
        records = json.loads(content)
    except json.JSONDecodeError:
        # Also support genuine JSON Lines files.
        try:
            records = [
                json.loads(line)
                for line in content.splitlines()
                if line.strip()
            ]
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=500,
                detail="Telemetry file contains invalid JSON",
            )

    if not isinstance(records, list):
        raise HTTPException(
            status_code=500,
            detail="Telemetry data must contain a list of records",
        )

    return records


@app.get("/")
def home():
    return {"message": "eShopCo telemetry API is running"}


@app.post("/")
def calculate_metrics(request: MetricsRequest):
    records = load_records()
    regions_result = {}

    for region in request.regions:
        rows = [
            record
            for record in records
            if str(record.get("region", "")).lower()
            == region.lower()
        ]

        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No records found for region: {region}",
            )

        try:
            latencies = np.array(
                [float(record["latency_ms"]) for record in rows],
                dtype=float,
            )
            uptimes = np.array(
                [float(record["uptime_pct"]) for record in rows],
                dtype=float,
            )
        except (KeyError, TypeError, ValueError):
            raise HTTPException(
                status_code=500,
                detail=f"Invalid telemetry record for region: {region}",
            )

        regions_result[region] = {
            "avg_latency": float(np.mean(latencies)),
            "p95_latency": float(np.percentile(latencies, 95)),
            "avg_uptime": float(np.mean(uptimes)),
            "breaches": int(
                np.sum(latencies > request.threshold_ms)
            ),
        }

    # The response must contain a top-level "regions" object.
    return {"regions": regions_result}
```