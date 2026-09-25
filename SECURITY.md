# Security policy

Security fixes are applied to the latest code on `main`.

Do not open a public issue for a suspected vulnerability or exposed credential.
Use GitHub's private vulnerability reporting for this repository when
available. If it is unavailable, contact the maintainer through the contact
method listed on the GitHub profile. Do not include active tokens, passwords,
or personal data in a report.

`claude-console` does not implement API-key storage. Supabase service-role keys
must never be provided to the CLI. The local session file is restricted to the
current user where the operating system supports those permissions.
