# Identity and account access

The identity module owns account credentials, mailbox verification, Google sign-in, and the member or administrator role. Profile preferences remain in `account_profile`, and subscription access belongs to `billing`. [Backend architecture](../architecture/02-backend-architecture.md)

## Password sign-up and verification

`POST /api/auth/signup` returns an email challenge. The pending record holds the proposed bcrypt password hash and a keyed digest of the six-digit code. The app sends the code through the configured TLS-protected SMTP transport. `POST /api/auth/verify-email` checks the code and creates a member with `email_verified_at`, then issues the PitWall bearer token. For a legacy password account with no verification timestamp, the first successful password check opens the same challenge. Future sign-ins use the verified account and password.

Codes expire in ten minutes. A challenge allows five incorrect attempts. Resends replace the previous challenge, and the database limits sends by mailbox and client. The `email_verifications` records are pruned on subsequent requests. The configuration response exposes availability only. [Local mail setup](../setup.md#email-verification)

## Google sign-in and account linking

The login and signup pages render the Google Identity Services button when a web client is configured. The backend checks the signed credential and consumes a short-lived nonce. Google `sub` identifies the linked account. An authoritative Google email claim can verify a new account. A third-party mailbox requires a PitWall code. Existing local accounts link Google from the profile with their current password. Google signing credentials and access tokens stay outside PostgreSQL. [Google ID token checks](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token)

## Session and administrator access

`GET /api/auth/session` validates the token and reads the role and verification status from `users`. The API checks that same state on protected requests. A trusted operator grants the `admin` role with the local provisioning command. Administrators sign in with their existing password and can open the diagnostics screen and module diagnostics endpoints. Public readiness routes expose basic status. [Administrator setup](../setup.md#local-administrator)

The frontend renews active sessions through `POST /api/auth/refresh`. Expired sessions require sign-in.
