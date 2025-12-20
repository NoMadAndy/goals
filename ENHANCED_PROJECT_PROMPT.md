# Enhanced Project Prompt: Stellwerk 2.0

## Project Vision

Create a next-generation AI-powered goal planning and tracking system that builds upon the Stellwerk MVP with significantly improved organization, modularity, and intelligent AI logic. The system should help users break down complex goals into actionable work packages visualized as an interactive graph.

---

## Executive Summary of Current System (Stellwerk v0.1.0-rc.3)

### What Stellwerk Currently Does
Stellwerk is a web-based goal planning system that:
- Accepts user-defined goals and uses OpenAI to generate detailed execution plans
- Breaks goals into Routes → Tasks → Work Packages
- Visualizes progress as a railway line graph with switches (decisions/branches)
- Supports branching plans with up to 10 levels of decision points and merges (DAG structure)
- Tracks work package completion and difficulty (length + grade)
- Manages people involved (companions, helpers)
- Persists data in SQLite (dev) or PostgreSQL (prod)

### Current Architecture (4,000+ LOC)
```
src/stellwerk/
├── app.py (591 lines)          # FastAPI endpoints, HTML rendering
├── planner.py (976 lines)      # OpenAI integration, plan parsing
├── repository.py (604 lines)   # Database CRUD operations
├── models.py (270 lines)       # Pydantic models (Goal, Route, Task, WorkPackage)
├── db.py (352 lines)           # SQLAlchemy ORM schemas
├── notes.py (317 lines)        # Markdown parsing for work package details
├── settings.py (45 lines)      # Environment configuration
├── debug.py (102 lines)        # Debug event bus for SSE console
└── cli.py (112 lines)          # CLI entry point
```

### Current Strengths
1. **Flexible graph structure**: Supports complex DAGs with decisions and merges
2. **Rich work packages**: Each package includes detailed markdown (steps, DoD, risks, resources, images)
3. **Real-time feedback**: SSE-based progress updates during AI planning
4. **Debug console**: Live request/response tracing
5. **Docker deployment**: Preprod/prod ready with auto-deploy scripts
6. **Test coverage**: 850+ lines of tests (pytest)

### Current Limitations
1. **Monolithic structure**: Large files mixing concerns (app.py is 591 lines)
2. **Tight coupling**: Repository, business logic, and API layers intertwined
3. **Single AI provider**: Hard dependency on OpenAI-compatible endpoints
4. **Limited validation**: AI responses sometimes fail schema validation
5. **No retry strategy**: Planning failures require manual restart
6. **Static prompts**: No prompt engineering or optimization
7. **No caching**: Every plan is generated from scratch
8. **Limited analytics**: No tracking of user patterns or plan quality

---

## Enhanced Project Goals

### Core Objectives
1. **Better Organization**: Modular, layered architecture with clear separation of concerns
2. **Intelligent AI Logic**: Advanced prompt engineering, multi-step reasoning, validation
3. **Extensibility**: Plugin architecture for AI providers, validators, renderers
4. **Robustness**: Comprehensive error handling, retries, fallbacks
5. **Analytics**: Track plan quality, user satisfaction, completion rates
6. **User Experience**: Interactive graph editing, plan refinement, collaborative features

---

## Proposed Architecture

### 1. Layered Architecture

