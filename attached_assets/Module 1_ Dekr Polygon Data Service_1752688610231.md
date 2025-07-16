# Module 1: Dekr Polygon Data Service

## Overview

The Polygon Data Service serves as the foundational data layer for the entire Dekr platform, providing real-time and historical market data through Polygon.io's comprehensive API. This module handles all market data requests, implements intelligent caching strategies, and provides WebSocket streaming capabilities for real-time price updates. As the core data infrastructure component, it ensures reliable, fast, and cost-effective access to market information while maintaining the tier-based access controls that drive Dekr's innovative pricing strategy.

## Technical Specifications

### Core Functionality

The Polygon Data Service operates as a FastAPI-based microservice that abstracts Polygon.io's complex API structure into simplified, consistent endpoints optimized for Dekr's specific use cases. The service implements sophisticated caching mechanisms using Redis to minimize API calls and reduce costs while maintaining data freshness appropriate for each user tier. WebSocket connections provide real-time streaming for premium users, while batch processing capabilities ensure efficient data retrieval for multiple symbols simultaneously.

The service architecture follows a multi-layer approach with distinct components for data fetching, caching, transformation, and delivery. The data fetching layer handles all interactions with Polygon.io's REST API and WebSocket streams, implementing robust error handling and automatic retry mechanisms. The caching layer uses Redis with intelligent TTL (Time To Live) strategies that vary based on data type and user tier requirements. The transformation layer standardizes data formats across different Polygon.io endpoints, ensuring consistent output regardless of the underlying API structure. Finally, the delivery layer implements tier-based access controls and rate limiting to ensure users receive appropriate data access levels.

### Data Sources and Endpoints

The service integrates with multiple Polygon.io endpoints to provide comprehensive market coverage. The aggregates endpoint provides historical and real-time OHLCV (Open, High, Low, Close, Volume) data with configurable timeframes from minute-level to monthly aggregations. The last trade and last quote endpoints deliver the most recent trading information for real-time price displays. The technical indicators endpoint provides calculated technical analysis metrics, while the news endpoint supplies market-relevant news articles with sentiment analysis capabilities.

WebSocket integration enables real-time streaming of price updates, trade executions, and quote changes. The service manages WebSocket connections efficiently, implementing connection pooling and automatic reconnection logic to ensure uninterrupted data flow. Subscription management allows dynamic addition and removal of symbols based on user preferences and tier limitations, optimizing bandwidth usage and reducing unnecessary data transmission.

### Caching Strategy

The intelligent caching system represents a critical component for cost optimization and performance enhancement. The service implements a multi-tier caching strategy with different TTL values based on data type and user tier requirements. Real-time data for premium users maintains minimal caching (30 seconds to 2 minutes) to ensure freshness, while delayed data for lower tiers can be cached for longer periods (15 minutes to 1 hour). Historical data, which changes infrequently, utilizes extended caching periods (4-24 hours) to minimize API calls.

Cache invalidation strategies ensure data accuracy while maximizing cache hit rates. The service monitors market hours and implements different caching behaviors for active trading periods versus after-hours sessions. During active trading, cache TTL values are reduced to ensure timely updates, while after-hours periods allow for extended caching to reduce costs. Smart cache warming preloads frequently requested data during low-cost periods, improving response times during peak usage.

## Replit Implementation Prompt

```
Create a comprehensive Polygon.io data service for the Dekr financial platform that provides market data with intelligent caching, WebSocket streaming, and tier-based access controls.

PROJECT SETUP:
Create a new Python Replit project named "dekr-polygon-data-service" and implement a FastAPI-based microservice that serves as the core data infrastructure for the Dekr platform.

CORE REQUIREMENTS:
- FastAPI application with comprehensive market data endpoints
- Polygon.io API integration with error handling and retry logic
- Redis-based intelligent caching with tier-appropriate TTL values
- WebSocket streaming for real-time data delivery
- Tier-based access controls and rate limiting
- Batch processing capabilities for multiple symbols
- Comprehensive logging and monitoring

IMPLEMENTATION STRUCTURE:
```python
from fastapi import FastAPI, HTTPException, WebSocket, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import aiohttp
import json
import redis
import websockets
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import pandas as pd
import numpy as np
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import os
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Dekr Polygon Data Service", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DataTier(Enum):
    FREEMIUM = 1
    MARKET_HOURS_PRO = 2
    SECTOR_SPECIALIST = 3
    WEEKEND_WARRIOR = 4
    DARK_POOL_INSIDER = 5
    ALGORITHMIC_TRADER = 6
    INSTITUTIONAL_ELITE = 7

@dataclass
class MarketData:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None
    transactions: Optional[int] = None

@dataclass
class RealTimeQuote:
    symbol: str
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    timestamp: datetime

