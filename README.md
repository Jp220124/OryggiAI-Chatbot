# Advance Chatbot

**Agentic AI Chatbot with RAG, Report Generation, and Action Execution**

Version 1.0.0

---

## Overview

Advance Chatbot is a next-generation AI-powered chatbot system that goes beyond simple question-answering. Built with LangGraph and RAG (Retrieval-Augmented Generation), it provides:

- **Unlimited Database Queries**: Answer any question that can be derived from your database using RAG
- **Report Generation**: Generate PDF/Excel reports and deliver via email
- **Action Execution**: Perform access control actions with human-in-the-loop confirmation
- **Role-Based Access Control**: 4-tier permission system (ADMIN, HR_MANAGER, HR_STAFF, VIEWER)

---

## Features

### 1. Unlimited Query Capability (RAG)
- Answer **any** question that can be answered from your database
- No more limited to predefined queries
- Uses ChromaDB vector store for schema understanding
- Improves success rate from 33% to 90%+

### 2. Report Generation
- Generate PDF reports with custom templates
- Generate Excel spreadsheets with charts
- Natural language time ranges ("last 30 days", "this week")
- Download or email reports directly

### 3. Action Execution
- Grant/block/revoke access permissions
- Human-in-the-loop confirmation workflow
- 100% audit logging
- Only ADMIN role can execute actions

### 4. Role-Based Access Control (RBAC)
- **ADMIN**: Full access to all features
- **HR_MANAGER**: Reports + department-scoped queries
- **HR_STAFF**: Basic queries for their department
- **VIEWER**: Read-only access

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         FastAPI API                         │
│                    (REST Endpoints)                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    LangGraph Agent                          │
│            (State Machine Orchestration)                    │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Query      │  │   Report     │  │   Action     │    │
│  │   Tool       │  │   Tool       │  │   Tool       │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└────────┬─────────────────┬────────────────┬───────────────┘
         │                 │                │
         ▼                 ▼                ▼
┌────────────────┐  ┌────────────┐  ┌────────────┐
│   ChromaDB     │  │  WeasyPrint│  │  SQL       │
│  (RAG Store)   │  │  (PDF Gen) │  │  Database  │
└────────────────┘  └────────────┘  └────────────┘
```

---

## Project Structure

```
Advance_Chatbot/
├── app/
│   ├── agents/           # LangGraph agents
│   ├── tools/            # Tool implementations
│   ├── rag/              # RAG system (ChromaDB)
│   ├── middleware/       # RBAC middleware
│   ├── reports/          # Report generation
│   ├── api/              # FastAPI routes
│   ├── database/         # Database connection
│   ├── security/         # Authentication & security
│   ├── models/           # Pydantic models
│   ├── utils/            # Utilities
│   ├── config.py         # Configuration
│   └── main.py           # FastAPI entry point
├── data/
│   ├── chroma_db/        # Vector store data
│   └── schemas/          # Database schema files
├── templates/            # Report templates (Jinja2)
├── reports_output/       # Generated reports
├── logs/                 # Application logs
├── tests/                # Unit & integration tests
├── requirements.txt      # Python dependencies
├── .env.template         # Environment variables template
├── .gitignore
└── README.md
```

---

## Installation

### Prerequisites

- Python 3.10+
- SQL Server database
- OpenAI API key
- SendGrid API key (optional, for email)

### Setup Steps

1. **Clone/Copy the Project**
   ```bash
   cd D:\OryggiAI_Service\Advance_Chatbot
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # Linux/Mac
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment**
   ```bash
   copy .env.template .env
   # Edit .env with your actual values
   ```

5. **Configure .env**
   Edit `.env` file with your credentials:
   ```env
   OPENAI_API_KEY=sk-...
   DB_SERVER=your_server
   DB_NAME=your_database
   DB_USERNAME=your_user
   DB_PASSWORD=your_password
   SECRET_KEY=your_secret_key_here
   ```

6. **Initialize Database Schema** (if needed)
   ```bash
   # TODO: Run schema migration script when available
   ```

7. **Start the Application**
   ```bash
   python -m app.main
   ```

The server will start on `http://localhost:9000`

---

## Usage

### 1. Health Check
```bash
curl http://localhost:9000/health
```

