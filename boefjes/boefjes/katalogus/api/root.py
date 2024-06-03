import json
import logging.config
from typing import Any

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel, Field

from boefjes.config import settings
from boefjes.katalogus.api import organisations, plugins
from boefjes.katalogus.api import settings as settings_router
from boefjes.katalogus.storage.interfaces import StorageError
from boefjes.katalogus.version import __version__

with settings.log_cfg.open() as f:
    logging.config.dictConfig(json.load(f))

logger = logging.getLogger(__name__)

app = FastAPI(title="KAT-alogus API", version=__version__)

if settings.span_export_grpc_endpoint is not None:
    logger.info("Setting up instrumentation with span exporter endpoint [%s]", settings.span_export_grpc_endpoint)

    FastAPIInstrumentor.instrument_app(app)
    Psycopg2Instrumentor().instrument()
    RequestsInstrumentor().instrument()

    resource = Resource(attributes={SERVICE_NAME: "katalogus"})
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=str(settings.span_export_grpc_endpoint)))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    logger.debug("Finished setting up instrumentation")

router = APIRouter()
router.include_router(organisations.router)
router.include_router(plugins.router)
router.include_router(settings_router.router)


app.include_router(router, prefix="/v1")


@app.exception_handler(StorageError)
def entity_not_found_handler(request: Request, exc: StorageError):
    logger.exception("some error", exc_info=exc)

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": exc.message},
    )


class ServiceHealth(BaseModel):
    service: str
    healthy: bool = False
    version: str | None = None
    additional: Any = None
    results: list["ServiceHealth"] = Field(default_factory=list)


ServiceHealth.update_forward_refs()


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/health")


@app.get("/health", response_model=ServiceHealth)
def health() -> ServiceHealth:
    return ServiceHealth(service="katalogus", healthy=True, version=__version__)


@router.get("/v1/", include_in_schema=False)
def v1_root() -> RedirectResponse:
    return RedirectResponse(url="/v1/docs")