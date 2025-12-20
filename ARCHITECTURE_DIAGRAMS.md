# Stellwerk Architecture Evolution

## Current Architecture (v0.1.0-rc.3)

```
┌─────────────────────────────────────────────────────┐
│                   FastAPI App                        │
│                    (app.py)                          │
│  ┌──────────────────────────────────────────────┐   │
│  │  HTTP Endpoints (591 LOC)                    │   │
│  │  - Goal CRUD                                 │   │
│  │  - Planning                                  │   │
│  │  - Work Packages                             │   │
│  │  - Debug Console                             │   │
│  └──────────────────────────────────────────────┘   │
│                         │                            │
│         ┌───────────────┼───────────────┐            │
│         ▼               ▼               ▼            │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐        │
│  │ Planner  │   │Repository│   │ Models   │        │
│  │(976 LOC) │   │(604 LOC) │   │(270 LOC) │        │
│  └────┬─────┘   └────┬─────┘   └──────────┘        │
│       │              │                               │
│       ▼              ▼                               │
│  ┌──────────┐   ┌──────────┐                        │
│  │  OpenAI  │   │    DB    │                        │
│  │   API    │   │SQLAlchemy│                        │
│  └──────────┘   └──────────┘                        │
└─────────────────────────────────────────────────────┘

Issues:
❌ Tight coupling between layers
❌ Large files mixing concerns
❌ Hard dependency on OpenAI
❌ No caching
❌ Limited validation
❌ No analytics
```

## Proposed Architecture (v2.0)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         API Layer                                    │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐     │
│  │ Goals Router │Planning      │Work Packages │Analytics     │     │
│  │              │Router        │Router        │Router        │     │
│  └──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┘     │
│         │              │              │              │              │
└─────────┼──────────────┼──────────────┼──────────────┼──────────────┘
          │              │              │              │
          ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Service Layer                                   │
│  ┌──────────────┬──────────────────────┬──────────────────────┐    │
│  │ Goal Service │ Planning Service     │ Analytics Service    │    │
│  └──────┬───────┴──────┬───────────────┴──────┬───────────────┘    │
│         │              │                       │                     │
└─────────┼──────────────┼───────────────────────┼─────────────────────┘
          │              │                       │
          ▼              ▼                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Core Domain Layer                                │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                   Business Logic                             │   │
│  │  - Goal, Route, Task, WorkPackage (Pure Domain Models)      │   │
│  │  - Validation Rules                                          │   │
│  │  - Domain Events                                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Infrastructure │  │ Planning Engine │  │  Visualization  │
├─────────────────┤  ├─────────────────┤  ├─────────────────┤
│                 │  │                 │  │                 │
│ ┌─────────────┐ │  │ ┌─────────────┐ │  │ ┌─────────────┐ │
│ │ Persistence │ │  │ │Orchestrator │ │  │ │Graph Builder│ │
│ │             │ │  │ │             │ │  │ │             │ │
│ │ SQLAlchemy  │ │  │ │ ┌─────────┐ │ │  │ │ Layout      │ │
│ │ Repository  │ │  │ │ │Validators│ │ │  │ │ Engine      │ │
│ │             │ │  │ │ └─────────┘ │ │  │ │             │ │
│ │ In-Memory   │ │  │ │             │ │  │ │ SVG/JS      │ │
│ │ (Testing)   │ │  │ │ ┌─────────┐ │ │  │ │ Renderers   │ │
│ └─────────────┘ │  │ │ │Refiners │ │ │  │ └─────────────┘ │
│                 │  │ │ └─────────┘ │ │  │                 │
│ ┌─────────────┐ │  │ │             │ │  └─────────────────┘
│ │  AI Layer   │ │  │ │ ┌─────────┐ │ │
│ │             │ │  │ │ │ Context │ │ │
│ │ OpenAI      │◄─┼──┼─┤ Manager │ │ │
│ │ Anthropic   │ │  │ │ └─────────┘ │ │
│ │ Local (LLM) │ │  │ └─────────────┘ │
│ └─────────────┘ │  │                 │
│                 │  │ ┌─────────────┐ │
│ ┌─────────────┐ │  │ │   Prompts   │ │
│ │   Cache     │ │  │ │  (Jinja2)   │ │
│ │             │ │  │ │             │ │
│ │ Redis       │◄─┼──┼─┤ Goal Decomp │ │
│ │ In-Memory   │ │  │ │ Task Gen    │ │
│ │ (Vector DB) │ │  │ │ WP Details  │ │
│ └─────────────┘ │  │ └─────────────┘ │
│                 │  └─────────────────┘
│ ┌─────────────┐ │
│ │ Monitoring  │ │
│ │             │ │
│ │ structlog   │ │
│ │ Sentry      │ │
│ │ Prometheus  │ │
│ └─────────────┘ │
└─────────────────┘

