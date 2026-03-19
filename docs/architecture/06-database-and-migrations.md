# Database & Migrations

← [Backend Architecture](./02-backend-architecture.md)  
→ Related: [Session Domain](./modules/session-domain.md)

---

## Purpose

This system uses a relational database (PostgreSQL) with version-controlled schema evolution.

The goal is to:

- store structured session and user data
- evolve schema safely over time
- keep DB changes reproducible and trackable

---

## Stack

- PostgreSQL → actual database
- SQLAlchemy → Python schema + connection layer
- Alembic → migration/version control system

---

## Concepts

### SQLAlchemy (schema + connection)

SQLAlchemy is used for:

1. **Defining table structure in Python**
2. **Managing DB connections**

Example:

```python
class SessionRecord(Base):
    __tablename__ = "sessions"

    id = ...
    name = ...
```

This defines the database table structure.

→ Used by: [Session Domain](./modules/session-domain.md)

---

### Alembic (schema evolution)

Alembic tracks how the database changes over time.

It works by creating **migration files**:

```
migrations/versions/
  create_sessions_table.py
```

Each file represents a change:

- create table
- add column
- modify schema

---

### Migrations

A migration is a Python file with:

```python
def upgrade():
    # apply change

def downgrade():
    # rollback change
```

---

## Current State (Week 1)

- PostgreSQL connection working
- SQLAlchemy engine configured
- Base model defined
- One table (`sessions`) defined
- Alembic initialized
- First migration created

---

## Workflow

### 1. Change model

Edit SQLAlchemy model:

```python
SessionRecord
```

---

### 2. Generate migration

```bash
alembic revision --autogenerate -m "change description"
```

---

### 3. Review migration file

Check:

- correct changes
- no unintended drops

---

### 4. Apply migration

```bash
alembic upgrade head
```

---

## Data Flow

See: [Data Flow](./04-data-flow.md)

DB interaction happens here:

Client  
→ API  
→ Application Service  
→ Repository  
→ Database  
→ Response

---

## Why this approach is good

### 1. Safe evolution
Schema changes are versioned and reversible

### 2. Reproducibility
Any environment can recreate DB state

### 3. Separation of concerns
DB structure is isolated in infrastructure layer

### 4. Future scalability
Supports large schema growth without chaos

---

## Future

### More tables

- users → [Identity Auth](./modules/identity-auth.md)
- laps → [Session Domain](./modules/session-domain.md)
- ingestion_runs → [Ingestion](./modules/ingestion.md)
- normalized_sessions → [Normalization](./modules/normalization.md)
- metrics → [Feature Metrics](./modules/feature-metrics.md)

### Advanced features

- indexing
- partitioning (for telemetry scale)
- analytics queries

---

## Key Rule

> Always change models → generate migration → apply migration  
> Never manually edit production DB schema.
