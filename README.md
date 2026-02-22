<!-- [Project Logo/Banner Placeholder] -->

# JudgeLoom
**A modern, high-performance online judge platform**

JudgeLoom is a complete rewrite of the DMOJ/VNOJ online judge platform, designed for scalability, performance, and modern developer experience. It provides a robust foundation for hosting competitive programming contests and managing a large library of problems.

## Feature Highlights
- **Contest Formats**: Native support for IOI, ICPC, AtCoder, and ECOO formats.
- **Real-time Judging**: Instant feedback via WebSocket integration using Django Channels.
- **Ratings**: Elo-based rating system with historical tracking and leaderboards.
- **REST API**: Fully documented API built with Django Ninja and OpenAPI.
- **Async Processing**: High-throughput task execution powered by Celery and Redis.
- **Plugin Architecture**: Extensible registry for custom contest formats and judge behaviors.

## Tech Stack
| Component | Technology |
| :--- | :--- |
| **Framework** | Django 5.1+ |
| **API Layer** | Django Ninja |
| **Validation** | Pydantic v2 |
| **Real-time** | Django Channels |
| **Task Queue** | Celery |
| **Broker/Cache** | Redis |
| **Database** | PostgreSQL |

## Project Structure
```text
judgeloom-core/
├── apps/           # Django applications
├── config/         # Project configuration and settings
├── core/           # Shared utilities and base classes
├── requirements/   # Dependency specifications
├── tests/          # Global test suite
└── manage.py       # Django management script
```

## Quick Start

### Prerequisites
- Python 3.12+
- PostgreSQL 16+
- Redis 7+

### Installation
1. **Clone the repository**
   ```bash
   git clone https://github.com/judgeloom/judgeloom-core.git
   cd judgeloom-core
   ```

2. **Set up virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements/base.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your database and redis credentials
   ```

5. **Initialize database**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

6. **Run the development server**
   ```bash
   python manage.py runserver
   ```

## Configuration
JudgeLoom uses `django-environ` for configuration. All essential settings are defined in `.env.example`. Copy this file to `.env` and update the values to match your local environment. Key configurations include:
- `DATABASE_URL`: PostgreSQL connection string.
- `REDIS_URL`: Redis connection for caching.
- `CELERY_BROKER_URL`: Redis connection for the task queue.
- `CHANNEL_LAYERS_URL`: Redis connection for WebSockets.

## Architecture
JudgeLoom follows a clean, maintainable architecture designed for long-term evolution:
- **Service Layer Pattern**: Business logic is encapsulated in `@staticmethod` services within the `services/` directory, keeping models and views thin.
- **Event-Driven**: Internal pub/sub mechanism for decoupled communication between apps.
- **Plugin Registry**: A centralized registry allows for easy extension of contest formats and scoring rules without modifying core code.

## Apps Overview
- **accounts**: User authentication, profiles, and permission management.
- **organizations**: Multi-tenant organization support for schools and clubs.
- **problems**: Problem management with support for multiple test case formats.
- **submissions**: Real-time code submission processing and result tracking.
- **contests**: Flexible contest management supporting various formats and rules.
- **judge**: Communication bridge between the core platform and judge servers.
- **content**: CMS for blog posts, announcements, and static pages.
- **tickets**: Integrated support ticket system for user inquiries.
- **ratings**: Elo-based rating system for competitive programming performance.
- **tags**: Hierarchical tagging system for problems and content categorization.

## Development
### Running Tests
The project uses `pytest` for testing.
```bash
pytest
```

### Linting
We use `ruff` for linting and formatting.
```bash
ruff check .
ruff format .
```

## License
This project is licensed under the [GNU Affero General Public License v3.0](https://www.gnu.org/licenses/agpl-3.0.html).

## Acknowledgments
- Inspired by the [DMOJ](https://github.com/dmoj/online-judge) open-source judge platform.
