# Employee Management System

A production-style backend project for managing employees, leave workflows, role-based access, and audit trails using FastAPI, MySQL, SQLAlchemy, Alembic, and JWT authentication. The project is designed as a modular FastAPI application using multiple files and routers, which is the recommended structure for larger FastAPI applications instead of a single-file setup. FastAPI also provides built-in support for OAuth2 password flow and JWT-style bearer token patterns, which makes it a strong fit for secure authentication and authorization layers.

## Features

- JWT-based authentication with protected API routes using FastAPI security dependencies
- Role-based authorization for `ADMIN`, `HR`, `MANAGER`, and `EMPLOYEE`
- Employee profile management and organization structure
- Leave request, approval, rejection, and cancellation workflows
- Audit logging for sensitive actions such as login, employee updates, and leave approvals
- MySQL persistence with SQLAlchemy 2.0 ORM patterns
- Alembic migrations for version-controlled schema changes
- Dockerized local development setup
- GitHub-friendly modular codebase for portfolio and interview use

## Tech Stack

| Layer | Technology |
|-------|------------|
| API Framework | FastAPI |
| Database | MySQL |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic |
| Auth | JWT Bearer Tokens with FastAPI security utilities |
| Validation | Pydantic |
| Server | Uvicorn |
| Containerization | Docker, Docker Compose |

## Modules

### 1. Authentication & Authorization
Handles login, token generation, current-user resolution, and role-based access checks. FastAPI’s security system is designed around reusable dependencies, which is useful for implementing `get_current_user` and role-protection patterns across routes.

### 2. Employee Management
Handles employee CRUD operations, department mapping, reporting manager relationships, employee status, and self-profile access.

### 3. Leave Management
Handles leave types, leave balances, leave requests, approval flow, rejection flow, and cancellation logic.

### 4. Audit Logging
Tracks important system actions such as logins, employee creation, employee updates, leave applications, and leave approvals for traceability.

## Project Structure

FastAPI recommends splitting larger applications into multiple files with routers and proper package organization, which is the pattern this project follows.

```text
employee-management-system/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── security.py
│   │   └── dependencies.py
│   ├── models/
│   │   ├── user.py
│   │   ├── role.py
│   │   ├── employee.py
│   │   ├── leave.py
│   │   └── audit_log.py
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── employee.py
│   │   ├── leave.py
│   │   └── audit.py
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── employee_service.py
│   │   ├── leave_service.py
│   │   └── audit_service.py
│   ├── api/
│   │   ├── auth.py
│   │   ├── employees.py
│   │   ├── leaves.py
│   │   └── audit.py
│   └── utils/
├── alembic/
├── tests/
├── .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Core Roles

| Role | Access |
|------|--------|
| ADMIN | Full system access |
| HR | Manage employees, view and process leave records |
| MANAGER | View team members and approve or reject team leave |
| EMPLOYEE | View self profile, apply leave, view own leave history |

## Main API Areas

| Module | Example Endpoints |
|--------|-------------------|
| Auth | `POST /auth/login`, `GET /auth/me` |
| Employees | `POST /employees`, `GET /employees`, `GET /employees/{id}`, `PATCH /employees/{id}/status` |
| Leaves | `POST /leaves`, `GET /leaves/my`, `PATCH /leaves/{id}/approve`, `PATCH /leaves/{id}/reject` |
| Audit | `GET /audit-logs` |

## Database Design

The system is built around separate identity and domain models so authentication logic and HR data remain cleanly separated.

Main tables:
- `users`
- `roles`
- `employees`
- `departments`
- `leave_types`
- `leave_balances`
- `leave_requests`
- `audit_logs`

SQLAlchemy 2.0 is suitable for defining these ORM models in a modern Python backend, while Alembic provides versioned migration support for managing schema changes over time.

## Authentication Flow

1. User logs in with email/username and password.
2. API verifies credentials and returns a JWT access token.
3. Protected routes use bearer token authentication.
4. Dependency-based current-user logic loads the authenticated user.
5. Role-check dependencies enforce authorization before business logic runs.

This approach aligns well with FastAPI’s documented security patterns for OAuth2 password flow and bearer token usage.

## Business Rules

- Only authorized roles can create or update employee records.
- Employees can view their own profile and leave history.
- Managers can approve or reject leave requests for their team.
- Leave requests should not exceed available balance.
- Overlapping leave requests should be blocked.
- Sensitive actions should create audit log entries.
- Inactive users should not be allowed to log in.

## Local Setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd employee-management-system
```

### 2. Create environment file

```bash
cp .env.example .env
```

Fill values such as:
- `DATABASE_URL`
- `SECRET_KEY`
- `ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`

### 3. Start with Docker

```bash
docker compose up --build
```

### 4. Run migrations

```bash
alembic upgrade head
```

### 5. Start the app manually (optional)

```bash
uvicorn app.main:app --reload
```

## Future Improvements

- Refresh token support
- Email notifications for leave approval/rejection
- Attendance management
- Payroll integration
- Pagination, filtering, and search improvements
- Unit and integration test coverage
- CI pipeline for linting, tests, and Docker checks

## License

This project is for learning, portfolio, and demonstration purposes.
