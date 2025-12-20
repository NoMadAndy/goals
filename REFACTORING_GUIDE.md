# Stellwerk Refactoring Guide

## Overview

This guide provides **immediate, actionable refactoring steps** to improve the current Stellwerk codebase incrementally, without requiring a full rewrite. These changes can be implemented gradually while maintaining backward compatibility.

---

## Quick Wins (Can Be Done Today)

### 1. Extract Configuration to TOML (Already Partially Done)

**Current State**: Settings in `settings.py` + `.env`  
**Improvement**: Extend `stellwerk.toml` support for all configuration

```toml
# stellwerk.toml - Extended
[server]
host = "127.0.0.1"
port = 8002
reload = false

[database]
url = "sqlite+pysqlite:///./data/stellwerk.db"

[openai]
api_key = "${OPENAI_API_KEY}"
base_url = "https://api.openai.com/v1"
model = "gpt-4o-mini"
timeout_seconds = 60
retries = 2

[planning]
max_routes = 20
max_tasks_per_route = 6
max_work_packages_per_task = 6
min_steps_per_package = 6
min_dod_items = 7
min_risks = 3
min_sources = 3
max_sources = 8
min_images = 1
max_images = 3

[debug]
enabled = false
max_events = 800
```

### 2. Split `app.py` Into Smaller Modules

**Current**: 591 lines in one file  
**Target**: ~100 lines per file

```
src/stellwerk/
├── api/
│   ├── __init__.py
│   ├── goals.py          # Goal CRUD endpoints
│   ├── planning.py       # Planning endpoints
│   ├── work_packages.py  # Work package endpoints
│   ├── people.py         # People management endpoints
│   └── debug.py          # Debug endpoints
├── app.py                # Just FastAPI app setup + middleware
└── ...
```

**Migration Script**:
```python
# src/stellwerk/api/goals.py
from fastapi import APIRouter, Form, Request
from stellwerk.repository import create_goal, delete_goal, get_goal, list_goals
from stellwerk.db import open_session, engine

router = APIRouter(prefix="/goals", tags=["goals"])

@router.post("")
async def create_goal_endpoint(
    title: str = Form(""),
    description: str = Form("")
):
    title = title.strip()
    if not title:
        return RedirectResponse(url="/", status_code=303)
    
    with open_session(engine) as session:
        goal_id = create_goal(session, title=title, description=description.strip())
    
    return RedirectResponse(url=f"/?goal={goal_id}", status_code=303)

@router.post("/{goal_id}/delete")
async def delete_goal_endpoint(goal_id: UUID):
    with open_session(engine) as session:
        delete_goal(session, goal_id)
    return RedirectResponse(url="/", status_code=303)
```

```python
# src/stellwerk/app.py (simplified)
from fastapi import FastAPI
from stellwerk.api import goals, planning, work_packages, people, debug

app = FastAPI(title="Goals", lifespan=lifespan)

# Include routers
app.include_router(goals.router)
app.include_router(planning.router)
app.include_router(work_packages.router)
app.include_router(people.router)
app.include_router(debug.router)

# Mount static files
app.mount("/static", StaticFiles(directory="src/stellwerk/static"), name="static")
```

### 3. Extract Prompt Templates to Separate Files

**Current**: Prompts hardcoded in `planner.py`  
**Improvement**: Use Jinja2 templates for prompts

```
src/stellwerk/
├── prompts/
│   ├── goal_decomposition.jinja2
│   ├── work_package_details.jinja2
│   └── plan_refinement.jinja2
└── planner.py
```

```python
# src/stellwerk/planner.py
from jinja2 import Environment, FileSystemLoader

prompt_env = Environment(
    loader=FileSystemLoader("src/stellwerk/prompts"),
    autoescape=False
)

def get_decomposition_prompt(goal: str, context: str) -> str:
    template = prompt_env.get_template("goal_decomposition.jinja2")
    return template.render(goal=goal, context=context)
```

