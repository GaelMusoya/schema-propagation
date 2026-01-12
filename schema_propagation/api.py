from fastapi import FastAPI
from prometheus_client import make_asgi_app, Counter, Histogram, Gauge

from .routes import router

app = FastAPI(title="Schema Propagation", version="1.0.0")
app.include_router(router)

# Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

propagation_total = Counter("schema_propagation_total", "Total propagations", ["status", "schema_type"])
propagation_duration = Histogram(
    "schema_propagation_duration_seconds", "Duration per database",
    ["schema_type"], buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)
propagation_rate = Gauge("schema_propagation_rate_per_second", "Current propagation rate")


@app.get("/health")
async def health():
    return {"status": "ok"}
