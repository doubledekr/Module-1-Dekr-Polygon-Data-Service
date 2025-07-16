# Dekr Polygon Data Service

## Overview

This is a FastAPI-based microservice that provides real-time and historical market data through Polygon.io's API. The service acts as the foundational data layer for the Dekr financial platform, offering intelligent caching, WebSocket streaming, and tier-based access controls for different user subscription levels.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

The application follows a microservice architecture with the following key characteristics:

- **FastAPI Backend**: Main API server handling HTTP requests and WebSocket connections
- **Multi-tier Data Access**: Seven different user tiers with varying levels of access and rate limits
- **Real-time Streaming**: WebSocket integration for live market data
- **Intelligent Caching**: Redis-based caching system with tier-appropriate TTL values
- **Rate Limiting**: Per-user rate limiting based on subscription tiers
- **External API Integration**: Polygon.io API for market data

## Key Components

### 1. Application Layer (`app.py`)
- FastAPI application with CORS middleware
- Global service initialization using lifespan events
- Background task management for cache warming and WebSocket connections

### 2. Data Models (`models/data_models.py`)
- **DataTier Enum**: Seven tier levels from FREEMIUM to INSTITUTIONAL_ELITE
- **UserTier**: Configuration for each tier including rate limits, cache TTL, and feature access
- **MarketData**: OHLCV data structure with serialization methods

### 3. Services Layer
- **PolygonDataService**: Handles all interactions with Polygon.io API
- **WebSocketManager**: Manages real-time WebSocket connections and streaming

### 4. Utilities
- **CacheManager**: Redis-based caching with fallback to mock cache for development
- **RateLimiter**: In-memory rate limiting with tier-based restrictions

### 5. Frontend Interface
- Admin dashboard with real-time monitoring
- Market data visualization using Chart.js
- WebSocket connection management interface

## Data Flow

1. **Request Processing**: Client requests come through FastAPI endpoints
2. **Tier Validation**: Rate limiter checks user tier and request limits
3. **Cache Check**: Cache manager looks for existing data in Redis
4. **API Call**: If cache miss, fetch from Polygon.io API
5. **Data Processing**: Transform and validate data according to tier restrictions
6. **Response**: Return data to client and cache for future requests
7. **Real-time Updates**: WebSocket connections stream live updates

## External Dependencies

### Core Dependencies
- **FastAPI**: Web framework for API endpoints
- **aiohttp**: Async HTTP client for external API calls
- **redis**: Caching layer
- **websockets**: Real-time data streaming
- **uvicorn**: ASGI server

### Third-party Services
- **Polygon.io API**: Primary data source for market information
- **Redis**: Caching and session storage

### Frontend Dependencies
- **Bootstrap**: UI framework
- **Chart.js**: Data visualization
- **Font Awesome**: Icons

## Deployment Strategy

### Development Environment
- Replit-based deployment with environment variables
- Mock Redis fallback for local development
- Static file serving for admin interface

### Production Considerations
- Redis instance required for caching
- Environment variables for API keys and configuration
- Background tasks for cache warming and WebSocket maintenance
- Rate limiting to prevent API quota exhaustion

### Key Configuration
- `POLYGON_API_KEY`: Authentication for Polygon.io API
- `REDIS_HOST` and `REDIS_PORT`: Redis connection details
- Tier-based configurations for rate limits and cache TTL values

### Performance Optimizations
- Intelligent caching with different TTL values per tier
- Connection pooling for HTTP requests
- WebSocket connection management with automatic reconnection
- Background cache warming for popular symbols

The service is designed to scale horizontally with proper load balancing and can handle multiple concurrent WebSocket connections while maintaining rate limits and caching efficiency.

## Recent Updates (July 16, 2025)

### Fixed ASGI-to-WSGI Compatibility
- Resolved "Event loop is closed" error by improving event loop handling in the ASGI-to-WSGI bridge
- Services now properly initialize for gunicorn compatibility
- Static file serving fixed (/static/styles.css and /static/admin.js)
- Admin interface fully functional with proper resource loading

### API Status
- Market data API working correctly with real Polygon.io data
- Real-time quote endpoint returning proper 403 error (expected for free tier)
- Cache system operational with hit/miss tracking
- Health check endpoint responding correctly

### Known Limitations
- Real-time quotes require paid Polygon.io subscription (free tier returns 403)
- Using MockRedis for development (data doesn't persist between restarts)
- WebSocket connections work but require premium API access for real-time data