```
stellwerk2/
├── core/                       # Domain logic (no dependencies on FastAPI/DB)
│   ├── models.py              # Pure domain models
│   ├── services.py            # Business logic
│   └── interfaces.py          # Ports (repository, AI, etc.)
├── infrastructure/
│   ├── persistence/           # Repository implementations
│   │   ├── sqlalchemy_repo.py
│   │   └── in_memory_repo.py
│   ├── ai/                    # AI provider implementations
│   │   ├── base.py            # Abstract AI provider
│   │   ├── openai_provider.py
│   │   ├── anthropic_provider.py
│   │   └── local_provider.py  # Ollama, etc.
│   ├── cache/                 # Caching layer
│   │   ├── redis_cache.py
│   │   └── in_memory_cache.py
│   └── monitoring/            # Observability
│       ├── logger.py
│       └── metrics.py
├── api/                       # HTTP layer
│   ├── routes/                # Endpoint definitions
│   │   ├── goals.py
│   │   ├── planning.py
│   │   └── analytics.py
│   ├── middleware/            # Request processing
│   └── dependencies.py        # Dependency injection
├── planning/                  # AI planning engine
│   ├── orchestrator.py        # Multi-step planning workflow
│   ├── prompts/               # Structured prompt library
│   │   ├── goal_decomposition.py
│   │   ├── task_generation.py
│   │   └── work_package_detail.py
│   ├── validators/            # Output validation
│   │   ├── schema_validator.py
│   │   ├── semantic_validator.py
│   │   └── quality_scorer.py
│   ├── refiners/              # Plan improvement
│   │   ├── granularity_refiner.py
│   │   └── dependency_analyzer.py
│   └── context/               # Context management
│       ├── user_history.py
│       └── domain_knowledge.py
├── visualization/             # Graph rendering
│   ├── graph_builder.py       # Convert plan to graph
│   ├── layout_engine.py       # Auto-layout algorithms
│   └── renderers/
│       ├── svg_renderer.py
│       └── interactive_js.py
├── analytics/                 # Metrics and insights
│   ├── plan_quality.py        # Track plan success rates
│   ├── user_patterns.py       # Learn from user behavior
│   └── recommendations.py     # Suggest improvements
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

### 2. Key Design Patterns

#### Dependency Injection
```python
# Use dependency injector or similar
from dependency_injector import containers, providers

class Container(containers.DeclarativeContainer):
    config = providers.Configuration()
    
    # Infrastructure
    db = providers.Singleton(Database, config.database_url)
    cache = providers.Singleton(RedisCache, config.redis_url)
    ai_provider = providers.Factory(
        OpenAIProvider,
        api_key=config.openai_api_key,
        model=config.openai_model
    )
    
    # Repositories
    goal_repository = providers.Factory(
        GoalRepository,
        db=db
    )
    
    # Services
    planning_service = providers.Factory(
        PlanningService,
        ai_provider=ai_provider,
        repository=goal_repository,
        cache=cache
    )
```

#### Strategy Pattern for AI Providers
```python
from abc import ABC, abstractmethod

class AIProvider(ABC):
    @abstractmethod
    async def generate_plan(
        self,
        goal: str,
        context: PlanningContext
    ) -> PlanResult:
        pass
    
    @abstractmethod
    async def refine_plan(
        self,
        plan: Plan,
        feedback: str
    ) -> Plan:
        pass

class OpenAIProvider(AIProvider):
    # Implementation with o1-preview for complex reasoning
    pass

class AnthropicProvider(AIProvider):
    # Implementation with Claude 3.5 Sonnet
    pass
```

#### Repository Pattern
```python
class GoalRepository(ABC):
    @abstractmethod
    async def create(self, goal: Goal) -> UUID:
        pass
    
    @abstractmethod
    async def get(self, goal_id: UUID) -> Goal | None:
        pass
    
    @abstractmethod
    async def update(self, goal: Goal) -> None:
        pass
```

---

## Enhanced AI Logic

### 1. Multi-Stage Planning Pipeline

```python
class PlanningOrchestrator:
    """Coordinates multi-step AI planning with validation and refinement."""
    
    async def create_plan(
        self,
        goal: str,
        context: PlanningContext
    ) -> Plan:
        # Stage 1: Goal decomposition (high-level structure)
        structure = await self._decompose_goal(goal, context)
        
        # Stage 2: Validate structure
        validation = await self._validate_structure(structure)
        if not validation.is_valid:
            structure = await self._refine_structure(structure, validation)
        
        # Stage 3: Generate detailed tasks (parallel)
        routes = await asyncio.gather(*[
            self._generate_route_details(route, context)
            for route in structure.routes
        ])
        
        # Stage 4: Generate work packages (parallel with batching)
        plan = await self._generate_work_packages(routes, context)
        
        # Stage 5: Quality scoring and optional refinement
        quality = await self._score_plan_quality(plan)
        if quality.score < 0.7:
            plan = await self._refine_plan(plan, quality.feedback)
        
        # Stage 6: Add metadata (dependencies, estimates, risks)
        plan = await self._enrich_plan(plan)
        
        return plan
