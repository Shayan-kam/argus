argus/
│
├── backend/
│   │
│   ├── main.py
│   ├── agent.py
│   ├── repository.py
│   ├── github.py
│   ├── findings.py
│   ├── report.py
│   ├── rules.py
│   ├── orchestrator.py
│   ├── preprocessor.py
│   ├── routing.py
│   ├── timing.py
│   ├── requirements.txt
│   ├── .env
│   │
│   └── agents/
│       ├── __init__.py
│       ├── base_agent.py
│       ├── sql_injection.py
│       ├── xss.py
│       └── secrets.py
│
└── frontend/
    ├── package.json
    ├── src/
    │   ├── App.jsx
    │   ├── main.jsx
    │   └── ...
    └── ...

Move towards: 

Repository
    ↓
Security Agent
    ↓
search_code()
read_file()
get_file_context()
    ↓
Relevant code
    ↓
LLM


For example:

"Find SQL queries"
       ↓
search repository
       ↓
5 relevant files
       ↓
read those files
       ↓
LLM