```jinja2
{# src/stellwerk/prompts/goal_decomposition.jinja2 #}
Du bist ein Planungsassistent für eine App namens 'Goals'.
Ziel: Ein maximal detaillierter, VERZWEIGTER Plan als gerichteter azyklischer Graph (DAG) mit Merges.

Anforderungen:
- Bis zu 10 Abzweigungsebenen (Entscheidungen können auch auf Abzweigen erneut verzweigen).
- Merges sind erlaubt (mehrere Kanten können wieder auf denselben Knoten zeigen).
- Keine Zyklen (DAG). Der Graph muss am Ende zu einem Ziel-Endknoten führen.
- 6–20 Knoten (routes) insgesamt.
- Pro Route: 2–6 Aufgaben. Pro Aufgabe: 2–6 Arbeitspakete.

{# ... rest of prompt ... #}

Eingabe: {{ goal }}
Kontext: {{ context }}
```

### 4. Add Type Hints Everywhere

**Current**: Some functions lack complete type hints  
**Improvement**: Full type coverage

```python
# Before
def create_goal(session, title, description, *, log=None):
    ...

# After
from typing import Callable
from uuid import UUID

def create_goal(
    session: Session,
    title: str,
    description: str,
    *,
    log: Callable[[str, str, dict | None], None] | None = None
) -> UUID:
    ...
```

### 5. Extract Magic Numbers to Constants

```python
# src/stellwerk/constants.py
from enum import IntEnum

class PlanLimits(IntEnum):
    MIN_ROUTES = 6
    MAX_ROUTES = 20
    MIN_TASKS = 2
    MAX_TASKS = 6
    MIN_WORK_PACKAGES = 2
    MAX_WORK_PACKAGES = 6
    MIN_STEPS = 6
    MIN_DOD_ITEMS = 7
    MIN_RISKS = 3
    MIN_SOURCES = 3
    MAX_SOURCES = 8
    MIN_IMAGES = 1
    MAX_IMAGES = 3
    
class WorkPackageLimits(IntEnum):
    MIN_LENGTH = 1
    MAX_LENGTH = 8
    MIN_GRADE = 0
    MAX_GRADE = 10

class DebugLimits(IntEnum):
    MAX_EVENTS = 800
    MAX_SUBSCRIBERS = 50
    QUEUE_SIZE = 200
```

```python
# Usage in planner.py
from stellwerk.constants import PlanLimits, WorkPackageLimits

prompt = f"""
Anforderungen:
- {PlanLimits.MIN_ROUTES}–{PlanLimits.MAX_ROUTES} Knoten (routes) insgesamt.
- Pro Route: {PlanLimits.MIN_TASKS}–{PlanLimits.MAX_TASKS} Aufgaben.
"""
```

---

## Medium-Term Improvements (This Week)

### 6. Add Dependency Injection for Database

**Current**: `engine` is a global variable  
**Improvement**: Pass engine as dependency

```python
# src/stellwerk/dependencies.py
from fastapi import Depends
from sqlalchemy.orm import Session
from stellwerk.db import create_db_engine, open_session

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine

def get_session() -> Session:
    engine = get_engine()
    with open_session(engine) as session:
        yield session
```

```python
# src/stellwerk/api/goals.py
from fastapi import Depends
from sqlalchemy.orm import Session
from stellwerk.dependencies import get_session

@router.post("")
async def create_goal_endpoint(
    title: str = Form(""),
    description: str = Form(""),
    session: Session = Depends(get_session)
):
    title = title.strip()
    if not title:
        return RedirectResponse(url="/", status_code=303)
    
    goal_id = create_goal(session, title=title, description=description.strip())
    return RedirectResponse(url=f"/?goal={goal_id}", status_code=303)
```

### 7. Create Service Layer

**Current**: Controllers directly call repository  
**Improvement**: Add service layer for business logic

```python
# src/stellwerk/services/goal_service.py
from uuid import UUID
from sqlalchemy.orm import Session
from stellwerk.models import Goal
from stellwerk.repository import (
    create_goal as repo_create_goal,
    get_goal as repo_get_goal,
    list_goals as repo_list_goals,
    delete_goal as repo_delete_goal
)

class GoalService:
    """Business logic for goal management."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create_goal(self, title: str, description: str) -> UUID:
        """Create a new goal with validation."""
        # Validation logic
        if not title or len(title.strip()) < 3:
            raise ValueError("Goal title must be at least 3 characters")
        
        if len(title) > 200:
            raise ValueError("Goal title too long")
        
        # Business logic
        return repo_create_goal(
            self.session,
            title=title.strip(),
            description=description.strip()
        )
    
    def get_goal(self, goal_id: UUID) -> Goal | None:
        """Retrieve goal with authorization check."""
        goal = repo_get_goal(self.session, goal_id)
        # Could add permission checks here
        return goal
    
    def delete_goal(self, goal_id: UUID) -> None:
        """Delete goal with cascade handling."""
        # Could add soft delete, archival, etc.
        repo_delete_goal(self.session, goal_id)
```

