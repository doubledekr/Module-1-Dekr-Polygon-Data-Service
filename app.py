from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from contextlib import asynccontextmanager

from models.data_models import MarketData, RealTimeQuote, DataTier, UserTier
from services.polygon_service import PolygonDataService
from services.websocket_service import WebSocketManager
from utils.cache_manager import CacheManager
from utils.rate_limiter import RateLimiter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
polygon_service = None
websocket_manager = None
cache_manager = None
rate_limiter = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global polygon_service, websocket_manager, cache_manager, rate_limiter
    
    logger.info("Starting Dekr Polygon Data Service...")
    
    # Initialize services
    cache_manager = CacheManager()
    rate_limiter = RateLimiter()
    polygon_service = PolygonDataService(cache_manager)
    websocket_manager = WebSocketManager(polygon_service)
    
    # Start background tasks
    asyncio.create_task(cache_warming_task())
    asyncio.create_task(websocket_manager.start_polygon_websocket())
    
    logger.info("All services initialized successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down services...")
    if websocket_manager:
        await websocket_manager.disconnect_all()

app = FastAPI(
    title="Dekr Polygon Data Service",
    description="Financial data service with intelligent caching and tier-based access",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Helper function to get user tier
async def get_user_tier(tier: str = Query("freemium")) -> DataTier:
    """Get user tier from query parameter"""
    try:
        tier_mapping = {
            "freemium": DataTier.FREEMIUM,
            "market_hours_pro": DataTier.MARKET_HOURS_PRO,
            "sector_specialist": DataTier.SECTOR_SPECIALIST,
            "weekend_warrior": DataTier.WEEKEND_WARRIOR,
            "dark_pool_insider": DataTier.DARK_POOL_INSIDER,
            "algorithmic_trader": DataTier.ALGORITHMIC_TRADER,
            "institutional_elite": DataTier.INSTITUTIONAL_ELITE
        }
        return tier_mapping.get(tier.lower(), DataTier.FREEMIUM)
    except Exception:
        return DataTier.FREEMIUM

# API Endpoints
@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Dekr Polygon Data Service",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "market_data": "/api/market-data/{symbol}",
            "real_time_quote": "/api/quote/{symbol}",
            "batch_quotes": "/api/batch-quotes",
            "websocket": "/ws/{symbol}",
            "admin": "/admin"
        }
    }

@app.get("/admin", response_class=HTMLResponse)
async def admin_interface():
    """Serve admin interface"""
    with open("static/admin.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/market-data/{symbol}")
async def get_market_data(
    symbol: str,
    timespan: str = Query("day", description="Time span: minute, hour, day, week, month"),
    limit: int = Query(100, description="Number of data points to return"),
    tier: DataTier = Depends(get_user_tier)
):
    """Get historical market data for a symbol"""
    try:
        # Rate limiting check
        if not rate_limiter.is_allowed(f"market_data:{symbol}", tier):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        data = await polygon_service.get_market_data(symbol, timespan, limit, tier)
        
        return {
            "symbol": symbol,
            "timespan": timespan,
            "data": [
                {
                    "timestamp": item.timestamp.isoformat(),
                    "open": item.open,
                    "high": item.high,
                    "low": item.low,
                    "close": item.close,
                    "volume": item.volume,
                    "vwap": item.vwap,
                    "transactions": item.transactions
                }
                for item in data
            ],
            "count": len(data)
        }
    except Exception as e:
        logger.error(f"Error getting market data for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/quote/{symbol}")
