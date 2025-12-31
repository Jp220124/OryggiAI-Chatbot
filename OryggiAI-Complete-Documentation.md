---
title: OryggiAI Database Assistant - Complete Documentation
created: 2024-12-09
tags: [oryggi, chatbot, ai, database, documentation, architecture]
status: production
version: 1.0.0
---

# 🤖 OryggiAI Database Assistant

> **Intelligent Natural Language Database Interface**
> Transform how you interact with your database - Ask questions in plain English, get instant answers.

---

## 📋 Table of Contents

1. [Overview](#-overview)
2. [Key Features](#-key-features)
3. [System Architecture](#-system-architecture)
4. [Core Components](#-core-components)
5. [Data Flow](#-data-flow)
6. [Database Architecture](#-database-architecture)
7. [API Reference](#-api-reference)
8. [Security & RBAC](#-security--rbac)
9. [Project Structure](#-project-structure)
10. [Technology Stack](#-technology-stack)

---

## 🎯 Overview

OryggiAI Database Assistant is an **AI-powered natural language interface** that enables users to query databases without writing SQL. Built as a multi-tenant SaaS platform, it combines:

- **Large Language Models (LLMs)** for understanding natural language
- **RAG (Retrieval-Augmented Generation)** for accurate SQL generation
- **Role-Based Access Control** for secure data access
- **Multi-Tool Orchestration** for complex workflows

### What It Does

| Capability | Description |
|------------|-------------|
| 🗣️ Natural Language Queries | Ask questions in plain English |
| 🔍 Intelligent SQL Generation | Auto-converts questions to optimized SQL |
| 📊 Report Generation | Create PDF/Excel reports on demand |
| 📧 Email Delivery | Send reports directly via email |
| 🔐 Role-Based Access | Users only see authorized data |
| 🏢 Multi-Tenant | Supports multiple organizations |

---

## ✨ Key Features

### 1. Natural Language Processing
```
User: "How many employees were hired last month?"
System: SELECT COUNT(*) FROM Employees WHERE HireDate >= DATEADD(month, -1, GETDATE())
Result: 47 employees
```

### 2. RAG-Enhanced SQL Generation
- Retrieves relevant schema context before generating SQL
- Uses few-shot examples for accurate query patterns
- Understands table relationships and business logic

### 3. Multi-Tool Orchestration
```
User: "Email me a PDF report of active employees in IT department"
```
**System executes:**
1. ✅ Query database for IT employees
2. ✅ Generate PDF report
3. ✅ Send via email

### 4. Enterprise Security
- JWT-based authentication
- Role hierarchy (Admin → Manager → Staff → Viewer)
- Automatic data scoping based on user role
- Complete audit logging

---

## 🏗️ System Architecture

### High-Level Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        UI[Web UI<br/>HTML/CSS/JS]
        API_Client[API Clients]
    end

    subgraph "API Gateway"
        FastAPI[FastAPI Server<br/>Port 9000]
        Auth[JWT Auth<br/>Middleware]
        RBAC[RBAC<br/>Middleware]
    end

    subgraph "Orchestration Layer"
        Orchestrator[Chatbot Orchestrator<br/>LangGraph State Machine]
        Intent[Intent<br/>Classifier]
    end

    subgraph "Tool Layer"
        QueryTool[Query Database<br/>Tool]
        ReportTool[Generate Report<br/>Tool]
        EmailTool[Send Email<br/>Tool]
        AccessTool[Access Control<br/>Tool]
    end

    subgraph "AI/ML Layer"
        SQLAgent[RAG SQL Agent]
        LLM[LLM Provider<br/>Gemini/OpenRouter]
        Embeddings[Embedding<br/>Model]
    end

    subgraph "Data Layer"
        ChromaDB[(ChromaDB<br/>Vector Store)]
        FAISS[(FAISS<br/>Few-Shot Index)]
        SQLServer[(SQL Server<br/>Tenant Data)]
        PostgreSQL[(PostgreSQL<br/>Conversations)]
        PlatformDB[(Platform DB<br/>Multi-Tenant)]
    end

    UI --> FastAPI
    API_Client --> FastAPI
    FastAPI --> Auth
    Auth --> RBAC
    RBAC --> Orchestrator

    Orchestrator --> Intent
    Orchestrator --> QueryTool
    Orchestrator --> ReportTool
    Orchestrator --> EmailTool
    Orchestrator --> AccessTool

    QueryTool --> SQLAgent
    SQLAgent --> LLM
    SQLAgent --> ChromaDB
    SQLAgent --> FAISS
    SQLAgent --> SQLServer

    ReportTool --> SQLServer
    EmailTool -.-> External[External<br/>Email Service]

    Embeddings --> ChromaDB

    FastAPI --> PostgreSQL
    FastAPI --> PlatformDB

    style FastAPI fill:#e1f5fe
    style Orchestrator fill:#fff3e0
    style SQLAgent fill:#e8f5e9
    style ChromaDB fill:#fce4ec
    style SQLServer fill:#f3e5f5
```

### Deployment Architecture

```mermaid
graph LR
    subgraph "Cloud/VM"
        subgraph "Docker Compose"
            App[FastAPI App<br/>Port 9000]
            Chroma[ChromaDB<br/>Port 8000]
            PG[PostgreSQL<br/>Port 5432]
        end
    end

    subgraph "External Services"
        Gemini[Google Gemini API]
        OpenRouter[OpenRouter API]
        SendGrid[SendGrid Email]
    end

    subgraph "On-Premises"
        Gateway[Gateway Agent]
        TenantDB[(Tenant SQL Server)]
    end

    App --> Gemini
    App --> OpenRouter
    App --> SendGrid
    App <--> Gateway
    Gateway --> TenantDB

    style App fill:#bbdefb
    style Gateway fill:#c8e6c9
```

---

## 🔧 Core Components

### 1. SQL Agent with RAG

**File:** `app/agents/sql_agent.py`

The SQL Agent is the brain of query generation. It uses RAG (Retrieval-Augmented Generation) to create accurate SQL queries.

```mermaid
graph LR
    Q[User Question] --> TC{Template<br/>Check}
    TC -->|Match| Template[Pre-built<br/>SQL Template]
    TC -->|No Match| RAG[RAG Pipeline]

    RAG --> Schema[Retrieve Schema<br/>Context]
    RAG --> Examples[Retrieve Few-Shot<br/>Examples]

    Schema --> Prompt[Build<br/>Prompt]
    Examples --> Prompt

    Prompt --> LLM[Call LLM<br/>Gemini/OpenRouter]
    LLM --> SQL[Generated<br/>SQL]

    Template --> Execute
    SQL --> Execute[Execute Query]
    Execute --> Format[Format<br/>Response]
    Format --> Response[Natural Language<br/>Answer]

    style RAG fill:#e3f2fd
    style LLM fill:#fff8e1
```

**Key Features:**
- **Template Detection:** Recognizes common query patterns (e.g., "face access")
- **Schema Context:** Retrieves relevant tables/columns from ChromaDB
- **Few-Shot Learning:** Uses similar examples from FAISS index
- **Multi-Provider:** Supports Gemini and OpenRouter LLMs

### 2. Chatbot Orchestrator (LangGraph)

**File:** `app/workflows/chatbot_orchestrator.py`

The orchestrator is a state machine that routes user requests to appropriate tools.

```mermaid
stateDiagram-v2
    [*] --> ClassifyIntent

    ClassifyIntent --> ExecuteQuery: intent=query
    ClassifyIntent --> ExecuteQuery: intent=combined
    ClassifyIntent --> ExecuteReport: intent=report
    ClassifyIntent --> ExecuteEmail: intent=email

    ExecuteQuery --> ExecuteReport: needs_report
    ExecuteQuery --> FormatResponse: query_only

    ExecuteReport --> ExecuteEmail: needs_email
    ExecuteReport --> FormatResponse: report_only

    ExecuteEmail --> FormatResponse

    FormatResponse --> [*]

    note right of ClassifyIntent
        Uses LLM to determine
        user intent from question
    end note

    note right of ExecuteQuery
        RAG SQL Agent
        generates and executes SQL
    end note
```

**Supported Intents:**

| Intent | Example | Tools Used |
|--------|---------|------------|
| `query` | "How many employees?" | Query Database |
| `report` | "Generate PDF report" | Query + Report |
| `email` | "Email me the report" | Query + Report + Email |
| `combined` | "Email PDF of employees" | All tools |

### 3. RAG System

The RAG system combines two vector stores for optimal retrieval:

```mermaid
graph TB
    subgraph "ChromaDB - Schema Context"
        Schema[Database Schema]
        Tables[Table Definitions]
        Columns[Column Metadata]
        Relations[Relationships]

        Schema --> Embed1[Embeddings]
        Tables --> Embed1
        Columns --> Embed1
        Relations --> Embed1

        Embed1 --> ChromaIndex[(ChromaDB<br/>Collection)]
    end

    subgraph "FAISS - Few-Shot Examples"
        Examples[SQL Examples]
        QA[Question-Answer<br/>Pairs]

        Examples --> Embed2[Embeddings]
        QA --> Embed2

        Embed2 --> FAISSIndex[(FAISS<br/>Index)]
    end

    subgraph "Query Time"
        Question[User Question]
        Question --> Search1[Search ChromaDB]
        Question --> Search2[Search FAISS]

        Search1 --> Context[Schema Context]
        Search2 --> FewShot[Similar Examples]

        Context --> Prompt[Build Prompt]
        FewShot --> Prompt
    end

    ChromaIndex --> Search1
    FAISSIndex --> Search2

    style ChromaIndex fill:#fce4ec
    style FAISSIndex fill:#e8f5e9
```

**Components:**

| Component | File | Purpose |
|-----------|------|---------|
| ChromaDB Manager | `app/rag/chroma_manager.py` | Vector store for schema |
| Schema Indexer | `app/rag/schema_indexer.py` | Index database schema |
| Few-Shot Manager | `app/rag/few_shot_manager.py` | FAISS-based example retrieval |
| Schema Enricher | `app/rag/schema_enricher.py` | Add business context |

### 4. Report Generator

**Files:** `app/reports/`, `app/tools/generate_report_tool.py`

```mermaid
graph LR
    Request[Report Request] --> Query[Execute Query]
    Query --> Data[Query Results]

    Data --> Format{Format?}

    Format -->|PDF| PDF[WeasyPrint<br/>PDF Generator]
    Format -->|Excel| Excel[OpenPyXL<br/>Excel Generator]

    PDF --> Template[Apply Template]
    Excel --> Sheets[Create Sheets]

    Template --> File[Save File]
    Sheets --> File

    File --> Response[Return Path<br/>& Metadata]

    style PDF fill:#ffcdd2
    style Excel fill:#c8e6c9
```

**Supported Formats:**
- **PDF:** Professional reports with headers, footers, branding
- **Excel:** Multi-sheet workbooks with formatting

### 5. Gateway System (On-Premises Integration)

**Files:** `app/gateway/`, `app/api/gateway.py`

For databases behind firewalls, the gateway system provides secure access:

```mermaid
sequenceDiagram
    participant Cloud as Cloud Platform
    participant GW as Gateway Agent
    participant DB as On-Prem Database

    Note over GW: Agent starts and connects
    GW->>Cloud: WebSocket Connect
    GW->>Cloud: AUTH_REQUEST (token)
    Cloud->>GW: AUTH_RESPONSE (success)

    Note over Cloud: User makes query
    Cloud->>GW: QUERY_REQUEST (SQL)
    GW->>DB: Execute SQL
    DB->>GW: Results
    GW->>Cloud: QUERY_RESPONSE (data)

    loop Heartbeat
        GW->>Cloud: HEARTBEAT
        Cloud->>GW: HEARTBEAT_ACK
    end
```

**Protocol Messages:**

| Message | Direction | Purpose |
|---------|-----------|---------|
| AUTH_REQUEST | Agent → Cloud | Authenticate gateway |
| AUTH_RESPONSE | Cloud → Agent | Return auth status |
| QUERY_REQUEST | Cloud → Agent | Send SQL to execute |
| QUERY_RESPONSE | Agent → Cloud | Return results |
| HEARTBEAT | Agent → Cloud | Keep-alive signal |

---

## 🔄 Data Flow

### Complete Query Processing Flow

```mermaid
flowchart TB
    subgraph "1. Request Reception"
        User[User] -->|Natural Language| API[/api/chat/query]
        API --> Auth{Authenticate}
        Auth -->|Invalid| Reject[401 Unauthorized]
        Auth -->|Valid| RBAC{Check Role}
    end

    subgraph "2. Intent Classification"
        RBAC --> Classify[Classify Intent]
        Classify -->|Gemini/Keywords| Intent{Intent Type}
    end

    subgraph "3. Query Execution"
        Intent -->|query| SQLAgent[SQL Agent]

        SQLAgent --> Template{Template<br/>Match?}
        Template -->|Yes| PreBuilt[Use Template SQL]
        Template -->|No| RAG[RAG Pipeline]

        RAG --> ChromaDB[(ChromaDB)]
        RAG --> FAISS[(FAISS)]
        ChromaDB --> Context[Schema Context]
        FAISS --> Examples[Few-Shot Examples]

        Context --> Prompt[Build Prompt]
        Examples --> Prompt
        Prompt --> LLM[Call LLM]
        LLM --> SQL[Generated SQL]

        PreBuilt --> Execute
        SQL --> Execute[Execute SQL]
        Execute --> Results[Query Results]
    end

    subgraph "4. Response Formatting"
        Results --> Scope[Apply Data Scoping]
        Scope --> Format[Format Response]
        Format --> Cache[Cache in Memory]
        Cache --> Response[Return Response]
    end

    subgraph "5. Report Generation (Optional)"
        Intent -->|report/combined| Report[Generate Report]
        Report --> PDF[PDF/Excel]
        PDF --> Email{Send Email?}
        Email -->|Yes| SendGrid[SendGrid/SMTP]
        Email -->|No| Download[Return File Path]
    end

    Response --> User
    Download --> User

    style SQLAgent fill:#e3f2fd
    style LLM fill:#fff8e1
    style ChromaDB fill:#fce4ec
```

### RAG Pipeline Detail

```mermaid
flowchart LR
    subgraph "Input"
        Q[User Question]
    end

    subgraph "Retrieval"
        Q --> Embed[Generate Embedding]
        Embed --> S1[Search ChromaDB]
        Embed --> S2[Search FAISS]

        S1 --> R1[Top 10 Schema<br/>Contexts]
        S2 --> R2[Top 3 Similar<br/>Examples]
    end

    subgraph "Augmentation"
        R1 --> Build[Build Prompt]
        R2 --> Build

        Build --> Prompt["System: SQL Expert<br/>Schema: [contexts]<br/>Examples: [few-shots]<br/>Question: [user question]"]
    end

    subgraph "Generation"
        Prompt --> LLM[LLM API Call]
        LLM --> Extract[Extract SQL<br/>from Response]
        Extract --> Validate[Validate SQL<br/>Syntax]
        Validate --> Output[Final SQL Query]
    end

    style Embed fill:#e1f5fe
    style LLM fill:#fff3e0
    style Output fill:#e8f5e9
```

---

## 🗄️ Database Architecture

### Multi-Database Setup

```mermaid
graph TB
    subgraph "Application Databases"
        subgraph "Vector Stores"
            ChromaDB[(ChromaDB<br/>Schema Embeddings)]
            FAISS[(FAISS<br/>Few-Shot Index)]
        end

        subgraph "Application State"
            PostgreSQL[(PostgreSQL<br/>Conversation History)]
        end

        subgraph "Platform Data"
            PlatformDB[(Platform SQL Server<br/>Multi-Tenant Metadata)]
        end
    end

    subgraph "Tenant Databases"
        TenantDB1[(Tenant 1<br/>SQL Server)]
        TenantDB2[(Tenant 2<br/>SQL Server)]
        TenantDB3[(Tenant 3<br/>SQL Server)]
    end

    App[FastAPI Application] --> ChromaDB
    App --> FAISS
    App --> PostgreSQL
    App --> PlatformDB

    App -->|Dynamic Connection| TenantDB1
    App -->|Dynamic Connection| TenantDB2
    App -->|Dynamic Connection| TenantDB3

    style ChromaDB fill:#fce4ec
    style PostgreSQL fill:#e3f2fd
    style PlatformDB fill:#fff3e0
```

### Database Purposes

| Database | Type | Purpose | Key Tables |
|----------|------|---------|------------|
| **ChromaDB** | Vector | Schema embeddings for RAG | `database_schema` collection |
| **FAISS** | Index | Few-shot example retrieval | `few_shot_examples.json` |
| **PostgreSQL** | Relational | Conversation history | `conversations` |
| **Platform DB** | SQL Server | Multi-tenant metadata | `tenants`, `users`, `databases`, `api_keys` |
| **Tenant DB** | SQL Server | Business data (per tenant) | Employee data, etc. |

### Platform Database Schema

```mermaid
erDiagram
    tenants ||--o{ tenant_users : has
    tenants ||--o{ tenant_databases : configures
    tenants ||--o{ api_keys : owns
    tenant_users ||--o{ usage_metrics : generates
    tenant_users ||--o{ audit_logs : creates

    tenants {
        uuid id PK
        string name
        string slug
        string status
        string plan
        datetime created_at
    }

    tenant_users {
        uuid id PK
        uuid tenant_id FK
        string email
        string password_hash
        string role
        boolean is_active
    }

    tenant_databases {
        uuid id PK
        uuid tenant_id FK
        string name
        string server
        string database
        string encrypted_password
        boolean is_default
    }

    api_keys {
        uuid id PK
        uuid tenant_id FK
        string key_hash
        string scope
        datetime expires_at
    }

    usage_metrics {
        uuid id PK
        uuid user_id FK
        string action_type
        int tokens_used
        datetime timestamp
    }

    audit_logs {
        uuid id PK
        uuid user_id FK
        string action
        json details
        datetime timestamp
    }
```

---

## 📡 API Reference

### API Endpoints Overview

```mermaid
graph LR
    subgraph "Public Endpoints"
        Health[GET /health]
        UI[GET /ui/]
    end

    subgraph "Authentication"
        Login[POST /api/auth/login]
        Register[POST /api/auth/register]
        Refresh[POST /api/auth/refresh]
    end

    subgraph "Core Features"
        Chat[POST /api/chat/query]
        Reports[POST /api/reports/generate]
        Actions[POST /api/actions/execute]
    end

    subgraph "Tenant Management"
        Tenant[GET/PUT /api/tenant/]
        Databases[CRUD /api/tenant/databases]
        Users[CRUD /api/tenant/users]
    end

    subgraph "Gateway"
        WS[WS /api/gateway/ws]
        Status[GET /api/gateway/status]
    end

    style Chat fill:#e8f5e9
    style Reports fill:#fff3e0
```

### Endpoint Details

#### Chat API

```http
POST /api/chat/query
Authorization: Bearer <token>
Content-Type: application/json

{
    "question": "How many active employees?",
    "tenant_id": "uuid",
    "user_id": "admin",
    "user_role": "ADMIN",
    "session_id": "session_xxx"
}
```

**Response:**
```json
{
    "question": "How many active employees?",
    "sql_query": "SELECT COUNT(*) FROM Employees WHERE Active = 1",
    "answer": "There are 16,560 active employees.",
    "results": [{"TotalEmployees": 16560}],
    "execution_time_seconds": 2.34,
    "tables_used": ["Employees"],
    "success": true
}
```

#### Authentication API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | Register new tenant |
| `/api/auth/login` | POST | User login |
| `/api/auth/refresh` | POST | Refresh access token |
| `/api/auth/logout` | POST | Logout user |
| `/api/auth/change-password` | POST | Change password |

#### Reports API

```http
POST /api/reports/generate
Authorization: Bearer <token>

{
    "question": "List all IT department employees",
    "format": "pdf",
    "user_role": "ADMIN",
    "max_rows": 1000
}
```

#### Tenant API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tenant/` | GET | Get tenant details |
| `/api/tenant/` | PUT | Update tenant |
| `/api/tenant/databases` | GET | List databases |
| `/api/tenant/databases` | POST | Add database |
| `/api/tenant/databases/{id}/test` | POST | Test connection |
| `/api/tenant/users` | GET | List users |
| `/api/tenant/users` | POST | Create user |

---

## 🔐 Security & RBAC

### Authentication Flow

```mermaid
sequenceDiagram
    participant User
    participant API as FastAPI
    participant Auth as Auth Service
    participant JWT as JWT Handler
    participant DB as Platform DB

    User->>API: POST /auth/login (email, password)
    API->>Auth: authenticate_user()
    Auth->>DB: Find user by email
    DB->>Auth: User record
    Auth->>Auth: Verify password (bcrypt)

    alt Password Valid
        Auth->>JWT: create_access_token()
        JWT->>Auth: Access Token (30 min)
        Auth->>JWT: create_refresh_token()
        JWT->>Auth: Refresh Token (7 days)
        Auth->>API: Tokens
        API->>User: 200 OK + Tokens
    else Password Invalid
        Auth->>API: Authentication Failed
        API->>User: 401 Unauthorized
    end

    Note over User,API: Subsequent Requests
    User->>API: Request + Bearer Token
    API->>JWT: decode_token()
    JWT->>API: User claims (id, role, tenant)
    API->>API: Process request with RBAC
```

### Role Hierarchy

```mermaid
graph TD
    ADMIN[ADMIN<br/>Level 100]
    HR_MANAGER[HR_MANAGER<br/>Level 50]
    HR_STAFF[HR_STAFF<br/>Level 30]
    VIEWER[VIEWER<br/>Level 10]

    ADMIN --> HR_MANAGER
    HR_MANAGER --> HR_STAFF
    HR_STAFF --> VIEWER

    style ADMIN fill:#4caf50,color:#fff
    style HR_MANAGER fill:#2196f3,color:#fff
    style HR_STAFF fill:#ff9800,color:#fff
    style VIEWER fill:#9e9e9e,color:#fff
```

### Permission Matrix

| Role | Query DB | Reports | Email | Manage Users | Manage Tenant |
|------|:--------:|:-------:|:-----:|:------------:|:-------------:|
| ADMIN | ✅ All Data | ✅ All | ✅ | ✅ | ✅ |
| HR_MANAGER | ✅ Department | ✅ Department | ✅ | ❌ | ❌ |
| HR_STAFF | ✅ Own Data | ✅ Own | ❌ | ❌ | ❌ |
| VIEWER | ✅ Read Only | ❌ | ❌ | ❌ | ❌ |

### Data Scoping Logic

```mermaid
flowchart TD
    Query[SQL Query] --> Role{User Role?}

    Role -->|ADMIN| NoScope[No Scoping<br/>Full Access]
    Role -->|HR_MANAGER| DeptScope[Add Department<br/>Filter]
    Role -->|HR_STAFF| UserScope[Add User ID<br/>Filter]
    Role -->|VIEWER| ReadOnly[Read-Only<br/>Limited Tables]

    DeptScope --> AddWhere["WHERE DepartmentID IN<br/>(user's departments)"]
    UserScope --> AddWhere2["WHERE EmployeeID =<br/>user's employee_id"]

    NoScope --> Execute[Execute Query]
    AddWhere --> Execute
    AddWhere2 --> Execute
    ReadOnly --> Execute

    style NoScope fill:#4caf50
    style DeptScope fill:#2196f3
    style UserScope fill:#ff9800
    style ReadOnly fill:#9e9e9e
```

---

## 📁 Project Structure

```
OryggiAI_Service/Advance_Chatbot/
│
├── app/                              # Main application code
│   ├── main.py                       # FastAPI entry point
│   ├── config.py                     # Configuration settings
│   │
│   ├── api/                          # API endpoints
│   │   ├── chat.py                   # Chat query endpoint
│   │   ├── auth.py                   # Authentication endpoints
│   │   ├── reports.py                # Report generation
│   │   ├── tenant.py                 # Tenant management
│   │   ├── gateway.py                # Gateway WebSocket
│   │   ├── actions.py                # Action execution
│   │   └── onboarding.py             # Schema onboarding
│   │
│   ├── agents/                       # AI agents
│   │   ├── sql_agent.py              # RAG SQL Agent
│   │   └── tenant_sql_agent.py       # Tenant-specific agent
│   │
│   ├── workflows/                    # Orchestration
│   │   └── chatbot_orchestrator.py   # LangGraph workflow
│   │
│   ├── rag/                          # RAG components
│   │   ├── chroma_manager.py         # ChromaDB operations
│   │   ├── few_shot_manager.py       # FAISS few-shot
│   │   ├── schema_indexer.py         # Schema indexing
│   │   └── schema_enricher.py        # Schema enrichment
│   │
│   ├── tools/                        # Chatbot tools
│   │   ├── base_tool.py              # Abstract base class
│   │   ├── query_database_tool.py    # Database query
│   │   ├── generate_report_tool.py   # Report generation
│   │   ├── email_tools.py            # Email sending
│   │   └── access_control_tools.py   # Access management
│   │
│   ├── database/                     # Database connections
│   │   ├── connection.py             # SQL Server connection
│   │   └── platform_connection.py    # Platform DB connection
│   │
│   ├── security/                     # Security components
│   │   ├── jwt_handler.py            # JWT operations
│   │   └── encryption.py             # Encryption utilities
│   │
│   ├── middleware/                   # Request middleware
│   │   ├── rbac.py                   # Role-based access
│   │   ├── audit_logger.py           # Audit logging
│   │   └── tenant_context.py         # Tenant isolation
│   │
│   ├── memory/                       # Conversation memory
│   │   ├── conversation_store.py     # PostgreSQL storage
│   │   └── memory_retriever.py       # Memory retrieval
│   │
│   ├── gateway/                      # Gateway components
│   │   ├── connection_manager.py     # Connection tracking
│   │   ├── message_handler.py        # Message processing
│   │   └── query_router.py           # Query routing
│   │
│   ├── models/                       # Pydantic models
│   │   ├── chat.py                   # Chat schemas
│   │   ├── reports.py                # Report schemas
│   │   └── platform/                 # Platform models
│   │
│   ├── reports/                      # Report generators
│   │   ├── generator_factory.py      # Factory pattern
│   │   └── templates/                # Report templates
│   │
│   └── services/                     # Business services
│       ├── auth_service.py           # Authentication
│       └── auto_onboarding/          # Auto-onboarding
│
├── frontend/                         # Web UI
│   ├── index.html                    # Main dashboard
│   ├── style.css                     # Styles
│   └── tenant/                       # Tenant pages
│       ├── login.html
│       ├── register.html
│       ├── chat.html
│       └── dashboard.html
│
├── data/                             # Data storage
│   ├── chroma_db/                    # ChromaDB persistence
│   └── few_shot_examples.json        # SQL examples
│
├── templates/                        # Email templates
├── tests/                            # Test suites
├── logs/                             # Application logs
├── reports_output/                   # Generated reports
│
├── requirements.txt                  # Dependencies
├── docker-compose.yml                # Docker setup
├── .env                              # Configuration
└── README.md                         # Documentation
```

---

## 🛠️ Technology Stack

### Backend Framework

| Technology | Version | Purpose |
|------------|---------|---------|
| FastAPI | 0.109.0 | Web framework |
| Uvicorn | 0.27.0 | ASGI server |
| Pydantic | 2.7.4 | Data validation |
| SQLAlchemy | 2.0.25 | ORM |

### AI/ML Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| LangGraph | 0.2.50 | Workflow orchestration |
| LangChain | 0.3.20 | LLM integration |
| sentence-transformers | 3.3.1 | Embeddings |
| Google Generative AI | 0.8.3 | Gemini LLM |
| ChromaDB | 0.4.22 | Vector database |
| FAISS | 1.9.0 | Similarity search |

### Databases

| Technology | Version | Purpose |
|------------|---------|---------|
| SQL Server | 2019+ | Tenant data |
| PostgreSQL | 16 | Conversation history |
| ChromaDB | Latest | Vector embeddings |

### Security

| Technology | Version | Purpose |
|------------|---------|---------|
| python-jose | 3.3.0 | JWT tokens |
| passlib | 1.7.4 | Password hashing |
| bcrypt | 4.1.2 | Bcrypt algorithm |
| cryptography | 42.0.0 | Encryption |

### Reports & Email

| Technology | Version | Purpose |
|------------|---------|---------|
| OpenPyXL | 3.1.2 | Excel generation |
| WeasyPrint | - | PDF generation |
| SendGrid | 6.11.0 | Email delivery |
| Matplotlib | 3.8.2 | Charts |
| Pandas | 2.1.4 | Data processing |

---

## 📊 Quick Reference Diagrams

### Request Lifecycle

```mermaid
journey
    title User Query Journey
    section Authentication
      Login: 5: User
      Get Token: 5: System
    section Query
      Ask Question: 5: User
      Classify Intent: 4: System
      Generate SQL: 4: System
      Execute Query: 5: System
    section Response
      Format Results: 5: System
      Display Answer: 5: User
```

### System Components Summary

```mermaid
mindmap
  root((OryggiAI))
    API Layer
      FastAPI
      JWT Auth
      RBAC
    AI Layer
      SQL Agent
      RAG Pipeline
      LLM Integration
    Data Layer
      ChromaDB
      FAISS
      SQL Server
      PostgreSQL
    Features
      Natural Language
      Reports
      Email
      Gateway
```

---

## 📞 Support & Resources

- **Documentation:** This file
- **API Docs:** `/docs` (Swagger UI)
- **Health Check:** `/health`
- **Logs:** `logs/oryggi_saas.log`

---

*Last Updated: December 2024*
*Version: 1.0.0*
*Built with ❤️ by OryggiAI Team*