```

### 2. Advanced Prompt Engineering

#### Structured Prompts with Few-Shot Examples
```python
GOAL_DECOMPOSITION_PROMPT = """
You are an expert project planner. Decompose the user's goal into a directed acyclic graph (DAG) with:
- 6-20 nodes (routes)
- Clear decision points with merge possibilities
- Realistic branching (up to 10 levels)

# Examples of Good Decomposition

## Example 1: "Launch a SaaS product"
```json
{
  "routes": [
    {"id": "r0", "title": "Market Research", "kind": "trunk", ...},
    {"id": "r1", "title": "MVP Development", "kind": "trunk", ...},
    {"id": "r2", "title": "Beta Testing", "kind": "trunk", ...},
    // Decision point: Go-to-market strategy
    {"id": "r3", "title": "B2B Sales-Led", "kind": "branch", ...},
    {"id": "r4", "title": "B2C Product-Led", "kind": "branch", ...},
    // Both merge into:
    {"id": "r5", "title": "Scale Operations", "kind": "trunk", ...}
  ],
  "edges": [
    {"from": "r0", "to": "r1"},
    {"from": "r1", "to": "r2"},
    {"from": "r2", "to": "r3"}, // decision option 1
    {"from": "r2", "to": "r4"}, // decision option 2
    {"from": "r3", "to": "r5"}, // merge
    {"from": "r4", "to": "r5"}  // merge
  ],
  "decisions": [...]
}
```

# User's Goal
{goal}

# Additional Context
{context}

# Constraints
- Favor realistic, actionable steps over abstract milestones
- Each route should represent 2-4 weeks of focused work
- Decision points should reflect genuine trade-offs, not trivial choices
- Merges are encouraged when alternative approaches converge

Generate the plan structure as JSON following the schema above.
"""

WORK_PACKAGE_DETAIL_PROMPT = """
You are a technical writer creating actionable work package documentation.

# Work Package Title
{title}

# Task Context
{task_title} within {route_title}

# Goal
{goal_description}

Generate comprehensive Markdown documentation with these EXACT sections:

## Kurzfassung
[2-5 concrete sentences explaining what and why]

## Schritte
[Minimum 6 numbered, actionable steps. Use format: 1., 2., 3., ...]

## Definition of Done
[Minimum 7 checkboxes. Use format: - [ ] ...]

## Risiken
[Minimum 3 bullet points with mitigation strategies]

## Quellen
[3-8 real URLs to documentation, tutorials, or tools]

## Bilder
[1-3 relevant image URLs: diagrams, screenshots, reference examples]

# Quality Standards
- Steps must be specific (include tool names, commands, file paths)
- DoD criteria must be measurable and verifiable
- Risks must be realistic, not generic ("scope creep" is overused)
- URLs must be real, working links (no placeholders)
- Images should illustrate concepts, not be decorative

Generate the Markdown now:
"""
```

### 3. Validation and Quality Scoring

```python
class PlanValidator:
    """Multi-layered validation for AI-generated plans."""
    
    async def validate(self, plan: Plan) -> ValidationResult:
        checks = await asyncio.gather(
            self._check_schema(plan),
            self._check_dag_validity(plan),
            self._check_semantic_coherence(plan),
            self._check_work_package_quality(plan),
            self._check_resource_estimates(plan)
        )
        
        return ValidationResult.aggregate(checks)
    
    async def _check_dag_validity(self, plan: Plan) -> CheckResult:
        """Ensure graph is a valid DAG with no cycles."""
        # Topological sort to detect cycles
        # Check for unreachable nodes
        # Verify decision consistency
        pass
    
    async def _check_semantic_coherence(self, plan: Plan) -> CheckResult:
        """Use AI to check if plan makes logical sense."""
        # Ask AI: "Does this plan make sense for the goal?"
        # Check for contradictions
        # Verify route titles match their contents
        pass
    
    async def _check_work_package_quality(self, plan: Plan) -> CheckResult:
        """Validate work package markdown structure."""
        issues = []
        for route in plan.routes:
            for task in route.tasks:
                for wp in task.work_packages:
                    if not has_required_sections(wp.notes):
                        issues.append(f"Missing sections: {wp.title}")
                    if count_urls(wp.notes) < 3:
                        issues.append(f"Insufficient sources: {wp.title}")
        
        return CheckResult(is_valid=len(issues) == 0, issues=issues)