### 8. Improve Error Handling

**Current**: Generic exceptions  
**Improvement**: Custom exception hierarchy

```python
# src/stellwerk/exceptions.py
class StellwerkError(Exception):
    """Base exception for Stellwerk."""
    pass

class ValidationError(StellwerkError):
    """Data validation failed."""
    pass

class PlanningError(StellwerkError):
    """AI planning failed."""
    pass

class OpenAIError(PlanningError):
    """OpenAI API error."""
    pass

class SchemaValidationError(PlanningError):
    """Plan doesn't match expected schema."""
    pass

class NotFoundError(StellwerkError):
    """Resource not found."""
    pass
```

```python
# Usage
from stellwerk.exceptions import ValidationError, OpenAIError

async def create_goal(title: str) -> Goal:
    if not title:
        raise ValidationError("Goal title is required")
    
    try:
        plan = await openai_plan(...)
    except httpx.ReadTimeout:
        raise OpenAIError("OpenAI request timed out") from None
    except ValueError as e:
        raise SchemaValidationError(f"Invalid plan structure: {e}") from e
```

### 9. Add Request/Response Models

**Current**: Mix of Form data and direct parameters  
**Improvement**: Pydantic models for validation

```python
# src/stellwerk/schemas.py
from pydantic import BaseModel, Field, validator

class CreateGoalRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(default="", max_length=2000)
    
    @validator("title")
    def title_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()

class GoalResponse(BaseModel):
    id: UUID
    title: str
    description: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class PlanRequest(BaseModel):
    goal_id: UUID
    context: str = Field(default="", max_length=5000)
```

```python
# Usage
@router.post("", response_model=GoalResponse)
async def create_goal_endpoint(
    request: CreateGoalRequest,
    session: Session = Depends(get_session)
):
    service = GoalService(session)
    goal_id = service.create_goal(request.title, request.description)
    goal = service.get_goal(goal_id)
    return GoalResponse.from_orm(goal)
```

### 10. Add Logging Consistently

**Current**: Mix of debug_log and no logging  
**Improvement**: Structured logging everywhere

```python
# src/stellwerk/logging_config.py
import structlog

def configure_logging(debug: bool = False):
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

logger = structlog.get_logger()
```

```python
# Usage in services
from stellwerk.logging_config import logger

class GoalService:
    def create_goal(self, title: str, description: str) -> UUID:
        logger.info(
            "goal.create.started",
            title_length=len(title),
            has_description=bool(description)
        )
        
        try:
            goal_id = repo_create_goal(...)
            logger.info("goal.create.success", goal_id=str(goal_id))
            return goal_id
        except Exception as e:
            logger.error(
                "goal.create.failed",
                error=str(e),
                error_type=type(e).__name__
            )
            raise
```

---

## Long-Term Refactoring (This Month)

### 11. Introduce Repository Pattern Properly

**Current**: Repository functions with session parameter  
**Improvement**: Repository class with encapsulated session

```python
# src/stellwerk/repositories/goal_repository.py
from abc import ABC, abstractmethod
from uuid import UUID
from sqlalchemy.orm import Session
from stellwerk.models import Goal

class GoalRepository(ABC):
    """Abstract goal repository."""
    
    @abstractmethod
    def create(self, goal: Goal) -> UUID:
        pass
    
    @abstractmethod
    def get(self, goal_id: UUID) -> Goal | None:
        pass
    
    @abstractmethod
    def list_all(self) -> list[Goal]:
        pass
    
    @abstractmethod
    def update(self, goal: Goal) -> None:
        pass
    
    @abstractmethod
    def delete(self, goal_id: UUID) -> None:
        pass

class SQLAlchemyGoalRepository(GoalRepository):
    """SQLAlchemy implementation of goal repository."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, goal: Goal) -> UUID:
        row = GoalRow(
            id=str(goal.id),
            title=goal.title,
            description=goal.description,
            status=goal.status.value,
            created_at=goal.created_at,
        )
        self.session.add(row)
        self.session.commit()
        return goal.id
    
    def get(self, goal_id: UUID) -> Goal | None:
        row = self.session.get(GoalRow, str(goal_id))
        if not row:
            return None
        return row_to_goal(row)
    
    # ... other methods
```