Benefits:
✅ Clear separation of concerns
✅ Testable in isolation
✅ Pluggable AI providers
✅ Semantic caching
✅ Multi-stage validation
✅ Analytics and insights
✅ Horizontal scalability
```

## Planning Pipeline Evolution

### Current (Single-Stage)

```
User Input ──► OpenAI API ──► Parse JSON ──► Save to DB
                    │
                    └─► If fails: Error to user
```

### Proposed (Multi-Stage with Validation)

```
                    ┌─────────────────────────────────────┐
User Input ────────►│  Stage 1: Goal Decomposition       │
                    │  (Structure: routes, edges, decisions)│
                    └──────────────┬──────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────────┐
                    │  Stage 2: Structure Validation      │
                    │  (DAG check, connectivity)          │
                    └──────────────┬──────────────────────┘
                                   │
                            ┌──────┴──────┐
                            │  Valid?     │
                            └──────┬──────┘
                         Yes │     │ No
                             │     └────► Refine & Retry
                             ▼
                    ┌─────────────────────────────────────┐
                    │  Stage 3: Detailed Tasks            │
                    │  (Parallel generation for routes)   │
                    └──────────────┬──────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────────┐
                    │  Stage 4: Work Packages             │
                    │  (Batched parallel generation)      │
                    └──────────────┬──────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────────┐
                    │  Stage 5: Quality Scoring           │
                    │  (Markdown structure, URL count,    │
                    │   semantic coherence)               │
                    └──────────────┬──────────────────────┘
                                   │
                            ┌──────┴──────┐
                            │  Score ≥ 0.7│
                            └──────┬──────┘
                         Yes │     │ No
                             │     └────► Refine & Improve
                             ▼
                    ┌─────────────────────────────────────┐
                    │  Stage 6: Enrichment                │
                    │  (Dependencies, estimates, risks)   │
                    └──────────────┬──────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────────┐
                    │  Cache & Save to DB                 │
                    └─────────────────────────────────────┘
```

## Data Flow Comparison

### Current

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Browser  │───►│ FastAPI  │───►│  Planner │───►│  OpenAI  │
│          │◄───│          │◄───│          │◄───│          │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                      │                │
                      ▼                ▼
                ┌──────────┐    ┌──────────┐
                │   DB     │    │  No Cache│
                │(SQLite/  │    │          │
                │Postgres) │    └──────────┘
                └──────────┘
```

### Proposed

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ React    │───►│ FastAPI  │───►│ Service  │───►│Orchestr- │
│ Frontend │◄───│   API    │◄───│  Layer   │◄───│  ator    │
└──────────┘    └──────────┘    └──────────┘    └────┬─────┘
                                                      │
                      ┌───────────────────────────────┤
                      │                               │
                      ▼                               ▼
                ┌──────────┐                    ┌──────────┐
                │ Postgres │                    │AI Provider│
                │ +pgvector│                    │ (OpenAI/ │
                │          │                    │Anthropic)│
                └──────────┘                    └──────────┘
                      ▲                               │
                      │         ┌──────────┐          │
                      │         │  Redis   │◄─────────┘
                      │         │  Cache   │
                      └─────────┤ (Semantic│
                                │ Matching)│
                                └──────────┘
                                      │
                                      ▼
                                ┌──────────┐
                                │Analytics │
                                │ Service  │
                                └──────────┘
```

## Migration Strategy

```
Phase 1: Prepare (Weeks 1-2)
┌─────────────────────────────────────────────────┐
│ 1. Set up new project structure                 │
│ 2. Create interfaces/abstracts                  │
│ 3. Set up PostgreSQL + pgvector                 │
│ 4. Set up Redis                                 │
└─────────────────────────────────────────────────┘

Phase 2: Core (Weeks 3-4)
┌─────────────────────────────────────────────────┐
│ 1. Implement repositories                       │
│ 2. Implement AI provider interface              │
│ 3. Create planning orchestrator                 │
│ 4. Add validators                               │
└─────────────────────────────────────────────────┘

Phase 3: Intelligence (Weeks 5-6)
┌─────────────────────────────────────────────────┐
│ 1. Advanced prompts                             │
│ 2. Context management                           │
│ 3. Quality scoring                              │
│ 4. Semantic caching                             │
└─────────────────────────────────────────────────┘

Phase 4: Frontend (Weeks 7-8)
┌─────────────────────────────────────────────────┐
│ 1. React setup with TypeScript                  │
│ 2. Interactive graph editor                     │
│ 3. Real-time updates                            │
│ 4. Analytics dashboard                          │
└─────────────────────────────────────────────────┘

Phase 5: Collaboration (Weeks 9-10)
┌─────────────────────────────────────────────────┐
│ 1. Authentication                               │
│ 2. Plan sharing                                 │
│ 3. Comments                                     │
│ 4. Recommendations                              │
└─────────────────────────────────────────────────┘

