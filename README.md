# Gold-EDU E-Learning Platform

A production-focused Learning Management System built with Django, Django REST Framework, Channels, and Redis.

Gold-EDU supports public course discovery, structured module learning, instructor content management, token-secured APIs, real-time course chat, and in-page AI assistance.

[Live Demo](https://e-learning-aae0.onrender.com) | [Client Usage Guide](./docs/usage.md) | [API Documentation](./docs/api.md)

## Preview

![Homepage Preview](./docs/images/preview-home.png)
![Course Workspace Preview](./docs/images/preview-workspace.png)
![API Tools Preview](./docs/images/preview-api-tools.png)

## Table of Contents

- [Project Overview](#project-overview)
- [Key Features](#key-features)
- [Architecture and Data Model](#architecture-and-data-model)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup and Installation](#setup-and-installation)
- [Environment Variables](#environment-variables)
- [Run the Project](#run-the-project)
- [API Summary](#api-summary)
- [Management Commands](#management-commands)
- [Security and Access Control](#security-and-access-control)
- [Deployment Notes (Render)](#deployment-notes-render)
- [Roadmap](#roadmap)
- [License](#license)

## Project Overview

Gold-EDU is a full-stack LMS designed to demonstrate practical backend engineering and product-level feature integration in one cohesive project:

- Multi-role workflow for visitors, students, instructors, and administrators
- Course authoring and module-based delivery
- Rich content support: text, images, videos, and downloadable files
- Real-time collaboration with persistent chat history
- AI study assistant with session-aware conversational context
- Developer-facing API tooling with token management UI

## Key Features

### 1) Course Catalog and Discovery

- Public course listing with subject filters
- Search across course title, overview, and subject
- Subject metadata with course counts
- Cache-backed catalog queries in production for better performance

### 2) Structured Learning Experience

- Hierarchical model: `Subject -> Course -> Module -> Content`
- Ordered modules and ordered content blocks
- Student enrollment flow with protected course detail pages
- Module-focused workspace with progress and time-spent visibility

### 3) Rich Content Types

- Text content rendered as Markdown
- Sanitized HTML output using `bleach`
- Embedded video support via `django-embed-video`
- Image content delivery through authenticated endpoints
- File downloads through authenticated endpoints

### 4) Instructor CMS

- Instructor course CRUD
- Inline module management via formsets
- Dynamic content creation and editing (`text`, `image`, `video`, `file`)
- Drag-and-drop ordering for modules and content using JSON endpoints
- Owner-scoped querysets for data isolation

### 5) Student Progress Tracking

- Enrollment-specific course list
- Automatic module completion tracking
- Time tracking per module
- Aggregate course time and global progress percentage helpers

### 6) Real-Time Course Chat

- WebSocket chat rooms scoped by course
- Redis-backed Channels layer
- Message persistence in database
- Initial recent message load + infinite scroll history pagination
- Enrollment checks before chat room access

### 7) AI Assistant

- In-page assistant widget for authenticated users
- Gemini API integration with multi-key fallback (`API1_KEY` to `API4_KEY`)
- Session-based history window for context-aware responses
- Markdown rendering for assistant replies

### 8) Developer API

- DRF router-based API for courses and subjects
- Token authentication + Basic authentication support
- Protected enrollment and course-content endpoints
- `IsEnrolled` permission class for access control
- Paginated responses (`page_size`, `max_page_size`)
- Token dashboard UI with copy and rotate actions
- Full API usage guide in `docs/api.md`

### 9) User Experience and UI

- Responsive template-based interface
- Dark/light mode toggle persisted in local storage
- Global search bar in top navigation
- Sidebar progress card and integrated assistant panel

## Architecture and Data Model

Core course model chain:

- `Subject`
- `Course`
- `Module`
- `Content`

Content is polymorphic through Django ContentTypes:

- `Text`
- `Video`
- `Image`
- `File`

Additional domain models:

- `students.ModuleProgress` for completion and time tracking
- `chat.Message` for persistent discussion history

Important implementation details:

- Custom `OrderField` auto-assigns ordering per parent object
- Generic content rendering via `ItemBase.render()`
- Course content API returns rendered content blocks for direct client display

## Tech Stack

- Backend: Django 6, Django ORM, class-based views
- API: Django REST Framework + Token Auth
- Real-time: Channels + Daphne + Redis
- Database: Configurable via `DATABASE_URL` (PostgreSQL recommended in production)
- Caching: `django-redis` (Redis) with local-memory fallback for non-Redis environments
- Frontend: Django Templates, custom CSS, vanilla JavaScript
- Media and content: Pillow, markdown, bleach, embed video
- Deployment utilities: WhiteNoise, Gunicorn, dj-database-url

## Project Structure

```text
Deploy e-learning/
|- edu/
|  |- edu/                    # Project settings, ASGI/WSGI, root urls
|  |- courses/                # Catalog, instructor CMS, content models, API
|  |- students/               # Enrollment, student workspace, progress tracking
|  |- chat/                   # WebSocket chat, persistence, history endpoints
|  |- assistant/              # AI assistant endpoints, widget context, UI
|  |- media/                  # Uploaded media (development/local)
|  |- manage.py
|- docs/
|  |- api.md                  # Detailed API usage documentation
|  |- images/                 # README preview screenshots
|- api_examples/
|  |- enroll_all.py           # Example API automation script
|- requirements.txt
|- README.md
```

## Setup and Installation

### 1) Clone repository

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
```

### 2) Create virtual environment

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3) Install dependencies

```bash
pip install -r requirements.txt
```

### 4) Configure environment variables

Create `.env` in `edu/` or project root.

### 5) Apply migrations and load base subjects

```bash
cd edu
python manage.py migrate
python manage.py loaddata courses/fixtures/subjects.json
```

### 6) Create superuser

```bash
python manage.py createsuperuser
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Django secret key. |
| `DEBUG` | Yes | `True` for local development, `False` for production. |
| `ALLOWED_HOSTS` | Yes | Comma-separated host list. |
| `DATABASE_URL` | Yes | Database DSN parsed by `dj-database-url`. |
| `REDIS_URL` | Recommended | Redis connection URL for cache and channels. |
| `API1_KEY` | Optional | Gemini API key (primary). |
| `API2_KEY` | Optional | Gemini API key fallback #2. |
| `API3_KEY` | Optional | Gemini API key fallback #3. |
| `API4_KEY` | Optional | Gemini API key fallback #4. |
| `DJANGO_SUPERUSER_USERNAME` | Optional | Used by custom `create_superuser` command. |
| `DJANGO_SUPERUSER_EMAIL` | Optional | Used by custom `create_superuser` command. |
| `DJANGO_SUPERUSER_PASSWORD` | Optional | Used by custom `create_superuser` command. |

Example `.env`:

```env
SECRET_KEY=change_me
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
DATABASE_URL=sqlite:///db.sqlite3
REDIS_URL=redis://127.0.0.1:6379/0
API1_KEY=
API2_KEY=
API3_KEY=
API4_KEY=
```

## Run the Project

Development server:

```bash
cd edu
python manage.py runserver
```

ASGI server (recommended when validating WebSocket behavior):

```bash
cd edu
daphne -b 0.0.0.0 -p 8000 edu.asgi:application
```

Open `http://127.0.0.1:8000/`.

## API Summary

Base path: `/api/`

Key endpoints:

- `GET /api/subjects/`
- `GET /api/courses/`
- `POST /api/token-auth/`
- `POST /api/courses/{id}/enroll/` (auth required)
- `GET /api/courses/{id}/contents/` (auth + enrollment required)
- `GET /api/developer/token-ui/` (session login required)

For complete request/response details and examples, see `docs/api.md`.

## Management Commands

Custom commands included:

- Create or promote superuser from environment variables:

```bash
cd edu
python manage.py create_superuser
```

- Send reminder emails to users not enrolled in any course:

```bash
cd edu
python manage.py enroll_reminder --days 7
```

## Security and Access Control

- Instructor actions are owner-scoped server-side
- Student course content is restricted to enrolled users
- API content endpoint requires both authentication and enrollment permission
- File downloads and module image serving use authenticated Django endpoints
- Markdown content is sanitized before rendering
- Token dashboard supports immediate token rotation

## Deployment Notes (Render)

- Static assets are handled with WhiteNoise
- WebSocket support is configured via ASGI (`edu/asgi.py`)
- Media files should use persistent object storage in production
  - Render's ephemeral disk can lose uploaded media on redeploy/restart
  - Recommended: S3-compatible storage or Cloudinary
- Use `DEBUG=False` with correct `ALLOWED_HOSTS`, `DATABASE_URL`, and `REDIS_URL`

## Roadmap

- Add quizzes and assignment workflows
- Add richer analytics dashboards for instructors and students
- Add notifications and deadline reminders
- Add cloud media backend integration (S3/Cloudinary)
- Expand automated test coverage

## License

This project is licensed under the terms of the `LICENSE` file in this repository.