### 12. Extract AI Provider Interface

**Current**: OpenAI logic embedded in planner  
**Improvement**: Pluggable AI providers

```python
# src/stellwerk/ai/base.py
from abc import ABC, abstractmethod
from stellwerk.models import Goal

class AIProvider(ABC):
    """Abstract AI provider interface."""
    
    @abstractmethod
    async def generate_plan(
        self,
        goal: str,
        context: str
    ) -> Goal | None:
        """Generate a complete plan for the goal."""
        pass
    
    @abstractmethod
    async def refine_plan(
        self,
        plan: Goal,
        feedback: str
    ) -> Goal | None:
        """Refine an existing plan based on feedback."""
        pass

# src/stellwerk/ai/openai_provider.py
class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str, base_url: str):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
    
    async def generate_plan(self, goal: str, context: str) -> Goal | None:
        # Existing openai_plan logic
        pass
```

### 13. Add Plan Validation Layer

```python
# src/stellwerk/validators/plan_validator.py
from dataclasses import dataclass
from stellwerk.models import Goal

@dataclass
class ValidationIssue:
    severity: str  # 'error', 'warning', 'info'
    message: str
    location: str  # e.g., "routes[0].tasks[1]"

@dataclass
class ValidationResult:
    is_valid: bool
    issues: list[ValidationIssue]
    score: float  # 0.0-1.0

class PlanValidator:
    """Validates AI-generated plans."""
    
    def validate(self, plan: Goal) -> ValidationResult:
        issues = []
        
        # Check graph structure
        issues.extend(self._validate_graph_structure(plan))
        
        # Check work package quality
        issues.extend(self._validate_work_packages(plan))
        
        # Check route connectivity
        issues.extend(self._validate_connectivity(plan))
        
        # Calculate score
        errors = sum(1 for i in issues if i.severity == 'error')
        warnings = sum(1 for i in issues if i.severity == 'warning')
        score = max(0.0, 1.0 - (errors * 0.2 + warnings * 0.05))
        
        return ValidationResult(
            is_valid=errors == 0,
            issues=issues,
            score=score
        )
    
    def _validate_graph_structure(self, plan: Goal) -> list[ValidationIssue]:
        issues = []
        
        # Check for cycles (topological sort)
        if self._has_cycle(plan):
            issues.append(ValidationIssue(
                severity='error',
                message='Graph contains cycle',
                location='graph'
            ))
        
        # Check for unreachable nodes
        unreachable = self._find_unreachable_nodes(plan)
        for node_id in unreachable:
            issues.append(ValidationIssue(
                severity='warning',
                message=f'Route {node_id} is unreachable',
                location=f'routes[{node_id}]'
            ))
        
        return issues
    
    def _validate_work_packages(self, plan: Goal) -> list[ValidationIssue]:
        issues = []
        
        for route_idx, route in enumerate(plan.routes):
            for task_idx, task in enumerate(route.tasks):
                for wp_idx, wp in enumerate(task.work_packages):
                    location = f'routes[{route_idx}].tasks[{task_idx}].work_packages[{wp_idx}]'
                    
                    # Check markdown structure
                    if not self._has_required_sections(wp.notes):
                        issues.append(ValidationIssue(
                            severity='error',
                            message='Missing required markdown sections',
                            location=location
                        ))
                    
                    # Check URL count
                    url_count = self._count_urls(wp.notes)
                    if url_count < 3:
                        issues.append(ValidationIssue(
                            severity='warning',
                            message=f'Only {url_count} URLs found, expected at least 3',
                            location=location
                        ))
        
        return issues
```

### 14. Add Caching Layer

