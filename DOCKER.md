# Docker Deployment Guide

## Quick Start

### 1. Copy Environment File
```bash
cp .env.docker .env
# Edit .env and add your OpenRouter API key
```

### 2. Build and Run
```bash
# Build and start all services
docker-compose up --build

# Or run in background
docker-compose up --build -d
```

### 3. Access Services
- **Domain Enrichment API**: http://localhost:8000
- **SearXNG Search Engine**: http://localhost:8080
- **API Documentation**: http://localhost:8000/docs
- **Simple Lookup**: http://localhost:8000/static/lookup.html
- **CSV Upload**: http://localhost:8000/static/upload.html

## Architecture

### Services
- **domain-enrichment-api** (Port 8000): Main FastAPI application
- **searxng** (Port 8080): Self-hosted search engine
- **redis**: Caching for SearXNG

### Network
All services run on a dedicated Docker network (`domain-enrichment-network`) for secure internal communication.

## Configuration

### Environment Variables
Set in `.env` file:
```bash
OPENROUTER_API_KEY=your_api_key_here    # Required
AI_MODEL=moonshotai/kimi-k2              # Optional, defaults to Kimi K2
```

### SearXNG Configuration
- **settings.yml**: Search engine configuration optimized for business domain discovery
- **uwsgi.ini**: Performance settings for API usage (2 processes, 4 threads)

## Management Commands

### Start Services
```bash
docker-compose up -d
```

### Stop Services
```bash
docker-compose down
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f domain-enrichment-api
docker-compose logs -f searxng
```

### Restart Single Service
```bash
docker-compose restart domain-enrichment-api
```

### Rebuild After Code Changes
```bash
docker-compose up --build domain-enrichment-api
```

## Health Checks

### API Health
```bash
curl http://localhost:8000/health
```

### SearXNG Health
```bash
curl http://localhost:8080/search?q=test&format=json
```

## Performance Tuning

### SearXNG Settings
- Configured for 2 processes, 4 threads
- Redis caching enabled
- Request timeout: 10 seconds
- Optimized for API usage (no UI features)

### API Settings
- Non-root user for security
- Health checks every 30 seconds
- Graceful shutdown handling

## Troubleshooting

### Common Issues

**1. API can't connect to SearXNG**
```bash
# Check if searxng is running
docker-compose ps searxng

# Check searxng logs
docker-compose logs searxng
```

**2. Out of memory**
```bash
# Check resource usage
docker stats

# Restart with more memory
docker-compose down
docker-compose up -d
```

**3. OpenRouter API errors**
- Verify API key in `.env`
- Check API rate limits
- Monitor logs: `docker-compose logs domain-enrichment-api`

### Reset Everything
```bash
# Stop and remove all containers, networks, and volumes
docker-compose down -v --remove-orphans

# Rebuild from scratch
docker-compose up --build
```

## Production Considerations

### Security
- Change SearXNG secret key in `searxng/settings.yml`
- Use proper firewall rules
- Keep Docker images updated
- Use Docker secrets for sensitive data

### Monitoring
- Monitor API response times
- Watch SearXNG search success rates
- Track OpenRouter API usage
- Set up log aggregation

### Scaling
- Increase SearXNG processes in `uwsgi.ini`
- Add load balancer for multiple API instances
- Use external Redis for better caching
- Consider horizontal scaling with Docker Swarm/Kubernetes

## Backup and Recovery

### Data to Backup
- Environment configuration (`.env`)
- SearXNG settings (`searxng/settings.yml`)
- Any custom modifications

### Recovery
```bash
# Restore from backup
cp backup/.env .env
cp backup/searxng/settings.yml searxng/settings.yml

# Restart services
docker-compose up --build -d
```