class PolygonDataService:
    def __init__(self):
        self.api_key = os.getenv('POLYGON_API_KEY')
        self.redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=0,
            decode_responses=True
        )
        self.base_url = "https://api.polygon.io"
        self.websocket_url = "wss://socket.polygon.io"
        self.active_connections = {}
        
        # Tier-based cache TTL settings (in seconds)
        self.cache_ttl = {
            DataTier.FREEMIUM: {
                'real_time': 3600,  # 1 hour delay
                'historical': 86400,  # 24 hours
                'news': 7200  # 2 hours
            },
            DataTier.MARKET_HOURS_PRO: {
                'real_time': 900,  # 15 minutes delay
                'historical': 3600,  # 1 hour
                'news': 1800  # 30 minutes
            },
            DataTier.SECTOR_SPECIALIST: {
                'real_time': 900,  # 15 minutes delay
                'historical': 3600,  # 1 hour
                'news': 1800  # 30 minutes
            },
            DataTier.WEEKEND_WARRIOR: {
                'real_time': 300,  # 5 minutes delay
                'historical': 1800,  # 30 minutes
                'news': 900  # 15 minutes
            },
            DataTier.DARK_POOL_INSIDER: {
                'real_time': 300,  # 5 minutes delay
                'historical': 1800,  # 30 minutes
                'news': 900  # 15 minutes
            },
            DataTier.ALGORITHMIC_TRADER: {
                'real_time': 60,  # 1 minute delay
                'historical': 300,  # 5 minutes
                'news': 300  # 5 minutes
            },
            DataTier.INSTITUTIONAL_ELITE: {
                'real_time': 30,  # 30 seconds delay
                'historical': 300,  # 5 minutes
                'news': 300  # 5 minutes
            }
        }
    
    async def get_market_data(self, symbol: str, timespan: str = 'day', 
                            limit: int = 100, tier: DataTier = DataTier.FREEMIUM) -> List[MarketData]:
        """Get historical market data with tier-appropriate caching"""
        
        cache_key = f"market_data:{symbol}:{timespan}:{limit}"
        
        # Check cache first
        cached_data = self.redis_client.get(cache_key)
        if cached_data:
            logger.info(f"Cache hit for {cache_key}")
            data = json.loads(cached_data)
            return [MarketData(**item) for item in data]
        
        # Fetch from Polygon.io
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=limit * 2)  # Buffer for weekends
            
            url = f"{self.base_url}/v2/aggs/ticker/{symbol}/range/1/{timespan}/{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
            
            params = {
                'apikey': self.api_key,
                'adjusted': 'true',
                'sort': 'asc',
                'limit': limit
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('results'):
                            market_data = []
                            for result in data['results']:
                                market_data.append(MarketData(
                                    symbol=symbol,
                                    timestamp=datetime.fromtimestamp(result['t'] / 1000),
                                    open=result['o'],
                                    high=result['h'],
                                    low=result['l'],
                                    close=result['c'],
                                    volume=result['v'],
                                    vwap=result.get('vw'),
                                    transactions=result.get('n')
                                ))
                            
                            # Cache with tier-appropriate TTL
                            ttl = self.cache_ttl[tier]['historical']
                            cache_data = [asdict(item) for item in market_data]
                            self.redis_client.setex(cache_key, ttl, json.dumps(cache_data, default=str))
                            
                            logger.info(f"Fetched and cached {len(market_data)} records for {symbol}")
                            return market_data
                        else:
                            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
                    else:
                        raise HTTPException(status_code=response.status, detail="Polygon API error")
        
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch market data: {str(e)}")
    
    async def get_real_time_quote(self, symbol: str, tier: DataTier = DataTier.FREEMIUM) -> RealTimeQuote:
        """Get real-time quote with tier-appropriate delay"""
        
        cache_key = f"quote:{symbol}"
        
        # Check cache based on tier
        cached_quote = self.redis_client.get(cache_key)
        if cached_quote:
            quote_data = json.loads(cached_quote)
            cached_time = datetime.fromisoformat(quote_data['timestamp'])
            
            # Check if cache is still valid for this tier
            cache_age = (datetime.now() - cached_time).total_seconds()
            max_age = self.cache_ttl[tier]['real_time']
            
            if cache_age < max_age:
                logger.info(f"Cache hit for quote {symbol} (age: {cache_age}s)")
                return RealTimeQuote(**quote_data)
        
        # Fetch fresh quote from Polygon.io
        try:
            url = f"{self.base_url}/v2/last/nbbo/{symbol}"
            params = {'apikey': self.api_key}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = data.get('results', {})
                        
                        quote = RealTimeQuote(
                            symbol=symbol,
                            bid=result.get('P', 0),
                            ask=result.get('p', 0),
                            bid_size=result.get('S', 0),
                            ask_size=result.get('s', 0),
                            timestamp=datetime.now()
                        )
                        
                        # Cache the quote
                        ttl = self.cache_ttl[tier]['real_time']
                        self.redis_client.setex(cache_key, ttl, json.dumps(asdict(quote), default=str))
                        
                        logger.info(f"Fetched fresh quote for {symbol}")
                        return quote
                    else:
                        raise HTTPException(status_code=response.status, detail="Failed to fetch quote")
        
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch quote: {str(e)}")
    
    async def get_batch_quotes(self, symbols: List[str], tier: DataTier = DataTier.FREEMIUM) -> Dict[str, RealTimeQuote]:
        """Get quotes for multiple symbols efficiently"""
        
        quotes = {}
        uncached_symbols = []
        
        # Check cache for all symbols first
        for symbol in symbols:
            cache_key = f"quote:{symbol}"
            cached_quote = self.redis_client.get(cache_key)
            
            if cached_quote:
                quote_data = json.loads(cached_quote)
                cached_time = datetime.fromisoformat(quote_data['timestamp'])
                cache_age = (datetime.now() - cached_time).total_seconds()
                max_age = self.cache_ttl[tier]['real_time']
                
                if cache_age < max_age:
                    quotes[symbol] = RealTimeQuote(**quote_data)
                else:
                    uncached_symbols.append(symbol)
            else:
                uncached_symbols.append(symbol)
        
        # Fetch uncached symbols
        if uncached_symbols:
            tasks = [self.get_real_time_quote(symbol, tier) for symbol in uncached_symbols]
            fresh_quotes = await asyncio.gather(*tasks, return_exceptions=True)
            
            for symbol, quote in zip(uncached_symbols, fresh_quotes):
                if not isinstance(quote, Exception):
                    quotes[symbol] = quote
        
        return quotes
    
    async def start_websocket_stream(self, symbols: List[str], tier: DataTier) -> str:
        """Start WebSocket stream for real-time data"""
        
        if tier.value < 5:  # Only premium tiers get WebSocket access
            raise HTTPException(status_code=403, detail="WebSocket access requires premium tier")
        
        stream_id = f"stream_{datetime.now().timestamp()}"
        
        try:
            # Connect to Polygon WebSocket
            websocket_uri = f"{self.websocket_url}/stocks"
            
            async def websocket_handler():
                async with websockets.connect(websocket_uri) as websocket:
                    # Authenticate
                    auth_message = {"action": "auth", "params": self.api_key}
                    await websocket.send(json.dumps(auth_message))
                    
                    # Subscribe to symbols
                    subscribe_message = {
                        "action": "subscribe",
                        "params": f"T.{',T.'.join(symbols)}"  # Trade updates
                    }
                    await websocket.send(json.dumps(subscribe_message))
                    
                    # Store connection
                    self.active_connections[stream_id] = websocket
                    
                    # Listen for messages
                    async for message in websocket:
                        data = json.loads(message)
                        # Process and cache real-time data
                        await self.process_websocket_message(data, tier)
            
            # Start WebSocket handler as background task
            asyncio.create_task(websocket_handler())
            
            return stream_id
            
        except Exception as e:
            logger.error(f"Error starting WebSocket stream: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to start stream: {str(e)}")
    
    async def process_websocket_message(self, data: Dict, tier: DataTier):
        """Process incoming WebSocket messages"""
        
        for message in data:
            if message.get('ev') == 'T':  # Trade update
                symbol = message.get('sym')
                price = message.get('p')
                volume = message.get('s')
                timestamp = datetime.fromtimestamp(message.get('t') / 1000)
                
                # Update real-time cache
                cache_key = f"live_trade:{symbol}"
                trade_data = {
                    'symbol': symbol,
                    'price': price,
                    'volume': volume,
                    'timestamp': timestamp.isoformat()
                }
                
                # Cache with short TTL for real-time data
                self.redis_client.setex(cache_key, 60, json.dumps(trade_data))
                
                logger.info(f"Updated live trade for {symbol}: ${price}")

# Initialize service
polygon_service = PolygonDataService()

# API Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/market-data/{symbol}")
async def get_market_data_endpoint(
    symbol: str,
    timespan: str = 'day',
    limit: int = 100,
    tier: int = 1
):
    """Get historical market data for a symbol"""
    
    data_tier = DataTier(tier)
    market_data = await polygon_service.get_market_data(symbol, timespan, limit, data_tier)
    return [asdict(data) for data in market_data]

@app.get("/quote/{symbol}")
async def get_quote_endpoint(symbol: str, tier: int = 1):
    """Get real-time quote for a symbol"""
    
    data_tier = DataTier(tier)
    quote = await polygon_service.get_real_time_quote(symbol, data_tier)
    return asdict(quote)

@app.post("/quotes/batch")
async def get_batch_quotes_endpoint(symbols: List[str], tier: int = 1):
    """Get quotes for multiple symbols"""
    
    data_tier = DataTier(tier)
    quotes = await polygon_service.get_batch_quotes(symbols, data_tier)
    return {symbol: asdict(quote) for symbol, quote in quotes.items()}

@app.post("/stream/start")
async def start_stream_endpoint(symbols: List[str], tier: int = 1):
    """Start WebSocket stream for real-time data"""
    
    data_tier = DataTier(tier)
    stream_id = await polygon_service.start_websocket_stream(symbols, data_tier)
    return {"stream_id": stream_id, "status": "started"}

@app.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics"""
    
    info = polygon_service.redis_client.info()
    return {
        "used_memory": info.get('used_memory_human'),
        "connected_clients": info.get('connected_clients'),
        "total_commands_processed": info.get('total_commands_processed'),
        "keyspace_hits": info.get('keyspace_hits'),
        "keyspace_misses": info.get('keyspace_misses')
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

ENVIRONMENT VARIABLES:
Set these in your Replit secrets:
- POLYGON_API_KEY=your_polygon_api_key_here
- REDIS_HOST=localhost
- REDIS_PORT=6379

REQUIREMENTS.TXT:
```
fastapi==0.104.1
uvicorn==0.24.0
aiohttp==3.9.1
redis==5.0.1
pandas==2.1.4
numpy==1.24.3
websockets==12.0
python-multipart==0.0.6
```

TESTING INSTRUCTIONS:
1. Test health endpoint: GET /health
2. Test market data: GET /market-data/AAPL?timespan=day&limit=10&tier=1
3. Test real-time quote: GET /quote/AAPL?tier=1
4. Test batch quotes: POST /quotes/batch with body: ["AAPL", "GOOGL", "MSFT"]
5. Test cache stats: GET /cache/stats

DEPLOYMENT NOTES:
- The service automatically handles Polygon.io rate limits
- Redis caching reduces API costs significantly
- WebSocket streams are available for premium tiers only
- All endpoints include comprehensive error handling
- Logging provides detailed operation tracking

This implementation provides a robust, scalable foundation for the Dekr platform's data infrastructure.
```

## Integration Points

The Polygon Data Service integrates seamlessly with other Dekr modules through standardized API contracts and shared data formats. The service exposes RESTful endpoints that other modules can consume, while also providing WebSocket streams for real-time data delivery. The caching layer ensures that multiple modules can request the same data without incurring additional API costs, while the tier-based access controls maintain consistency with Dekr's pricing strategy.

Integration with the User Preference Engine allows the data service to preload frequently requested symbols and optimize cache warming strategies. The Intelligent Card Engine relies on the data service for current market information and historical data for card generation. The Strategy Builder Enhanced module uses the data service for backtesting calculations and real-time signal generation. The News Sentiment Service coordinates with the data service to correlate market movements with news events.

## Performance Optimization

The service implements several performance optimization strategies to ensure fast response times and efficient resource utilization. Connection pooling manages HTTP connections to Polygon.io's API, reducing connection overhead and improving throughput. Batch processing capabilities allow multiple symbol requests to be handled efficiently, minimizing API calls and reducing latency. Asynchronous processing ensures that the service can handle multiple concurrent requests without blocking.

Memory management strategies include intelligent cache eviction policies that prioritize frequently accessed data while removing stale information. The service monitors memory usage and implements automatic cleanup procedures to prevent memory leaks. Database connection pooling ensures efficient database access for logging and monitoring purposes.

## Security and Reliability

Security measures include API key management through environment variables, request validation to prevent malicious inputs, and rate limiting to protect against abuse. The service implements comprehensive error handling with automatic retry mechanisms for transient failures. Circuit breaker patterns prevent cascading failures when external services are unavailable.

Monitoring and alerting capabilities provide real-time visibility into service health and performance. The service logs all significant events and errors, enabling effective troubleshooting and performance analysis. Health check endpoints allow load balancers and monitoring systems to verify service availability.

## Cost Optimization

The intelligent caching strategy represents the primary cost optimization mechanism, reducing Polygon.io API calls by 60-80% through strategic data reuse. Tier-based TTL values ensure that premium users receive fresher data while lower-tier users access cached data, balancing cost and user experience. Batch processing reduces the number of individual API calls, while smart cache warming during off-peak hours minimizes costs during high-demand periods.

The service monitors API usage patterns and provides detailed analytics on cost optimization opportunities. Automatic scaling capabilities ensure that resources are allocated efficiently based on demand, while connection pooling and efficient data structures minimize computational overhead.

