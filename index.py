```python
import json
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

DATA_FILE = Path(__file__).with_name("telemetry.jsonl")


class MetricsRequest(BaseModel):
    regions: list[str]
    threshold_ms: float = 180


@app.get("/")
def home():
    return {"message": "eShopCo telemetry API is running"}


@app.options("/")
def options_root():
    return Response(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        },
    )


@app.post("/")
def calculate_metrics(request: MetricsRequest):
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            records = json.load(f)

    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Telemetry data file not found",
        )

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail="Telemetry file contains invalid JSON",
        )

    regions_result = {}

    for region in request.regions:
        rows = [
            record
            for record in records
            if record["region"].lower() == region.lower()
        ]

        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No records found for region: {region}",
            )

        latencies = np.array(
            [float(record["latency_ms"]) for record in rows]
        )

        uptimes = np.array(
            [float(record["uptime_pct"]) for record in rows]
        )

        regions_result[region] = {
            "avg_latency": float(np.mean(latencies)),
            "p95_latency": float(np.percentile(latencies, 95)),
            "avg_uptime": float(np.mean(uptimes)),
            "breaches": int(
                np.sum(latencies > request.threshold_ms)
            ),
        }

    return {"regions": regions_result}
```