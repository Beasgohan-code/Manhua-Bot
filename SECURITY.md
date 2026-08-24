# Security Policy

## Supported Versions

The following versions of Chapter Pilot are currently being supported with security updates.

| Version | Supported          |
| ------- | ------------------ |
| v1.1.x  | :white_check_mark: |
| < v1.1  | :x:                |

## Reporting a Vulnerability

We take the security of Chapter Pilot seriously. If you believe you have found a security vulnerability, please do NOT open a public issue. Instead:

1. **Telegram**: Contact the developer directly at [@nullzair](https://t.me/nullzair).
2. **Details**: Provide a detailed description of the vulnerability, including steps to reproduce it if possible.

Once you have reported the vulnerability, we will acknowledge your report within 48 hours and work with you to resolve it. We ask that you give us reasonable time to investigate and address the issue before making any information public.

## Sensitive Information

**NEVER** share your `BOT_TOKEN`, `API_ID`, `API_HASH`, or `MONGO_DB_URI` in any public channel or issue. These credentials give full access to your bot and database.

If you have accidentally exposed these, rotate them immediately:
- **BOT_TOKEN**: Use @BotFather to revoke and generate a new token.
- **API ID/HASH**: These cannot be changed; you may need to create a new session if they are deeply compromised.
- **MONGO_DB_URI**: Update your password or generate a new connection string in your MongoDB dashboard.