```

### 4. Context Management

```python
class PlanningContext:
    """Aggregates relevant context for AI planning."""
    
    user_history: list[Goal]              # Past goals by this user
    domain_knowledge: dict[str, Any]      # Relevant best practices
    organizational_standards: dict        # Company-specific guidelines
    similar_successful_plans: list[Plan]  # Reference examples
    
    def to_prompt_context(self) -> str:
        """Format context for inclusion in AI prompts."""
        sections = []
        
        if self.user_history:
            sections.append("# User's Past Goals")
            sections.append(self._summarize_history())
        
        if self.similar_successful_plans:
            sections.append("# Similar Successful Plans")
            sections.append(self._format_reference_plans())
        
        if self.domain_knowledge:
            sections.append("# Domain Knowledge")
            sections.append(self._format_domain_knowledge())
        
        return "\n\n".join(sections)
```

### 5. Intelligent Caching

```python
class PlanCache:
    """Cache AI responses with semantic similarity matching."""
    
    async def get_similar_plan(
        self,
        goal: str,
        threshold: float = 0.85
    ) -> Plan | None:
        """Find cached plan for semantically similar goal."""
        # Use embeddings to find similar goals
        embedding = await self.embedding_service.embed(goal)
        
        similar = await self.vector_db.similarity_search(
            embedding,
            k=5,
            threshold=threshold
        )
        
        if similar:
            # Return most recent similar plan
            return await self.repository.get_plan(similar[0].plan_id)
        
        return None
    
    async def cache_plan(self, goal: str, plan: Plan) -> None:
        """Cache plan with embedding for future retrieval."""
        embedding = await self.embedding_service.embed(goal)
        await self.vector_db.insert(
            embedding=embedding,
            plan_id=plan.id,
            goal=goal,
            created_at=datetime.now(timezone.utc)
        )
```

---

## Enhanced User Experience

### 1. Interactive Graph Editing

```javascript
// React-based interactive graph editor
const PlanGraph = ({ plan, onUpdate }) => {
  const [nodes, edges] = useMemo(() => planToGraph(plan), [plan]);
  
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={handleNodeChange}
      onEdgesChange={handleEdgeChange}
      onConnect={handleConnect}
      nodeTypes={customNodeTypes}
    >
      <Controls />
      <MiniMap />
      <Background />
      <Panel position="top-right">
        <PlanQualityScore score={plan.quality_score} />
      </Panel>
    </ReactFlow>
  );
};
```

### 2. Collaborative Features

```python
class CollaborationService:
    """Enable team collaboration on plans."""
    
    async def share_plan(
        self,
        plan_id: UUID,
        user_ids: list[UUID],
        permission: Permission
    ) -> None:
        """Share plan with other users."""
        pass
    
    async def add_comment(
        self,
        plan_id: UUID,
        work_package_id: UUID,
        user_id: UUID,
        comment: str
    ) -> Comment:
        """Add comment to work package."""
        pass
    
    async def suggest_refinement(
        self,
        plan_id: UUID,
        suggestion: str
    ) -> Plan:
        """Let AI refine plan based on team feedback."""
        pass
```

### 3. Progress Analytics

```python
class AnalyticsService:
    """Track and analyze plan execution."""
    
    async def get_completion_insights(
        self,
        goal_id: UUID
    ) -> CompletionInsights:
        """Analyze completion patterns."""
        plan = await self.repository.get_goal(goal_id)
        
        return CompletionInsights(
            overall_progress=self._calculate_progress(plan),
            velocity=self._calculate_velocity(plan),
            bottlenecks=self._identify_bottlenecks(plan),
            estimated_completion=self._estimate_completion(plan),
            recommendations=await self._generate_recommendations(plan)
        )
    
    async def _generate_recommendations(self, plan: Plan) -> list[str]:
        """Use AI to suggest optimizations."""
        # Analyze blocked work packages
        # Identify underutilized resources
        # Suggest re-prioritization
        pass
