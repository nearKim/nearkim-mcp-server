from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.bootstrap.container import Container
from src.bootstrap.settings.settings import Settings
from src.domain.exceptions import WebhookValidationException


logger = logging.getLogger(__name__)


class WebhookRequest(BaseModel):
    event_name: str
    event_data: Dict[str, Any]
    initiator: Optional[Dict[str, Any]] = None
    version: Optional[str] = None


class ClassifyTaskRequest(BaseModel):
    task_id: str
    force_reclassify: bool = False


class BulkClassifyRequest(BaseModel):
    project_id: Optional[str] = None
    filter_str: Optional[str] = None
    force_reclassify: bool = False
    limit: int = 100


class ManualOverrideRequest(BaseModel):
    task_id: str
    enable: bool = True


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    services: Dict[str, str]


class ClassificationResult(BaseModel):
    task_id: str
    quadrant: str
    urgent: bool
    important: bool
    reason: str
    success: bool
    error: Optional[str] = None


class BulkClassificationResponse(BaseModel):
    total: int
    successful: int
    failed: int
    results: List[ClassificationResult]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Eisenhower MCP API server...")
    settings = Settings.from_env()
    container = Container(settings)
    await container.initialize()
    app.state.container = container
    app.state.settings = settings
    
    yield
    logger.info("Shutting down Eisenhower MCP API server...")
    await container.shutdown()


app = FastAPI(
    title="Eisenhower MCP Server",
    description="API for Eisenhower Matrix task classification",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    container: Container = request.app.state.container
    
    services = {
        "todoist": "healthy" if container.todoist_adapter else "unavailable",
        "classifier": "healthy" if container.classifier_service else "unavailable",
        "database": "healthy" if container.decision_repository else "unavailable",
    }
    
    if container.calendar_service:
        services["calendar"] = "healthy"
    
    if container.email_service:
        services["email"] = "healthy"
    
    return HealthResponse(
        status="healthy" if all(v == "healthy" for v in services.values()) else "degraded",
        services=services
    )


@app.post("/webhook/todoist", status_code=status.HTTP_200_OK)
async def todoist_webhook(
    request: Request,
    webhook_data: WebhookRequest,
    x_todoist_hmac_sha256: Optional[str] = Header(None)
) -> Dict[str, Any]:
    container: Container = request.app.state.container
    webhook_service = container.webhook_service
    raw_body = await request.body()
    
    try:
        response = await webhook_service.handle(
            event_name=webhook_data.event_name,
            payload=webhook_data.event_data,
            raw_payload=raw_body,
            signature=x_todoist_hmac_sha256
        )
        
        return {
            "status": "success",
            "event": webhook_data.event_name,
            "task_id": response.task_id,
            "action": response.action,
            "details": response.details
        }
        
    except WebhookValidationException as e:
        logger.warning(f"Webhook validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.post("/classify", response_model=ClassificationResult)
async def classify_task(
    request: Request,
    classify_request: ClassifyTaskRequest
) -> ClassificationResult:
    container: Container = request.app.state.container
    todoist_service = container.todoist_service
    
    try:
        task = await container.todoist_adapter.get_task(classify_request.task_id)
        if not classify_request.force_reclassify:
            if await container.todoist_adapter.should_ignore_task(task):
                return ClassificationResult(
                    task_id=classify_request.task_id,
                    quadrant="ignored",
                    urgent=False,
                    important=False,
                    reason="Task is in ignore list",
                    success=True
                )
        decision = await container.classifier_service.classify(task)
        await container.todoist_adapter.apply_eisenhower(classify_request.task_id, decision)
        await todoist_service.save_decision(classify_request.task_id, decision)
        
        return ClassificationResult(
            task_id=classify_request.task_id,
            quadrant=decision.quadrant,
            urgent=decision.urgent,
            important=decision.important,
            reason=decision.reason,
            success=True
        )
        
    except Exception as e:
        logger.error(f"Classification failed for task {classify_request.task_id}: {e}")
        return ClassificationResult(
            task_id=classify_request.task_id,
            quadrant="error",
            urgent=False,
            important=False,
            reason=str(e),
            success=False,
            error=str(e)
        )


@app.post("/classify/bulk", response_model=BulkClassificationResponse)
async def classify_bulk(
    request: Request,
    bulk_request: BulkClassifyRequest
) -> BulkClassificationResponse:
    container: Container = request.app.state.container
    
    tasks = await container.todoist_adapter.fetch_tasks(
        project_id=bulk_request.project_id,
        filter_str=bulk_request.filter_str
    )
    tasks = tasks[:bulk_request.limit]
    
    results = []
    successful = 0
    failed = 0
    
    for task in tasks:
        try:
            if not bulk_request.force_reclassify:
                if await container.todoist_adapter.should_ignore_task(task):
                    results.append(ClassificationResult(
                        task_id=task.todoist_id,
                        quadrant="ignored",
                        urgent=False,
                        important=False,
                        reason="Task is in ignore list",
                        success=True
                    ))
                    successful += 1
                    continue
            decision = await container.classifier_service.classify(task)
            await container.todoist_adapter.apply_eisenhower(task.todoist_id, decision)
            
            results.append(ClassificationResult(
                task_id=task.todoist_id,
                quadrant=decision.quadrant,
                urgent=decision.urgent,
                important=decision.important,
                reason=decision.reason,
                success=True
            ))
            successful += 1
            
        except Exception as e:
            logger.error(f"Failed to classify task {task.todoist_id}: {e}")
            results.append(ClassificationResult(
                task_id=task.todoist_id,
                quadrant="error",
                urgent=False,
                important=False,
                reason=str(e),
                success=False,
                error=str(e)
            ))
            failed += 1
    
    return BulkClassificationResponse(
        total=len(tasks),
        successful=successful,
        failed=failed,
        results=results
    )


@app.post("/override", status_code=status.HTTP_204_NO_CONTENT)
async def set_manual_override(
    request: Request,
    override_request: ManualOverrideRequest
) -> None:
    container: Container = request.app.state.container
    
    try:
        await container.todoist_adapter.set_manual_override(
            override_request.task_id,
            override_request.enable
        )
    except Exception as e:
        logger.error(f"Failed to set override for task {override_request.task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/projects")
async def get_projects(request: Request) -> List[Dict[str, Any]]:
    container: Container = request.app.state.container
    
    try:
        projects = await container.todoist_adapter.get_projects()
        return projects
    except Exception as e:
        logger.error(f"Failed to fetch projects: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/decisions/{task_id}")
async def get_decision(request: Request, task_id: str) -> Dict[str, Any]:
    container: Container = request.app.state.container
    
    try:
        record = await container.decision_repository.get(task_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No decision found for task {task_id}"
            )
        
        return {
            "task_id": record.todoist_id,
            "quadrant": record.quadrant,
            "urgent": record.urgent,
            "important": record.important,
            "reason": record.reason,
            "applied_mode": record.applied_mode,
            "updated_at": record.updated_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch decision for task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.delete("/decisions/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_decision(request: Request, task_id: str) -> None:
    container: Container = request.app.state.container
    
    try:
        await container.decision_repository.delete(task_id)
    except Exception as e:
        logger.error(f"Failed to delete decision for task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.exception_handler(WebhookValidationException)
async def webhook_validation_exception_handler(request: Request, exc: WebhookValidationException):
    return JSONResponse(
        status_code=401,
        content={"detail": str(exc)}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )