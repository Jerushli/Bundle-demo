# Bundle Data Assistant

An AI-powered data assistant that allows users to ask questions about order data using natural language and receive accurate answers from a PostgreSQL database.

The application is built using SvelteKit, FastAPI, Groq AI, and Neon PostgreSQL.

## 1. Project Overview

Bundle Data Assistant is a web-based AI chatbot designed to simplify order reporting.

Instead of writing SQL queries manually, users can ask questions in plain English.

For example:

**User:**
How many orders are there?

**Assistant:**
There are 5 orders between September 1 and September 3, 2026.

Users can also ask questions such as:

- Show orders by provider.
- Show orders by date.
- How many orders did Alpha receive?
- Show orders between September 1 and September 3, 2026.

The assistant understands the question, selects the appropriate reporting function, retrieves the data from PostgreSQL, and displays the result.

The AI does not directly execute SQL or generate database numbers.

All reporting figures come from PostgreSQL.

---

## 2. Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Frontend | SvelteKit | Chat interface |
| Programming language | TypeScript | Frontend development |
| Backend | Python + FastAPI | API and application logic |
| AI Model API | Groq | Natural-language understanding |
| AI Model | GPT-OSS 20B | Tool calling and intent interpretation |
| Database | PostgreSQL | Order data storage |
| Database hosting | Neon | Cloud PostgreSQL database |
| Database driver | Psycopg | Python and PostgreSQL connectivity |
| Frontend build | SvelteKit adapter-static | Production frontend |
| Deployment target | Hugging Face Docker Spaces | Hosting the application |

---

## 3. Application Architecture

The application follows a frontend-backend-AI-database architecture.

```text
                      USER
                       |
                       |
                       v
                SvelteKit Frontend
                 Chat Interface
                       |
                       |
                 HTTP POST Request
                    /api/chat
                       |
                       |
                       v
                 FastAPI Backend
                       |
                       |
                       v
                    Groq AI
                       |
                       |
              Understands the question
                       |
                       |
                       v
                Tool Selection
                       |
                       |
                       v
              get_order_summary()
                       |
                       |
                       v
               SQL Reporting Logic
                       |
                       |
                       v
                Neon PostgreSQL
                       |
                       |
                 Database Results
                       |
                       |
                       v
                 FastAPI Backend
                       |
                       |
                JSON API Response
                       |
                       |
                       v
                SvelteKit Frontend
                       |
                       |
                       v
                    USER
```

### How the architecture works

1. The user enters a question in the chat interface.
2. SvelteKit sends the question to the FastAPI backend.
3. FastAPI sends the question to Groq AI.
4. Groq understands the request and selects the appropriate reporting function.
5. FastAPI validates the selected function and its arguments.
6. Python executes a predefined SQL query.
7. Neon PostgreSQL returns the matching database records.
8. FastAPI prepares a response using the database results.
9. SvelteKit displays the answer and reporting table.

The database is the source of truth for all reporting figures.

---

## 4. Project Structure

```text
Bundle-demo/
│
├── backend/
│   │
│   ├── main.py
│   ├── ai.py
│   ├── database.py
│   ├── reporting.py
│   │
│   ├── test_database.py
│   ├── test_groq.py
│   ├── test_reporting.py
│   │
│   ├── requirements.txt
│   ├── .env.example
│   └── .env
│
├── frontend/
│   │
│   ├── src/
│   │   └── routes/
│   │       ├── +page.svelte
│   │       ├── +layout.svelte
│   │       └── +layout.ts
│   │
│   ├── build/
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.ts
│   └── svelte.config.js
│
├── database/
│   └── schema_and_seed.sql
│
├── .gitignore
└── README.md
```

### Important Files

| File | Purpose |
|---|---|
| main.py | FastAPI application and chat endpoint |
| ai.py | Groq integration and AI tool calling |
| database.py | PostgreSQL connection management |
| reporting.py | SQL reporting functions |
| test_database.py | Tests PostgreSQL connectivity |
| test_groq.py | Tests the Groq API connection |
| test_reporting.py | Tests reporting operations |
| +page.svelte | Main chatbot interface |
| schema_and_seed.sql | Creates and populates the sample database |
| .env.example | Example environment configuration |
| requirements.txt | Python dependencies |

The `.env` file contains private credentials and must not be committed to GitHub.

---

# 5. Development Progress

## Day 1 — Project Setup and Basic Integration

**Status: Completed**

The initial development environment and application components were successfully created.

### Completed Work

- Created the project repository.
- Set up the Python virtual environment.
- Created the SvelteKit frontend.
- Created the FastAPI backend.
- Implemented the initial chat interface.
- Connected the frontend and backend using HTTP requests.
- Created the Neon PostgreSQL database.
- Created the providers and orders tables.
- Inserted sample records.
- Connected Python to PostgreSQL using Psycopg.
- Successfully retrieved real database results through FastAPI.
- Configured Groq API credentials.
- Successfully tested the Groq API connection.

### Day 1 Result

The chatbot successfully retrieved the total order count from PostgreSQL.

```text
User:
How many orders are there?

Assistant:
There are 5 orders in the database.
```

---

## Day 2 — AI Tool Calling and Database Reporting

**Status: Completed**

Groq AI was integrated with the reporting functions to enable natural-language database queries.

### Completed Work

- Created the reporting.py module.
- Implemented the get_order_summary() function.
- Added total-order reporting.
- Added provider-wise reporting.
- Added date-wise reporting.
- Added provider filtering.
- Implemented Groq function calling.
- Connected Groq to the reporting function.
- Connected the reporting function to PostgreSQL.
- Replaced the temporary keyword-matching logic.
- Implemented structured JSON responses.
- Tested the complete AI reporting workflow.

### Reporting Function

```python
get_order_summary(
    from_date,
    to_date,
    group_by,
    provider
)
```

The reporting function supports:

| Parameter | Description |
|---|---|
| from_date | Starting date |
| to_date | Ending date |
| group_by | total, provider, or date |
| provider | Optional provider filter |

### Day 2 Result

```text
User:
Show orders by provider.

Assistant:
Found 5 orders across 2 providers.
```

| Provider | Total Orders |
|---|---:|
| Alpha | 3 |
| Beta | 2 |

---

## Day 3 — Frontend Improvements and Testing

**Status: Completed for the initial demo**

The basic frontend was upgraded into a responsive, ChatGPT-inspired web application.

### Completed Work

- Designed the chatbot interface.
- Added a conversation sidebar.
- Added a New Chat button.
- Added suggested questions.
- Added user and assistant message styles.
- Added loading indicators.
- Added database result tables.
- Added error messages.
- Added browser-based conversation storage.
- Added responsive layouts for desktop and mobile.
- Tested the reporting functions through the website.
- Tested conversation history.
- Tested invalid-date handling.
- Tested requests with no matching records.
- Tested backend connection failure handling.

### Conversation History

Conversations are currently stored in the browser using localStorage.

Users can create multiple conversations and reopen previous chats.

Note: The backend currently processes each question independently. Full AI conversational memory is not yet implemented.

---

## Day 4 — Production Build and Deployment Preparation

**Status: In Progress**

The project is being prepared for deployment through Hugging Face Docker Spaces.

### Completed Work

- Installed SvelteKit adapter-static.
- Configured the static frontend build.
- Updated the Vite configuration.
- Removed unnecessary library packaging from the build command.
- Enabled prerendering.
- Successfully generated the production frontend.

The production build contains:

```text
frontend/build/
│
├── index.html
├── 200.html
├── _app/
├── favicon.svg
└── robots.txt
```

### Current Deployment Work

The next stage is to serve the frontend and FastAPI backend through a single server.

The planned architecture is:

```text
             Hugging Face Docker Space
                       |
                       v
                 FastAPI Server
                   Port 7860
                       |
              -------------------
              |                 |
              v                 v
         Static Frontend     /api/chat
                                |
                                v
                             Groq AI
                                |
                                v
                         Reporting Function
                                |
                                v
                         Neon PostgreSQL
```

---

# 6. Database Design

The demo uses two relational tables.

### Providers

| provider_id | provider_name |
|---|---|
| 1 | Alpha |
| 2 | Beta |

### Orders

| order_id | provider_id | order_date |
|---|---|---|
| 1 | 1 | 2026-09-01 |
| 2 | 1 | 2026-09-02 |
| 3 | 1 | 2026-09-03 |
| 4 | 2 | 2026-09-01 |
| 5 | 2 | 2026-09-03 |

### Database Relationship

