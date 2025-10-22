# API Server Scripts

Scripts for starting and managing the AutoTrader API server.

## Available Scripts

### start_api.py
Starts the AutoTrader Dashboard API server.

**Usage:**
```bash
python scripts/api/start_api.py
```

**Description:**
- Starts FastAPI server on http://127.0.0.1:8001
- Provides API documentation at http://127.0.0.1:8001/docs
- Health check endpoint: http://127.0.0.1:8001/health
- Token list endpoint: http://127.0.0.1:8001/api/tokens

**Features:**
- RESTful API for scanner results
- Real-time token data
- Health monitoring
- Interactive API documentation (Swagger UI)

**When to Use:**
- Running the dashboard web interface
- API development and testing
- Integration with external systems
- Monitoring scanner operations

### simple_api.py
Compatibility shim for legacy imports.

**Description:**
- Re-exports the FastAPI app from `src.api.main`
- Maintains backwards compatibility with older scripts
- Use `start_api.py` for actually running the server

## API Endpoints

### Health Check
```bash
curl http://127.0.0.1:8001/health
```

### Get All Tokens
```bash
curl http://127.0.0.1:8001/api/tokens
```

### Get Specific Token
```bash
curl http://127.0.0.1:8001/api/tokens/PEPE
```

## Configuration

The API server uses settings from:
- Environment variables (`.env` file)
- Configuration files in `configs/`
- Default values defined in `src/api/main.py`

## Development

For API development:
1. Start the server with `python scripts/api/start_api.py`
2. Visit http://127.0.0.1:8001/docs for interactive documentation
3. Make changes to `src/api/` modules
4. Server auto-reloads on code changes (in development mode)

## Production Deployment

For production:
- Use a production WSGI server (e.g., gunicorn, uvicorn with workers)
- Set appropriate environment variables for production
- Configure reverse proxy (nginx/Apache) for HTTPS
- See `docs/OPERATIONS_RUNBOOKS.md` for detailed deployment guide

## Troubleshooting

If the API fails to start:
1. Check port 8001 is not already in use
2. Verify all dependencies are installed
3. Check logs for specific error messages
4. Ensure database migrations are up to date
5. See `docs/API_DOCUMENTATION.md` for detailed API information
