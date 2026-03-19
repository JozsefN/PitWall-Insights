## Database interaction

The database is accessed via:

- SQLAlchemy (connection + models)
- Repositories (module-level access)

See: [Database & Migrations](./06-database-and-migrations.md)

---

## Flow with DB

Client  
→ API  
→ Application Service  
→ Repository  
→ Database  
→ Response