# Identity Auth

Back to [Backend Architecture](../architecture/02-backend-architecture.md)

## Purpose

The identity-auth module owns basic user authentication.

Current responsibilities:

- sign up a user
- log in a user
- return a lightweight auth-session view from a bearer token

## Current Storage

The module currently persists:

- `users`

Each user stores:

- `id`
- `email`
- `password_hash`

## Current API Surface

- `GET /api/auth/health`
- `POST /api/auth/signup`
- `POST /api/auth/login`
- `GET /api/auth/session`

## Current Auth Flow

1. user signs up or logs in
2. backend validates credentials
3. backend returns a bearer token
4. frontend stores the token locally
5. frontend sends the token in the `Authorization` header
6. `/api/auth/session` decodes the token and reports whether the session is authenticated

## Scope Boundaries

This module currently handles authentication, not a full account or permission system.

Not implemented yet:

- refresh tokens
- role-based authorization
- server-side session revocation
- profile management

## Why The Current Shape Is Fine

The current auth surface is small, but it is enough for:

- protected frontend flows later on
- user-specific saved behavior in the future
- realistic local development and route gating

## Future Work

- add refresh/revocation strategy if required
- introduce authorization rules once user-specific data matters
- optionally add persistent session tracking beyond stateless bearer tokens
