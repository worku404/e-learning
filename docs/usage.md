# Gold-EDU Client Usage Guide

This guide is for end users and external clients consuming the deployed Gold-EDU product on Render.



## Production URL

- Main app: `https://e-learning-aae0.onrender.com`
- API root: `https://e-learning-aae0.onrender.com/api/`
- API docs: `https://e-learning-aae0.onrender.com/api/developer/token-ui/` (login required)

## Who This Guide Is For

- Students learning through the web UI
- Instructors publishing and managing course content
- External developers integrating with the API

## 1) Student Usage (Web App)

### Account and Login

1. Open `https://e-learning-aae0.onrender.com`
2. Click `Sign in` (or register first from student registration flow or `https://e-learning-aae0.onrender.com/students/register/`)


![Account and Login](./images/create_account.png)


3. After login, go to `My Courses`


![Account and Login](./images/logged_in.png)


### Enroll in a Course

1. Go to Dashboard page (`/`), open any course card
2. Click `Enroll now`
3. You are redirected to your learning workspace


![Enrollment Flow](./images/open_course_view.png)

![Enrollment Flow](./images/enroll_now.png)


### Learning Workspace

Inside `/students/course/<course_id>/`:

- Left panel: module navigation + total time spent
- Main panel: module contents
- Available content types:
  - Markdown text lessons
  - Embedded videos
  - Images
  - File resources (PDF preview + download)

![Learning Workspace Placeholder](./images/content-preview.png)


![Learning Workspace Placeholder](./images/course_preview_1.png)



### PDF and File Usage

- PDFs can open inline in the course page (iframe preview)
- `Download PDF` triggers file download
- `Open PDF in new tab` opens the same file endpoint in a separate tab

![PDF Usage Placeholder](./images/pdf-preview.png)



### Course Chat

- From course detail page, click `Course chat room`
- Real-time chat uses WebSocket and is scoped per course
- Previous messages are persisted and loaded with history pagination

![Course Chat Placeholder](./images/chat-preview.png)



### AI Assistant

- The AI sidebar is available to authenticated users
- Ask course-related questions from within the workspace
- Session keeps short conversation history for context

![AI Assistant Placeholder](./images/placeholder-ai-assistant.png)

AI Assistance may not work in Firefox.

## 2) Instructor Usage (Web App)

Instructor entry points are under `/course/`.

### Manage Courses

- `GET /course/mine/` -> list owned courses
- `GET /course/create/` -> create new course
- `GET /course/<pk>/edit/` -> edit course
- `GET /course/<pk>/delete/` -> delete course


![Instructor Course Management Placeholder](./images/course-create.png)


### Manage Modules

- `GET /course/<pk>/module/` -> edit module formset
- Add, remove, and reorder modules

![Instructor Module Management Placeholder](./images/placeholder-instructor-modules.png)


### Manage Content

- `GET /course/module/<module_id>/` -> module content list
- Add/update content types:
  - `text`
  - `video`
  - `image`
  - `file`

![Instructor Content Management Placeholder](./images/placeholder-instructor-content.png)


### Ordering

- Drag-and-drop ordering is enabled for:
  - Module order
  - Content order within a module

![Drag and Drop Ordering Placeholder](./images/placeholder-ordering.png)

![Drag and Drop Ordering Placeholder](./images/placeholder-ordering2.png)


## 3) API Client Usage (Production)

Use this when building mobile apps, SPAs, scripts, or integrations.

### Base URL

- `https://e-learning-aae0.onrender.com/api/`

### Public Endpoints

- `GET /api/subjects/`
- `GET /api/courses/`
- `GET /api/courses/{id}/`

### Authenticated Endpoints

- `POST /api/token-auth/` -> get token
- `POST /api/courses/{id}/enroll/` -> enroll authenticated user
- `GET /api/courses/{id}/contents/` -> requires enrolled user

![API Token Dashboard Placeholder](./images/placeholder-api-token-ui.png)


### Example: Get Token (Production)

```bash
curl -X POST https://e-learning-aae0.onrender.com/api/token-auth/ \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"your_username\",\"password\":\"your_password\"}"
```

### Example: Access Protected Content

```bash
curl https://e-learning-aae0.onrender.com/api/courses/1/contents/ \
  -H "Authorization: Token your_generated_token_value"
```

### API Integration Notes

- Pagination is enabled on list endpoints (`page`, `page_size`)
- Respect `401` and `403` responses (auth/enrollment issues)
- For full endpoint details, use `docs/api.md`

## 4) Client Troubleshooting

### Cannot access course content

- Confirm the user is enrolled in the target course
- Confirm session/token is valid

### 401 Unauthorized (API)

- Missing or invalid `Authorization: Token <token>`
- Regenerate token via `/api/token-auth/` or token UI page

### 403 Forbidden on `/contents/`

- User is authenticated but not enrolled in that course

### PDF does not render inline

- Use `Open PDF in new tab` fallback
- Confirm the uploaded file exists in storage
- On platforms with ephemeral disk, old uploads can disappear after restart/redeploy

![Troubleshooting Placeholder](./images/placeholder-troubleshooting.png)


## 5) Recommended Client Onboarding Flow

For fastest adoption in production:

1. Open homepage and browse catalog
2. Register and sign in
3. Enroll in one course
4. Complete one module with text/video/file content
5. Join course chat
6. Test API token generation from `/api/developer/token-ui/`

This confirms both UI and API consumption paths are working end-to-end.
