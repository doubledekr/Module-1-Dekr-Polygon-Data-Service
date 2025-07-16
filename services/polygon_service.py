import aiohttp
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import os

from models.data_models import MarketData, RealTimeQuote, DataTier, Trade, NewsItem, get_tier_config
from utils.cache_manager import CacheManager

logger = logging.getLogger(__name__)

class PolygonDataService:
    """Service for interacting with Polygon.io API"""
    
    def __init__(self, cache_manager: CacheManager):
        self.api_key = os.getenv('POLYGON_API_KEY', 'demo_key')
        self.base_url = "https://api.polygon.io"
        self.cache_manager = cache_manager
        self.session = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={'Authorization': f'Bearer {self.api_key}'}
            )
        return self.session
    
    async def close_session(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_market_data(self, symbol: str, timespan: str = 'day', 
                             limit: int = 100, tier: DataTier = DataTier.FREEMIUM) -> List[MarketData]:
        """Get historical market data with tier-appropriate caching"""
        
        cache_key = f"market_data:{symbol}:{timespan}:{limit}"
        tier_config = get_tier_config(tier)
        
        # Check cache first
        cached_data = self.cache_manager.get(cache_key)
        if cached_data:
            logger.info(f"Cache hit for {cache_key}")
            return [MarketData.from_dict(item) for item in cached_data]
        
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
            
            session = await self._get_session()
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
                        ttl = tier_config.historical_cache_ttl
                        cache_data = [item.to_dict() for item in market_data]
                        self.cache_manager.set(cache_key, cache_data, ttl)
                        
                        logger.info(f"Fetched and cached {len(market_data)} records for {symbol}")
                        return market_data
                    else:
                        logger.warning(f"No data found for {symbol}")
                        return []
                else:
                    logger.error(f"Polygon API error {response.status} for {symbol}")
                    raise Exception(f"Polygon API error: {response.status}")
        
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {str(e)}")
            raise Exception(f"Failed to fetch market data: {str(e)}")
    
    async def get_real_time_quote(self, symbol: str, tier: DataTier = DataTier.FREEMIUM) -> RealTimeQuote:
        """Get real-time quote with tier-appropriate delay"""
        
        cache_key = f"quote:{symbol}"
        tier_config = get_tier_config(tier)
        
        # Check cache based on tier
        cached_quote = self.cache_manager.get(cache_key)
        if cached_quote:
            cached_time = datetime.fromisoformat(cached_quote['timestamp'])
            
            # Check if cache is still valid for this tier
            cache_age = (datetime.now() - cached_time).total_seconds()
            max_age = tier_config.real_time_delay
            
            if cache_age < max_age:
                logger.info(f"Cache hit for quote {symbol} (age: {cache_age}s)")
                return RealTimeQuote.from_dict(cached_quote)
        
        # Fetch fresh quote from Polygon.io
        try:
            url = f"{self.base_url}/v2/last/nbbo/{symbol}"
            params = {'apikey': self.api_key}
            
            session = await self._get_session()
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data.get('results', {})
                    
                    quote = RealTimeQuote(
                        symbol=symbol,
                        bid=result.get('P', 0.0),
                        ask=result.get('p', 0.0),
                        bid_size=result.get('S', 0),
                        ask_size=result.get('s', 0),
                        timestamp=datetime.now()
                    )
                    
                    # Cache the quote
                    ttl = tier_config.real_time_delay
                    self.cache_manager.set(cache_key, quote.to_dict(), ttl)
                    
                    logger.info(f"Fetched and cached quote for {symbol}")
                    return quote
                else:
                    logger.error(f"Polygon API error {response.status} for quote {symbol}")
                    raise Exception(f"Polygon API error: {response.status}")
        
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {str(e)}")
            raise Exception(f"Failed to fetch quote: {str(e)}")
    
    async def get_batch_quotes(self, symbols: List[str], tier: DataTier = DataTier.FREEMIUM) -> List[RealTimeQuote]:
        """Get real-time quotes for multiple symbols"""
        tier_config = get_tier_config(tier)
        
        # Check batch size limit
        if len(symbols) > tier_config.batch_size_limit:
            raise Exception(f"Batch size {len(symbols)} exceeds limit {tier_config.batch_size_limit} for tier {tier.name}")
        
        # Process symbols in parallel
        tasks = []
        for symbol in symbols:
            task = asyncio.create_task(self.get_real_time_quote(symbol, tier))
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = []
        for task in asyncio.as_completed(tasks):
            try:
                quote = await task
                results.append(quote)
            except Exception as e:
                logger.error(f"Error in batch quote processing: {str(e)}")
                continue
        
        return results
    
    async def get_last_trade(self, symbol: str, tier: DataTier = DataTier.FREEMIUM) -> Optional[Trade]:
        """Get last trade for a symbol"""
        cache_key = f"trade:{symbol}"
        tier_config = get_tier_config(tier)
        
        # Check cache
        cached_trade = self.cache_manager.get(cache_key)
        if cached_trade:
            cached_time = datetime.fromisoformat(cached_trade['timestamp'])
            cache_age = (datetime.now() - cached_time).total_seconds()
            
            if cache_age < tier_config.real_time_delay:
                return Trade(**cached_trade)
        
        # Fetch from API
        try:
            url = f"{self.base_url}/v2/last/trade/{symbol}"
            params = {'apikey': self.api_key}
            
            session = await self._get_session()
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data.get('results', {})
                    
                    trade = Trade(
                        symbol=symbol,
                        timestamp=datetime.fromtimestamp(result.get('t', 0) / 1000),
                        price=result.get('p', 0.0),
                        size=result.get('s', 0),
                        conditions=result.get('c', []),
                        exchange=result.get('x', '')
                    )
                    
                    # Cache the trade
                    self.cache_manager.set(cache_key, trade.to_dict(), tier_config.real_time_delay)
                    
                    return trade
                else:
                    logger.error(f"Error fetching trade for {symbol}: {response.status}")
                    return None
        
        except Exception as e:
            logger.error(f"Error fetching trade for {symbol}: {str(e)}")
            return None
    
    async def get_news(self, symbol: str = None, limit: int = 10, tier: DataTier = DataTier.FREEMIUM) -> List[NewsItem]:
        """Get news items"""
        cache_key = f"news:{symbol or 'all'}:{limit}"
        tier_config = get_tier_config(tier)
        
        # Check cache
        cached_news = self.cache_manager.get(cache_key)
        if cached_news:
            return [NewsItem(**item) for item in cached_news]
        
        # Fetch from API
        try:
            url = f"{self.base_url}/v2/reference/news"
            params = {
                'apikey': self.api_key,
                'limit': limit
            }
            
            if symbol:
                params['ticker'] = symbol
            
            session = await self._get_session()
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    results = data.get('results', [])
                    
                    news_items = []
                    for item in results:
                        news_items.append(NewsItem(
                            id=item.get('id', ''),
                            title=item.get('title', ''),
                            summary=item.get('description', ''),
                            url=item.get('article_url', ''),
                            published=datetime.fromisoformat(item.get('published_utc', '').replace('Z', '+00:00')),
                            symbols=item.get('tickers', []),
                            keywords=item.get('keywords', [])
                        ))
                    
                    # Cache news items
                    cache_data = [item.to_dict() for item in news_items]
                    self.cache_manager.set(cache_key, cache_data, tier_config.news_cache_ttl)
                    
                    return news_items
                else:
                    logger.error(f"Error fetching news: {response.status}")
                    return []
        
        except Exception as e:
            logger.error(f"Error fetching news: {str(e)}")
            return []
    
    async def health_check(self) -> Dict[str, Any]:
        """Check API health"""
        try:
            url = f"{self.base_url}/v2/last/trade/AAPL"
            params = {'apikey': self.api_key}
            
            session = await self._get_session()
            async with session.get(url, params=params) as response:
                return {
                    'status': 'healthy' if response.status == 200 else 'unhealthy',
                    'response_code': response.status,
                    'timestamp': datetime.now().isoformat()
                }
        
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
