# Setup Scripts

Configuration and token management utilities.

## Available Scripts

### set_questrade_token.py
Interactive setup for Questrade refresh token.

**Usage:**
```bash
python scripts/setup/set_questrade_token.py
```

**Description:**
- Guides you through Questrade token setup
- Validates token format
- Saves token to `configs/broker_credentials.yaml`
- Tests connection with new token

**When to Use:**
- First-time Questrade setup
- Setting up a new machine
- Switching between practice and live accounts

### update_questrade_token.py
Updates an existing Questrade token.

**Usage:**
```bash
python scripts/setup/update_questrade_token.py
```

**Description:**
- Updates existing token in credentials file
- Validates new token before saving
- Preserves other broker credentials
- Tests connection with updated token

**When to Use:**
- Token expiration (tokens typically last 6-12 months)
- Token refresh after rotation
- Fixing invalid token issues

## Token Management Best Practices

1. **Token Rotation**: Questrade tokens expire. Plan to refresh them periodically.
2. **Secure Storage**: Never commit tokens to version control. Use `.gitignore` for credentials.
3. **Environment Separation**: Use separate tokens for development vs. production.
4. **Token Validation**: Always test tokens after setup using `scripts/debug/debug_questrade.py`.

## Troubleshooting

If token setup fails:
1. Verify API access is enabled in Questrade account settings
2. Ensure you copied the complete token (no spaces or line breaks)
3. Run `python scripts/troubleshooting/diagnose_questrade.py` for detailed diagnostics
4. Check `docs/legacy/QUESTRADE_SETUP.md` for detailed setup instructions
