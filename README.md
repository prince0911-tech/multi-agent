# Multi-Agent AI Productivity System

A **production-ready multi-agent AI system** built with FastAPI, LangGraph, OpenAI, and MongoDB. It helps users manage tasks, schedules, and information through coordinated AI agents.

---

## 🏗 Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     FastAPI REST API                     │
│   /query  /tasks  /events  /notes  /insights  /users     │
└──────────────────────┬───────────────────────────────────┘
                       │
            ┌──────────▼──────────┐
            │  OrchestratorAgent  │  ← LangGraph state machine
            └──┬──────┬──────┬───┘
               │      │      │
          ┌────▼─┐ ┌──▼──┐ ┌▼──────┐ ┌──────────┐
          │Task  │ │Cal. │ │Notes  │ │  Risk    │
          │Agent │ │Agent│ │Agent  │ │  Agent   │
          └──────┘ └─────┘ └───────┘ └──────────┘
               │      │        │           │
            ┌──▼──────▼────────▼───────────▼──┐
            │        MCP-style Tool Layer       │
            │  task_tool / calendar_tool /      │
            │  notes_tool                       │
            └──────────────┬────────────────────┘
                           │
           ┌───────────────┼────────────────┐
           │               │                │
    ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
    │   MongoDB   │ │  FAISS Vec  │ │ APScheduler │
    │  (Motor)    │ │   Memory    │ │  (jobs)     │
    └─────────────┘ └─────────────┘ └─────────────┘
```

---

## 🚀 Features

| Feature | Description |
|---------|-------------|
| **Multi-agent coordination** | LangGraph orchestrator routes queries to Task, Calendar, Notes, or Risk agents |
| **Natural language queries** | "What should I do today?" / "Show delayed tasks" |
| **Smart prioritisation** | Scoring: `(urgency×0.4) + (importance×0.4) + (base_priority×0.2)` |
| **Auto-scheduling** | Calendar Agent finds free slots and schedules tasks automatically |
| **Proactive alerts** | APScheduler checks deadlines every 30 minutes |
| **Risk detection** | Risk Agent detects overload and missed deadlines |
| **Semantic memory** | FAISS vector store for personalised responses |
| **Multi-user support** | Tasks, events, and calendars scoped per user with shared views |
| **Productivity insights** | Dashboard API with completion rates, daily patterns, priority distribution |
| **Inter-agent communication** | Agents communicate internally (Calendar → Task → prep task) |

---

## 📁 Project Structure

```
multi-agent/
├── app/
│   ├── main.py                  # FastAPI entry point + lifespan
│   ├── config.py                # Pydantic settings
│   ├── database/
│   │   ├── connection.py        # Motor async MongoDB client
│   │   └── models.py            # Pydantic document models
│   ├── agents/
│   │   ├── orchestrator.py      # LangGraph primary agent
│   │   ├── task_agent.py        # Task management agent
│   │   ├── calendar_agent.py    # Calendar & scheduling agent
│   │   ├── notes_agent.py       # Notes agent + FAISS search
│   │   └── risk_agent.py        # Risk detection agent
│   ├── tools/
│   │   ├── task_tool.py         # Task CRUD MCP-style tool
│   │   ├── calendar_tool.py     # Calendar + free-slot tool
│   │   └── notes_tool.py        # Notes CRUD + search tool
│   ├── routes/
│   │   ├── query.py             # POST /query
│   │   ├── tasks.py             # CRUD /tasks
│   │   ├── events.py            # CRUD /events
│   │   ├── notes.py             # CRUD /notes
│   │   ├── insights.py          # GET /insights
│   │   └── users.py             # CRUD /users
│   ├── scheduler/
│   │   └── jobs.py              # APScheduler background jobs
│   └── memory/
│       └── vector_store.py      # FAISS vector memory
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── DEPLOYMENT.md                # Google Cloud Run deployment guide
└── README.md
```

---

## ⚡ Quick Start (Local)

### 1. Clone and configure

```bash
git clone https://github.com/prince0911-tech/multi-agent.git
cd multi-agent
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 2. Run with Docker Compose

```bash
docker compose up --build
```

The API will be available at **http://localhost:8080**
Interactive docs at **http://localhost:8080/docs**

### 3. Run without Docker (development)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start MongoDB (or use Atlas)
# Set MONGODB_URI in .env

# Run the app
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

---

## 🔌 API Usage Examples

### Create a user
```bash
curl -X POST http://localhost:8080/users/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alice Smith",
    "email": "alice@example.com",
    "preferences": {"timezone": "America/New_York"}
  }'
```

### Ask the AI assistant (main endpoint)
```bash
curl -X POST http://localhost:8080/query/ \
  -H "Content-Type: application/json" \
  -d '{"user_id": "USER_ID", "query": "What should I do today?"}'
```

```bash
curl -X POST http://localhost:8080/query/ \
  -H "Content-Type: application/json" \
  -d '{"user_id": "USER_ID", "query": "Show me my delayed tasks"}'
```

```bash
curl -X POST http://localhost:8080/query/ \
  -H "Content-Type: application/json" \
  -d '{"user_id": "USER_ID", "query": "Am I overloaded this week?"}'
```

### Create a task
```bash
curl -X POST http://localhost:8080/tasks/ \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "USER_ID",
    "title": "Prepare quarterly report",
    "priority": "high",
    "importance": 8,
    "deadline": "2024-07-15T17:00:00"
  }'
```

### Create a calendar event
```bash
curl -X POST http://localhost:8080/events/ \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "USER_ID",
    "title": "Team standup",
    "start_time": "2024-07-10T09:00:00",
    "end_time": "2024-07-10T09:30:00"
  }'
```

### Find free time slots
```bash
curl "http://localhost:8080/events/free-slots?user_id=USER_ID&date=2024-07-10&duration_minutes=60"
```

### Get productivity insights
```bash
curl "http://localhost:8080/insights/?user_id=USER_ID&days=30"
```

### Create a note
```bash
curl -X POST http://localhost:8080/notes/ \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "USER_ID",
    "title": "Meeting notes",
    "content": "Discussed Q3 roadmap, decided on agile sprints",
    "tags": ["meeting", "roadmap"]
  }'
```

---

## 🧪 Example API Responses

### POST /query/ — "What should I do today?"
```json
{
  "user_id": "user_abc123",
  "query": "What should I do today?",
  "route": "task",
  "answer": "Here are your top priorities for today:\n\n1. **Prepare quarterly report** (HIGH priority, due today at 5 PM)\n2. **Review PR #42** (MEDIUM priority, due tomorrow)\n\nYou have 2 tasks overdue — I recommend addressing those first.",
  "raw_agent_output": "..."
}
```

### GET /insights/?user_id=user_abc123&days=30
```json
{
  "user_id": "user_abc123",
  "period_days": 30,
  "task_stats": {
    "total": 24,
    "completed_in_period": 18,
    "overdue": 2,
    "in_progress": 4,
    "completion_rate_percent": 75.0
  },
  "priority_distribution": {"high": 6, "medium": 12, "low": 6},
  "daily_completions": {"2024-07-01": 3, "2024-07-02": 2},
  "active_risk_warnings": 1,
  "unread_alerts": 2,
  "generated_at": "2024-07-10T12:00:00"
}
```

---

## 🚢 Deployment

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for the complete Google Cloud Run deployment guide.

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + Uvicorn |
| AI / Agents | OpenAI GPT-4o + LangChain + LangGraph |
| Database | MongoDB (Motor async driver) |
| Vector Memory | FAISS + sentence-transformers |
| Scheduler | APScheduler |
| Containerisation | Docker |
| Cloud | Google Cloud Run |