async def get_real_time_quote(
    symbol: str,
    tier: DataTier = Depends(get_user_tier)
):
    """Get real-time quote for a symbol"""
    try:
        # Rate limiting check
        if not rate_limiter.is_allowed(f"quote:{symbol}", tier):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        quote = await polygon_service.get_real_time_quote(symbol, tier)
        
        return {
            "symbol": quote.symbol,
            "bid": quote.bid,
            "ask": quote.ask,
            "bid_size": quote.bid_size,
            "ask_size": quote.ask_size,
            "spread": quote.ask - quote.bid,
            "timestamp": quote.timestamp.isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting quote for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/batch-quotes")
async def get_batch_quotes(
    symbols: List[str],
    tier: DataTier = Depends(get_user_tier)
):
    """Get real-time quotes for multiple symbols"""
    try:
        # Rate limiting check
        if not rate_limiter.is_allowed(f"batch_quotes", tier):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        quotes = await polygon_service.get_batch_quotes(symbols, tier)
        
        return {
            "quotes": [
                {
                    "symbol": quote.symbol,
                    "bid": quote.bid,
                    "ask": quote.ask,
                    "bid_size": quote.bid_size,
                    "ask_size": quote.ask_size,
                    "spread": quote.ask - quote.bid,
                    "timestamp": quote.timestamp.isoformat()
                }
                for quote in quotes
            ],
            "count": len(quotes)
        }
    except Exception as e:
        logger.error(f"Error getting batch quotes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/cache/stats")
async def get_cache_stats():
    """Get cache statistics"""
    try:
        stats = cache_manager.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cache/warm")
async def warm_cache(
    symbols: List[str],
    background_tasks: BackgroundTasks
):
    """Warm cache for specific symbols"""
    try:
        background_tasks.add_task(cache_warming_for_symbols, symbols)
        return {"message": f"Cache warming initiated for {len(symbols)} symbols"}
    except Exception as e:
        logger.error(f"Error warming cache: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/{symbol}")
async def websocket_endpoint(websocket: WebSocket, symbol: str):
    """WebSocket endpoint for real-time data streaming"""
    await websocket.accept()
    
    try:
        # Add connection to manager
        await websocket_manager.connect(websocket, symbol)
        
        # Keep connection alive
        while True:
            try:
                # Receive any messages from client (heartbeat, etc.)
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                # Handle client messages if needed
                if message == "ping":
                    await websocket.send_text("pong")
                    
            except asyncio.TimeoutError:
                # Send periodic heartbeat
                await websocket.send_text(json.dumps({"type": "heartbeat", "timestamp": datetime.now().isoformat()}))
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for {symbol}")
    except Exception as e:
        logger.error(f"WebSocket error for {symbol}: {str(e)}")
    finally:
        await websocket_manager.disconnect(websocket, symbol)

# Background Tasks
async def cache_warming_task():
    """Background task to warm cache with popular symbols"""
    popular_symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "META", "NVDA", "SPY", "QQQ"]
    
    while True:
        try:
            logger.info("Starting cache warming cycle...")
            
            # Warm cache for popular symbols
            for symbol in popular_symbols:
                try:
                    # Get market data to warm cache
                    await polygon_service.get_market_data(symbol, "day", 100, DataTier.FREEMIUM)
                    await polygon_service.get_real_time_quote(symbol, DataTier.FREEMIUM)
                    
                    # Small delay to avoid overwhelming the API
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error warming cache for {symbol}: {str(e)}")
            
            logger.info("Cache warming cycle completed")
            
            # Wait 5 minutes before next cycle
            await asyncio.sleep(300)
            
        except Exception as e:
            logger.error(f"Error in cache warming task: {str(e)}")
            await asyncio.sleep(60)

async def cache_warming_for_symbols(symbols: List[str]):
    """Warm cache for specific symbols"""
    for symbol in symbols:
        try:
            await polygon_service.get_market_data(symbol, "day", 100, DataTier.FREEMIUM)
            await polygon_service.get_real_time_quote(symbol, DataTier.FREEMIUM)
            logger.info(f"Cache warmed for {symbol}")
        except Exception as e:
            logger.error(f"Error warming cache for {symbol}: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check Redis connection
        cache_status = cache_manager.health_check()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "cache": cache_status,
                "polygon_api": "connected",
                "websocket": "active"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