```python
# src/stellwerk/cache.py
from abc import ABC, abstractmethod
from typing import Any
import json
import hashlib

class Cache(ABC):
    @abstractmethod
    async def get(self, key: str) -> Any | None:
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> None:
        pass

class InMemoryCache(Cache):
    """Simple in-memory cache for development."""
    
    def __init__(self):
        self._cache: dict[str, tuple[Any, float]] = {}
    
    async def get(self, key: str) -> Any | None:
        if key in self._cache:
            value, expires_at = self._cache[key]
            if expires_at > time.time():
                return value
            del self._cache[key]
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        expires_at = time.time() + ttl
        self._cache[key] = (value, expires_at)
    
    async def delete(self, key: str) -> None:
        self._cache.pop(key, None)

class PlanCache:
    """Specialized cache for AI plans."""
    
    def __init__(self, cache: Cache):
        self.cache = cache
    
    def _make_key(self, goal: str, context: str) -> str:
        """Create deterministic cache key."""
        content = f"{goal}|{context}"
        return f"plan:{hashlib.sha256(content.encode()).hexdigest()}"
    
    async def get_plan(self, goal: str, context: str) -> Goal | None:
        """Retrieve cached plan if available."""
        key = self._make_key(goal, context)
        data = await self.cache.get(key)
        
        if data:
            return Goal.model_validate_json(data)
        return None
    
    async def cache_plan(
        self,
        goal: str,
        context: str,
        plan: Goal,
        ttl: int = 3600
    ) -> None:
        """Cache a generated plan."""
        key = self._make_key(goal, context)
        data = plan.model_dump_json()
        await self.cache.set(key, data, ttl)
```

### 15. Add Background Tasks with Celery

```python
# src/stellwerk/tasks.py
from celery import Celery
from stellwerk.planner import openai_plan
from stellwerk.repository import apply_plan

celery = Celery(
    'stellwerk',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

@celery.task
async def create_plan_async(goal_id: str, goal: str, context: str):
    """Create plan in background."""
    result = await openai_plan(PlanRequest(raw_goal=goal, context=context))
    
    if result.goal:
        with open_session(engine) as session:
            apply_plan(session, UUID(goal_id), result.goal, result.source)
        return {'status': 'success', 'goal_id': goal_id}
    
    return {'status': 'error', 'error': result.error}
```

```python
# Usage in API
@router.post("/{goal_id}/plan/async")
async def plan_goal_async(goal_id: UUID, context: str = Form("")):
    """Trigger async plan creation."""
    with open_session(engine) as session:
        goal = get_goal(session, goal_id)
    
    if not goal:
        raise HTTPException(404, "Goal not found")
    
    # Queue task
    task = create_plan_async.delay(
        str(goal_id),
        goal.title,
        context
    )
    
    return JSONResponse({
        'task_id': task.id,
        'status': 'queued'
    })

@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Check task status."""
    task = celery.AsyncResult(task_id)
    
    return JSONResponse({
        'task_id': task_id,
        'status': task.state,
        'result': task.result if task.ready() else None
    })
```

---

## Testing Improvements

### 16. Add Fixtures for Common Test Data

```python
# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from stellwerk.db import Base, open_session
from stellwerk.models import Goal, Route, Task, WorkPackage

@pytest.fixture
def in_memory_engine():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()

@pytest.fixture
def session(in_memory_engine):
    """Provide a database session for tests."""
    with open_session(in_memory_engine) as sess:
        yield sess

@pytest.fixture
def sample_goal() -> Goal:
    """Provide a sample goal for testing."""
    return Goal(
        title="Learn Python",
        description="Master Python programming",
        routes=[
            Route(
                title="Basics",
                tasks=[
                    Task(
                        title="Setup Environment",
                        work_packages=[
                            WorkPackage(
                                title="Install Python",
                                notes="## Kurzfassung\nInstall Python 3.11+",
                                length=2,
                                grade=1
                            )
                        ]
                    )
                ]
            )
        ]
    )

@pytest.fixture
def mock_openai_response():
    """Mock successful OpenAI response."""
    return {
        "title": "Learn Python",
        "description": "A plan to learn Python",
        "routes": [
            {
                "id": "r0",
                "title": "Basics",
                "kind": "trunk",
                "phase": 0,
                "tasks": [...]
            }
        ],
        "edges": [],
        "decisions": []
    }
```

### 17. Add Integration Tests