```

---

## Technical Specifications

### 1. Tech Stack

#### Backend
- **Framework**: FastAPI 0.115+ (existing)
- **Dependency Injection**: dependency-injector
- **ORM**: SQLAlchemy 2.0+ (existing)
- **Validation**: Pydantic v2 (existing)
- **AI Clients**: 
  - OpenAI SDK (existing)
  - Anthropic SDK
  - LangChain for advanced orchestration
- **Caching**: Redis with redis-py
- **Task Queue**: Celery + Redis (for async planning)
- **Monitoring**: structlog + Sentry
- **Testing**: pytest, pytest-asyncio, faker

#### Frontend
- **Framework**: React 18 with TypeScript
- **Graph Visualization**: ReactFlow or Cytoscape.js
- **State Management**: Zustand or Jotai
- **API Client**: TanStack Query (React Query)
- **UI Components**: shadcn/ui or Radix UI
- **Build**: Vite

#### Infrastructure
- **Container**: Docker + Docker Compose (existing)
- **Database**: PostgreSQL 16 (existing) + pgvector for embeddings
- **Cache**: Redis 7
- **Reverse Proxy**: Caddy (for TLS)
- **Observability**: Grafana + Prometheus + Loki

### 2. Database Schema Enhancements

```sql
-- Add vector embeddings for semantic search
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE goal_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    goal_id UUID NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
    embedding vector(1536),  -- OpenAI text-embedding-3-small
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_goal_embeddings_vector ON goal_embeddings
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Track plan quality metrics
CREATE TABLE plan_quality_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    goal_id UUID NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
    quality_score DECIMAL(3,2),  -- 0.00-1.00
    validation_errors JSONB,
    ai_confidence DECIMAL(3,2),
    user_rating INT CHECK (user_rating BETWEEN 1 AND 5),
    completion_rate DECIMAL(5,2),  -- percentage
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Track user feedback for continuous improvement
CREATE TABLE work_package_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_package_id UUID NOT NULL REFERENCES work_packages(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    feedback_type VARCHAR(50) NOT NULL,  -- 'helpful', 'unclear', 'too_detailed', etc.
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Collaboration features
CREATE TABLE plan_collaborators (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    goal_id UUID NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    permission VARCHAR(20) NOT NULL,  -- 'view', 'edit', 'admin'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(goal_id, user_id)
);

CREATE TABLE work_package_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_package_id UUID NOT NULL REFERENCES work_packages(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    comment TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 3. Configuration Management

```toml
# stellwerk2.toml
[server]
host = "127.0.0.1"
port = 8002
reload = false
workers = 4

[database]
url = "postgresql://user:pass@localhost:5432/stellwerk"
pool_size = 10
max_overflow = 20

[redis]
url = "redis://localhost:6379/0"
cache_ttl_seconds = 3600

[ai]
default_provider = "openai"

[ai.openai]
api_key = "${OPENAI_API_KEY}"
model = "gpt-4o-mini"
reasoning_model = "o1-preview"
timeout_seconds = 90
max_retries = 3

[ai.anthropic]
api_key = "${ANTHROPIC_API_KEY}"
model = "claude-3-5-sonnet-20241022"

[planning]
max_routes = 20
max_tasks_per_route = 6
max_work_packages_per_task = 6
quality_threshold = 0.7
enable_semantic_caching = true
cache_similarity_threshold = 0.85

[monitoring]
enable_debug_console = true
sentry_dsn = "${SENTRY_DSN}"
log_level = "INFO"
```

---

## Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
- [ ] Set up project structure with new architecture
- [ ] Implement dependency injection container
- [ ] Create abstract interfaces (repository, AI provider, cache)
- [ ] Set up PostgreSQL with pgvector
- [ ] Set up Redis
- [ ] Migrate existing tests to new structure

### Phase 2: Core Services (Weeks 3-4)
- [ ] Implement planning orchestrator with multi-stage pipeline
- [ ] Create structured prompt library
- [ ] Implement validators (schema, DAG, semantic, quality)
- [ ] Add OpenAI provider with o1-preview support
- [ ] Implement caching layer with embeddings
- [ ] Add comprehensive error handling

### Phase 3: Enhanced AI Logic (Weeks 5-6)
- [ ] Implement context aggregation
- [ ] Add few-shot learning examples
- [ ] Create plan refinement loop
- [ ] Implement quality scoring
- [ ] Add semantic similarity search
- [ ] Build plan enrichment (dependencies, estimates)

### Phase 4: API & Frontend (Weeks 7-8)
- [ ] Refactor FastAPI routes with new architecture
- [ ] Build React frontend with TypeScript
- [ ] Implement interactive graph editor
- [ ] Add real-time updates (WebSocket/SSE)
- [ ] Create analytics dashboard
- [ ] Add user feedback mechanisms

### Phase 5: Collaboration & Analytics (Weeks 9-10)
- [ ] Implement user authentication
- [ ] Add plan sharing
- [ ] Build commenting system
- [ ] Create progress analytics
- [ ] Add recommendation engine
- [ ] Implement export/import (JSON, Markdown)

### Phase 6: Testing & Deployment (Weeks 11-12)
- [ ] Comprehensive unit tests (>80% coverage)
- [ ] Integration tests for all services
- [ ] E2E tests for critical workflows
- [ ] Performance testing and optimization
- [ ] Security audit
- [ ] Production deployment
- [ ] Documentation and user guides

---

## Testing Strategy

### Unit Tests
```python
# tests/unit/planning/test_orchestrator.py
import pytest
from stellwerk2.planning.orchestrator import PlanningOrchestrator

@pytest.fixture
def orchestrator(mock_ai_provider, mock_validator, mock_cache):
    return PlanningOrchestrator(
        ai_provider=mock_ai_provider,
        validator=mock_validator,
        cache=mock_cache
    )

@pytest.mark.asyncio
async def test_create_plan_with_validation_failure(orchestrator):
    """Test plan creation retries when validation fails."""
    orchestrator.validator.validate = AsyncMock(
        side_effect=[
            ValidationResult(is_valid=False, issues=["Missing routes"]),
            ValidationResult(is_valid=True, issues=[])
        ]
    )
    
    plan = await orchestrator.create_plan(
        goal="Launch a product",
        context=PlanningContext()
    )
    
    assert plan is not None
    assert orchestrator.validator.validate.call_count == 2
```

### Integration Tests
```python
# tests/integration/test_planning_pipeline.py
@pytest.mark.integration
async def test_end_to_end_planning_pipeline(container):
    """Test complete planning flow from goal to validated plan."""
    service = container.planning_service()
    
    plan = await service.create_plan(
        goal="Build a mobile app",
        user_id=UUID("test-user")
    )
    
    assert plan.routes
    assert all(route.tasks for route in plan.routes)
    assert plan.quality_score >= 0.7
```

### E2E Tests
```python
# tests/e2e/test_user_journey.py
@pytest.mark.e2e
async def test_user_creates_and_completes_goal(playwright_page):
    """Test complete user journey from goal creation to completion."""
    # User creates goal
    await playwright_page.goto("http://localhost:8002")
    await playwright_page.fill("#goal-input", "Learn Python")
    await playwright_page.click("#create-plan-btn")
    
    # Wait for AI planning
    await playwright_page.wait_for_selector(".plan-graph", timeout=60000)
    
    # Verify plan structure
    routes = await playwright_page.query_selector_all(".graph-node")
    assert len(routes) >= 6
    
    # User completes first work package
    first_wp = routes[0]
    await first_wp.click()
    await playwright_page.click("#toggle-complete-btn")
    
    # Verify progress update
    progress = await playwright_page.text_content(".progress-bar")
    assert "%" in progress
```

---

## Migration Strategy

### From Stellwerk v0.1 to v2.0

1. **Data Migration**
   ```python
   # scripts/migrate_v1_to_v2.py
   async def migrate_goals():
       """Migrate existing goals to new schema."""
       v1_goals = await old_repo.list_goals()
       
       for v1_goal in v1_goals:
           v2_goal = convert_goal_v1_to_v2(v1_goal)
           await new_repo.create(v2_goal)
           
           # Generate embeddings for existing goals
           embedding = await embedding_service.embed(v2_goal.title)
           await embedding_repo.create(v2_goal.id, embedding)
   ```

2. **Gradual Rollout**
   - Run v1 and v2 side-by-side
   - Redirect new users to v2
   - Allow v1 users to migrate at their pace
   - Sunset v1 after 3 months

3. **API Compatibility**
   - Maintain v1 API endpoints with deprecation warnings
   - Provide v2 endpoints under `/v2/` prefix
   - Document migration guide

---

## Security Considerations

### 1. API Key Management
```python
# Never log or cache API keys
class SecureAIProvider(AIProvider):
    def __init__(self, api_key: str):
        self._api_key = api_key  # Store securely
        self._client = OpenAI(api_key=api_key)
    
    def __repr__(self):
        return f"SecureAIProvider(api_key=***)"
```

### 2. User Input Sanitization
```python
class InputSanitizer:
    """Sanitize user input before AI processing."""
    
    @staticmethod
    def sanitize_goal(goal: str) -> str:
        """Remove potential prompt injection attempts."""
        # Remove system-level instructions
        # Limit length
        # Escape special tokens
        return goal[:1000].strip()
```

### 3. Rate Limiting
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/v2/plans")
@limiter.limit("10/hour")  # Prevent AI abuse
async def create_plan(request: Request, goal: str):
    pass
```

---

## Performance Optimizations

### 1. Parallel AI Calls
```python
async def generate_work_packages_parallel(
    tasks: list[Task],
    batch_size: int = 5
) -> list[Task]:
    """Generate work packages in parallel batches."""
    results = []
    
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i+batch_size]
        batch_results = await asyncio.gather(*[
            ai_provider.generate_work_packages(task)
            for task in batch
        ])
        results.extend(batch_results)
    
    return results
```

### 2. Database Query Optimization
```python
# Use eager loading to prevent N+1 queries
def get_goal_with_relations(session: Session, goal_id: UUID) -> Goal:
    return session.query(GoalRow)\
        .options(
            selectinload(GoalRow.routes)
                .selectinload(RouteRow.tasks)
                    .selectinload(TaskRow.work_packages)
        )\
        .filter(GoalRow.id == str(goal_id))\
        .one_or_none()
```

### 3. Response Streaming
```python
@app.post("/api/v2/plans/stream")
async def create_plan_stream(goal: str):
    """Stream plan creation progress."""
    async def event_generator():
        async for event in planning_service.create_plan_with_progress(goal):
            yield f"data: {json.dumps(event.dict())}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

## Monitoring and Observability

### 1. Structured Logging
```python
import structlog

logger = structlog.get_logger()

async def create_plan(goal: str) -> Plan:
    logger.info(
        "planning.started",
        goal_length=len(goal),
        user_id=str(current_user.id)
    )
    
    try:
        plan = await orchestrator.create_plan(goal)
        
        logger.info(
            "planning.completed",
            plan_id=str(plan.id),
            routes=len(plan.routes),
            quality_score=plan.quality_score,
            duration_ms=elapsed_ms
        )
        
        return plan
    except Exception as e:
        logger.error(
            "planning.failed",
            error=str(e),
            error_type=type(e).__name__
        )
        raise
```

### 2. Metrics
```python
from prometheus_client import Counter, Histogram

plans_created = Counter(
    'stellwerk_plans_created_total',
    'Total number of plans created',
    ['status', 'ai_provider']
)

plan_creation_duration = Histogram(
    'stellwerk_plan_creation_duration_seconds',
    'Time spent creating plans',
    ['ai_provider']
)

@plan_creation_duration.time()
async def create_plan(goal: str) -> Plan:
    try:
        plan = await orchestrator.create_plan(goal)
        plans_created.labels(status='success', ai_provider='openai').inc()
        return plan
    except Exception:
        plans_created.labels(status='error', ai_provider='openai').inc()
        raise
```

---

## Documentation Requirements

### 1. API Documentation
- OpenAPI/Swagger with detailed examples
- Postman collection for all endpoints
- GraphQL schema (if GraphQL is added)

### 2. User Guides
- Getting started tutorial
- Video walkthrough
- Best practices for goal setting
- FAQ

### 3. Developer Documentation
- Architecture diagrams (C4 model)
- Database schema documentation
- AI prompt engineering guide
- Contributing guidelines

### 4. Operations Runbook
- Deployment procedures
- Monitoring dashboards
- Troubleshooting guide
- Disaster recovery

---

## Success Metrics

### Technical Metrics
- Plan creation success rate: >95%
- Average plan creation time: <30 seconds
- API response time (p95): <500ms
- Test coverage: >80%
- Zero critical security vulnerabilities

### Product Metrics
- Plan completion rate: >60%
- User satisfaction (NPS): >40
- Weekly active users: +50% vs v1
- Average work packages per goal: 15-30
- Plan refinement rate: <20% (indicating good initial quality)

### AI Quality Metrics
- Schema validation pass rate: >98%
- Semantic validation pass rate: >90%
- User-reported quality score: >4/5
- AI confidence score: >0.7

---

## Risk Mitigation

### Technical Risks
1. **AI provider outages**: Implement multi-provider failover
2. **Schema validation failures**: Add robust retry logic with prompt refinement
3. **Database scalability**: Plan for sharding and read replicas
4. **Cache invalidation**: Use TTL + event-driven invalidation

### Product Risks
1. **User adoption**: Gradual rollout with extensive beta testing
2. **Plan quality**: Continuous feedback loop and prompt tuning
3. **Feature complexity**: Start with MVP, iterate based on usage data

---

## Conclusion

This enhanced project builds upon Stellwerk's solid foundation to create a production-grade, AI-powered goal planning system. The key improvements are:

1. **Modularity**: Clean architecture with clear separation of concerns
2. **Intelligence**: Multi-stage AI pipeline with validation and refinement
3. **Extensibility**: Plugin architecture for AI providers and renderers
4. **Robustness**: Comprehensive error handling, retries, and monitoring
5. **Collaboration**: Team features for shared planning
6. **Analytics**: Data-driven insights for better planning

The proposed architecture supports rapid iteration, easy testing, and future enhancements while maintaining backward compatibility with the existing system.

---

## Next Steps

1. **Review this document** with stakeholders
2. **Prioritize features** for MVP vs future phases
3. **Set up development environment** with new structure
4. **Create detailed technical specs** for Phase 1
5. **Begin implementation** following the roadmap

---

## Appendix: Key Technologies & Libraries

### Backend
- `fastapi[all]>=0.115.0`
- `sqlalchemy>=2.0.0`
- `pydantic>=2.9.0`
- `dependency-injector>=4.41.0`
- `langchain>=0.1.0`
- `openai>=1.10.0`
- `anthropic>=0.18.0`
- `redis>=5.0.0`
- `celery>=5.3.0`
- `structlog>=24.1.0`
- `prometheus-client>=0.19.0`
- `sentry-sdk>=1.40.0`
- `pgvector>=0.2.0`
- `pytest>=8.0.0`
- `pytest-asyncio>=0.23.0`
- `faker>=22.0.0`

### Frontend
- `react>=18.2.0`
- `typescript>=5.3.0`
- `vite>=5.0.0`
- `@tanstack/react-query>=5.17.0`
- `zustand>=4.5.0`
- `reactflow>=11.10.0` or `cytoscape>=3.28.0`
- `@radix-ui/react-*` or `shadcn/ui`
- `axios>=1.6.0`
- `zod>=3.22.0`

### Infrastructure
- PostgreSQL 16 with pgvector extension
- Redis 7
- Docker & Docker Compose
- Caddy (reverse proxy)
- Grafana + Prometheus + Loki (monitoring)

---

**Document Version**: 1.0  
**Last Updated**: 2024-12-20  
**Author**: GitHub Copilot (AI Assistant)  
**Status**: Draft for Review