```text
       providers
    ----------------
       provider_id
       provider_name
            |
            |
            v
         orders
    ----------------
       order_id
       provider_id
       order_date
```

The provider_id column connects orders to their providers.

The application uses SQL operations such as JOIN, COUNT, GROUP BY, and WHERE to generate reports.

---

# 7. How to Run the Project Locally

## Prerequisites

Install the following:

- Python 3.12
- Node.js and npm
- Git
- VS Code or another code editor

You also need:

- A Neon PostgreSQL database.
- A Groq API key.

## Step 1 — Clone the Repository

```bash
git clone YOUR_REPOSITORY_URL
```

Open the project directory:

```bash
cd Bundle-demo
```

Use the actual cloned directory name if it differs.

## Step 2 — Create a Python Virtual Environment

On Windows:

```powershell
py -3.12 -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Step 3 — Install Python Dependencies

```powershell
python -m pip install -r backend/requirements.txt
```

## Step 4 — Configure Environment Variables

Create:

```text
backend/.env
```

Use backend/.env.example as the reference.

Add:

```env
DATABASE_URL=YOUR_NEON_DATABASE_CONNECTION_STRING
GROQ_API_KEY=YOUR_GROQ_API_KEY
```

Keep both credentials private.

## Step 5 — Configure PostgreSQL

Open the Neon SQL Editor.

Execute:

```text
database/schema_and_seed.sql
```

This creates the sample tables and inserts the demo records.

## Step 6 — Test PostgreSQL

From the project root:

```powershell
python backend/test_database.py
```

Expected:

```text
Database connected successfully!
Total orders: 5
```

## Step 7 — Test Groq

```powershell
python backend/test_groq.py
```

Expected:

```text
Groq API connected successfully!
```

## Step 8 — Test Reporting

```powershell
python -m backend.test_reporting
```

Expected reporting results:

| Report | Result |
|---|---|
| Total orders | 5 |
| Alpha orders | 3 |
| Beta orders | 2 |
| September 1 | 2 |
| September 2 | 1 |
| September 3 | 2 |

## Step 9 — Start FastAPI

From the project root:

```powershell
python -m uvicorn backend.main:app --reload
```

Open the API documentation:

http://127.0.0.1:8000/docs

## Step 10 — Start the Frontend

Open another terminal.

```powershell
cd frontend
```

Install dependencies:

```powershell
npm.cmd install
```

Start the development server:

```powershell
npm.cmd run dev
```

Open the localhost address displayed by Vite.

Note: If the frontend uses the relative API URL /api/chat during development, configure a Vite proxy to FastAPI or test the production frontend through FastAPI instead.

---

# 8. Production Frontend Build

To generate the frontend for deployment:

```powershell
cd frontend
```

Run:

```powershell
npm.cmd run check
```

Then:

```powershell
npm.cmd run build
```

The generated website will be available in:

```text
frontend/build/
```

FastAPI will serve these static files in the combined deployment.

---

# 9. Important Security Considerations

The application uses the following security principles:

- API credentials are stored in environment variables.
- Database passwords are not exposed in frontend code.
- The AI does not receive database credentials.
- The AI cannot directly execute arbitrary SQL.
- Backend reporting functions control database access.
- SQL values are passed through parameterized queries.
- Reporting dates and grouping parameters are validated.
- Invalid requests are handled without inventing database results.

Additional authentication, read-only database permissions, query timeouts, and production security checks are planned before public deployment.

---
# why using render

By searching across the multiple free hosting service , render supports existing python friendly backend and hosting the website for 15 minutes without any error.After every 15 minutes the connection get established freshly.

---
# 10. Pending Tasks

The following tasks remain:

- Complete FastAPI static frontend hosting.
- Create the Dockerfile.
- Configure Hugging Face Docker Spaces.
- Configure production environment variables.
- Deploy the complete application.
- Test the public website.
- Add basic demo authentication.
- Configure a read-only PostgreSQL database role.
- Finalize production security settings.
- Complete deployment documentation.
- Conduct final end-to-end testing.

---

# 11. Project Goal

The goal of Bundle Data Assistant is to demonstrate how natural-language questions can be converted into controlled database reporting operations using AI.

The project combines frontend development, backend APIs, AI tool calling, SQL reporting, and cloud database integration.

The final application will allow users to access order information through a simple chat interface without manually writing SQL queries.