### 2. Ask Questions (Unlimited Queries)
```bash
POST /api/chat/query
{
  "question": "How many employees joined in the last 30 days?",
  "user_id": "admin",
  "tenant_id": "default"
}
```

### 3. Generate Reports
```bash
POST /api/reports/generate
{
  "report_type": "attendance",
  "start_date": "2025-01-01",
  "end_date": "2025-01-31",
  "format": "pdf",
  "email_to": "manager@company.com"
}
```

### 4. Execute Actions
```bash
POST /api/actions/execute
{
  "action_type": "grant_access",
  "user_id": "12345",
  "door_id": "101",
  "confirm": true
}
```

---

## Development

### Running Tests
```bash
# Unit tests
pytest tests/unit

# Integration tests
pytest tests/integration

# All tests with coverage
pytest --cov=app tests/
```

### Code Quality
```bash
# Format code
black app/

# Lint code
flake8 app/

# Type checking
mypy app/
```

---

## Configuration

### Environment Variables

See `.env.template` for all available configuration options.

Key settings:
- **Database**: Connection details for SQL Server
- **OpenAI**: API key and model selection
- **ChromaDB**: Vector store configuration
- **Email**: SendGrid or SMTP settings
- **RBAC**: Role definitions
- **Reports**: Output directory and formats

### Google Embedding Configuration

The system supports Google's `text-embedding-004` model for improved semantic search.

1. **Enable Google Embeddings**:
   Set `EMBEDDING_PROVIDER=google` in `.env`

2. **Configure Model**:
   ```env
   GOOGLE_EMBEDDING_MODEL=models/text-embedding-004
   GOOGLE_EMBEDDING_TASK_TYPE=retrieval_document
   ```

3. **Re-index Schemas**:
   Run the re-indexing script to populate the vector store with new embeddings:
   ```bash
   python reindex_schemas_google.py --rebuild
   ```

---

## Implementation Phases

Based on the detailed plan in Obsidian (`Advance-Chatbot.md`):

- **Phase 1** (Week 1-2): RAG System + Unlimited Queries
- **Phase 2** (Week 2-3): Tool Registry + RBAC
- **Phase 3** (Week 3-4): Report Generation (PDF/Excel)
- **Phase 4** (Week 4-5): Email Integration
- **Phase 5** (Week 5-6): Action Execution + Confirmation
- **Phase 6** (Week 7-8): Testing + Optimization

---

## Security

### Authentication
- JWT token-based authentication
- Token expiry: 30 minutes (configurable)

### RBAC
- 4 roles: ADMIN, HR_MANAGER, HR_STAFF, VIEWER
- Permission matrix enforced at middleware level
- Audit logging for all actions

### Data Protection
- SQL injection prevention
- Input validation on all endpoints
- Secure password hashing (bcrypt)

---

## Deployment

### Production Checklist

1. Set `ENVIRONMENT=production` in `.env`
2. Set `DEBUG=False`
3. Change default admin password
4. Configure production database
5. Set up SSL/TLS certificates
6. Configure firewall rules
7. Set up monitoring and alerts
8. Enable audit logging

### Docker Deployment (TODO)
```bash
# Build image
docker build -t advance-chatbot:1.0.0 .

# Run container
docker run -p 9000:9000 --env-file .env advance-chatbot:1.0.0
```

---

## Troubleshooting

### Common Issues

**Database Connection Fails**
- Check database credentials in `.env`
- Ensure SQL Server is running
- Check firewall allows connection

**OpenAI API Errors**
- Verify API key is valid
- Check API quota/limits
- Review error logs in `logs/`

**ChromaDB Errors**
- Ensure `data/chroma_db/` directory exists
- Check disk space
- Try reinitializing vector store

---

## License

Copyright © 2025 Oryggi AI. All rights reserved.

---

## Support

For support and questions:
- Email: support@oryggi.ai
- Documentation: See `D:\temp\advance-chatbot-plan.md`
- Issues: Contact development team

---

**Built with:**
- FastAPI
- LangGraph
- ChromaDB
- OpenAI GPT-4
- SQL Server
- WeasyPrint
- sentence-transformers
- Google Gemini (Embeddings & Generation)
