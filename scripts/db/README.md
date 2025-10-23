# Database Initialization Scripts

This directory contains scripts for initializing development databases.

## Quick Start

To initialize all development databases with empty schemas:

```bash
python scripts/db/init_dev_databases.py
```

This will create:
- `bouncehunter_memory.db` - Agent memory for trading signals
- `test_memory.db` - Test database with same structure
- `experiments.sqlite` - Experiment tracking database

## Important Notes

⚠️ **Database files are NOT committed to git**

All `*.db` and `*.sqlite` files are excluded from version control via `.gitignore`. This prevents:
- Repository bloat from growing database files
- Merge conflicts from binary files
- Accidental data leaks in version history

## Database Schemas

### bouncehunter_memory.db / test_memory.db

Tables:
- `signals` - Trading signal records
- `fills` - Executed trade fills
- `outcomes` - Trade outcomes and performance
- `ticker_stats` - Per-ticker performance statistics
- `system_state` - System configuration state

Schema source: `src/bouncehunter/agentic.py:AgentMemory._init_schema()`

### experiments.sqlite

Tables:
- `experiments` - Experiment configurations
- `experiment_tags` - Tags for categorizing experiments

Schema source: `src/utils/experiment_tracker.py:ExperimentRegistry._init_db()`

## Database Migrations

Schema changes should be managed via Alembic migrations in the `migrations/` directory.

To create a new migration:
```bash
alembic revision --autogenerate -m "Description of change"
```

To apply migrations:
```bash
alembic upgrade head
```

## Running Tests

To test the database initialization:
```bash
python -m pytest tests/test_db_initialization.py -v
```

## Troubleshooting

**Database already exists error**: The initialization script uses `CREATE TABLE IF NOT EXISTS`, so it's safe to run multiple times. Existing data will be preserved.

**Permission errors**: Ensure you have write permissions in the repository root directory.

**Schema mismatch**: If you encounter schema errors after pulling updates, the safest approach is:
1. Backup your database: `cp bouncehunter_memory.db bouncehunter_memory.db.backup`
2. Run Alembic migrations: `alembic upgrade head`
3. Or reinitialize: `rm *.db *.sqlite && python scripts/db/init_dev_databases.py`