```python
# tests/integration/test_planning_flow.py
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_complete_planning_flow(session, sample_goal):
    """Test end-to-end planning flow."""
    # Create goal
    goal_id = repo_create_goal(
        session,
        title="Test Goal",
        description="Test Description"
    )
    
    # Mock OpenAI response
    with patch('stellwerk.planner.httpx.AsyncClient') as mock_client:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': '{"title": "Test", "routes": [...]}'
                }
            }]
        }
        mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
        
        # Generate plan
        result = await openai_plan(PlanRequest(raw_goal="Test Goal"))
    
    # Verify plan
    assert result.goal is not None
    assert len(result.goal.routes) > 0
    
    # Apply plan
    apply_plan(session, goal_id, result.goal, result.source)
    
    # Retrieve and verify
    goal = repo_get_goal(session, goal_id)
    assert goal is not None
    assert len(goal.routes) > 0
```

### 18. Add Performance Tests

```python
# tests/performance/test_plan_generation.py
import time
import pytest

@pytest.mark.performance
async def test_plan_generation_performance():
    """Ensure plan generation completes within time limit."""
    start = time.perf_counter()
    
    result = await openai_plan(PlanRequest(
        raw_goal="Build a web application",
        context=""
    ))
    
    duration = time.perf_counter() - start
    
    # Should complete within 60 seconds
    assert duration < 60.0, f"Plan generation took {duration:.2f}s"
    assert result.goal is not None

@pytest.mark.performance
def test_database_query_performance(session, sample_goal):
    """Ensure database queries are efficient."""
    # Insert 100 goals
    goal_ids = []
    for i in range(100):
        goal_id = repo_create_goal(
            session,
            title=f"Goal {i}",
            description=f"Description {i}"
        )
        goal_ids.append(goal_id)
    
    # Measure list query
    start = time.perf_counter()
    goals = repo_list_goals(session)
    duration = time.perf_counter() - start
    
    assert len(goals) == 100
    assert duration < 0.1, f"List query took {duration:.2f}s"
```

---

## Documentation Improvements

### 19. Add Docstrings Everywhere

```python
# Use Google-style docstrings
def create_goal(
    session: Session,
    title: str,
    description: str,
    *,
    log: Callable | None = None
) -> UUID:
    """Create a new goal in the database.
    
    Args:
        session: Active database session
        title: Goal title (required, 3-200 chars)
        description: Optional goal description
        log: Optional logging callback
    
    Returns:
        UUID of the created goal
    
    Raises:
        ValueError: If title is empty or too long
        SQLAlchemyError: If database operation fails
    
    Example:
        >>> with open_session(engine) as session:
        ...     goal_id = create_goal(session, "Learn Python", "Master the basics")
        ...     print(f"Created goal: {goal_id}")
    """
    ...
```

### 20. Generate API Documentation

```python
# src/stellwerk/app.py
app = FastAPI(
    title="Stellwerk API",
    description="AI-powered goal planning and tracking system",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "goals",
            "description": "Goal management operations"
        },
        {
            "name": "planning",
            "description": "AI planning operations"
        },
        {
            "name": "work-packages",
            "description": "Work package operations"
        }
    ]
)
```

---

## Priority Order

### Immediate (Do Today)
1. ✅ Split `app.py` into modules
2. ✅ Extract prompt templates
3. ✅ Add constants file
4. ✅ Add type hints

### Short-Term (This Week)
5. ✅ Add dependency injection
6. ✅ Create service layer
7. ✅ Improve error handling
8. ✅ Add request/response models

### Medium-Term (This Month)
9. ✅ Introduce repository pattern
10. ✅ Extract AI provider interface
11. ✅ Add plan validation
12. ✅ Add caching layer

### Long-Term (Next Month)
13. ✅ Add background tasks
14. ✅ Add comprehensive tests
15. ✅ Generate documentation

---

## Migration Checklist

For each refactoring:
- [ ] Create new structure in parallel
- [ ] Write tests for new code
- [ ] Migrate one module at a time
- [ ] Update imports
- [ ] Run full test suite
- [ ] Update documentation
- [ ] Remove old code
- [ ] Deploy and verify

---

## Conclusion

These refactoring steps will incrementally improve code quality, maintainability, and testability without requiring a complete rewrite. Start with the quick wins and gradually work toward the long-term improvements.

Each change should be:
- **Small**: One logical change per commit
- **Tested**: Add/update tests
- **Documented**: Update relevant docs
- **Reviewed**: Get feedback before merging

Remember: **Perfect is the enemy of good**. Ship incremental improvements rather than waiting for a perfect rewrite.