Phase 6: Production (Weeks 11-12)
┌─────────────────────────────────────────────────┐
│ 1. Testing (unit, integration, e2e)             │
│ 2. Performance optimization                     │
│ 3. Security audit                               │
│ 4. Deployment                                   │
└─────────────────────────────────────────────────┘
```

## Key Metrics Comparison

| Metric | Current (v0.1) | Target (v2.0) | Improvement |
|--------|----------------|---------------|-------------|
| **Lines of Code** |
| Largest File | 976 (planner.py) | <300 per file | 69% ↓ |
| Average File | ~370 LOC | ~150 LOC | 59% ↓ |
| Total Backend | ~4,000 LOC | ~6,000 LOC | 50% ↑ |
| **Architecture** |
| Layers | 1-2 | 5 | Better separation |
| Coupling | High | Low | Testability ↑ |
| **AI Quality** |
| Success Rate | ~90% | >98% | 8% ↑ |
| Avg. Time | 30-60s | <30s | 50% ↓ |
| Validation | Basic | Multi-stage | Robustness ↑ |
| **Performance** |
| API Response | 200-500ms | <200ms (cached) | 60% ↓ |
| Concurrent Users | ~10 | ~100 | 10x ↑ |
| **Testing** |
| Test Coverage | ~20% | >80% | 4x ↑ |
| Test Types | Unit | Unit+Integration+E2E | Comprehensive |
| **Features** |
| AI Providers | 1 (OpenAI) | 3+ (pluggable) | Flexibility ↑ |
| Caching | None | Semantic | Performance ↑ |
| Analytics | None | Full dashboard | Insights ↑ |
| Collaboration | None | Full support | Team work ↑ |

## Technology Evolution

### Current Stack
```
Backend:
├── FastAPI 0.115
├── SQLAlchemy 2.0
├── Pydantic 2.9
├── httpx (for OpenAI)
└── uvicorn

Frontend:
├── Jinja2 templates
├── Vanilla JavaScript
└── Inline CSS

Database:
├── SQLite (dev)
└── PostgreSQL (prod)

Deployment:
├── Docker
└── Docker Compose
```

### Proposed Stack
```
Backend:
├── FastAPI 0.115+ (same)
├── SQLAlchemy 2.0+ (same)
├── Pydantic 2.9+ (same)
├── dependency-injector (new)
├── LangChain (new)
├── openai SDK (updated)
├── anthropic SDK (new)
├── Celery (new)
├── structlog (new)
└── prometheus-client (new)

Frontend:
├── React 18 (new)
├── TypeScript 5.3+ (new)
├── Vite (new)
├── ReactFlow/Cytoscape (new)
├── TanStack Query (new)
└── Radix UI/shadcn (new)

Database:
├── PostgreSQL 16 + pgvector (upgraded)
└── Redis 7 (new)

Monitoring:
├── Grafana (new)
├── Prometheus (new)
├── Loki (new)
└── Sentry (new)

Deployment:
├── Docker (same)
├── Docker Compose (same)
└── Caddy (new, for TLS)
```

## Decision Matrix

| Aspect | Refactor v0.1 | Build v2.0 | Hybrid |
|--------|---------------|------------|--------|
| **Time to Value** | ⭐⭐⭐⭐⭐ Fast | ⭐⭐ Slow | ⭐⭐⭐⭐ Good |
| **Risk** | ⭐⭐⭐⭐⭐ Low | ⭐⭐⭐ Medium | ⭐⭐⭐⭐ Low-Medium |
| **Final Quality** | ⭐⭐⭐ Good | ⭐⭐⭐⭐⭐ Excellent | ⭐⭐⭐⭐ Very Good |
| **Learning Curve** | ⭐⭐⭐⭐⭐ Easy | ⭐⭐ Hard | ⭐⭐⭐ Medium |
| **Team Disruption** | ⭐⭐⭐⭐⭐ Minimal | ⭐⭐ High | ⭐⭐⭐ Moderate |
| **Tech Debt** | ⭐⭐ Some | ⭐⭐⭐⭐⭐ None | ⭐⭐⭐⭐ Low |
| **Scalability** | ⭐⭐⭐ Limited | ⭐⭐⭐⭐⭐ Excellent | ⭐⭐⭐⭐ Very Good |
| **Cost** | ⭐⭐⭐⭐⭐ Low | ⭐⭐ High | ⭐⭐⭐ Medium |

## Conclusion

Die Dokumentation bietet zwei klare Wege:

1. **REFACTORING_GUIDE.md**: Für schnelle, risikoarme Verbesserungen
2. **ENHANCED_PROJECT_PROMPT.md**: Für langfristige, umfassende Modernisierung

**Empfehlung**: Hybrid-Ansatz für beste Balance zwischen sofortigem Nutzen und langfristiger Qualität.

---

**Version**: 1.0  
**Erstellt**: 2024-12-20  
**Format**: ASCII-Art Diagramme für universelle Lesbarkeit
