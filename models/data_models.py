from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import json

class DataTier(Enum):
    FREEMIUM = 1
    MARKET_HOURS_PRO = 2
    SECTOR_SPECIALIST = 3
    WEEKEND_WARRIOR = 4
    DARK_POOL_INSIDER = 5
    ALGORITHMIC_TRADER = 6
    INSTITUTIONAL_ELITE = 7

@dataclass
class UserTier:
    """User tier configuration"""
    tier: DataTier
    real_time_delay: int  # seconds
    historical_cache_ttl: int  # seconds
    news_cache_ttl: int  # seconds
    rate_limit_per_minute: int
    websocket_enabled: bool
    batch_size_limit: int

@dataclass
class MarketData:
    """Market data structure for OHLCV information"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None
    transactions: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with proper datetime serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MarketData':
        """Create from dictionary with proper datetime deserialization"""
        if isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)

@dataclass
class RealTimeQuote:
    """Real-time quote structure"""
    symbol: str
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    timestamp: datetime
    
    @property
    def spread(self) -> float:
        """Calculate bid-ask spread"""
        return self.ask - self.bid
    
    @property
    def midpoint(self) -> float:
        """Calculate midpoint price"""
        return (self.bid + self.ask) / 2
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with proper datetime serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['spread'] = self.spread
        data['midpoint'] = self.midpoint
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RealTimeQuote':
        """Create from dictionary with proper datetime deserialization"""
        if isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)

@dataclass
class Trade:
    """Trade data structure"""
    symbol: str
    timestamp: datetime
    price: float
    size: int
    conditions: List[str]
    exchange: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with proper datetime serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

@dataclass
class NewsItem:
    """News item structure"""
    id: str
    title: str
    summary: str
    url: str
    published: datetime
    symbols: List[str]
    keywords: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with proper datetime serialization"""
        data = asdict(self)
        data['published'] = self.published.isoformat()
        return data

@dataclass
class WebSocketMessage:
    """WebSocket message structure"""
    type: str  # 'quote', 'trade', 'aggregate', 'status'
    symbol: str
    data: Dict[str, Any]
    timestamp: datetime
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps({
            'type': self.type,
            'symbol': self.symbol,
            'data': self.data,
            'timestamp': self.timestamp.isoformat()
        })

# Tier configurations
TIER_CONFIGS = {
    DataTier.FREEMIUM: UserTier(
        tier=DataTier.FREEMIUM,
        real_time_delay=3600,  # 1 hour delay
        historical_cache_ttl=86400,  # 24 hours
        news_cache_ttl=7200,  # 2 hours
        rate_limit_per_minute=10,
        websocket_enabled=False,
        batch_size_limit=5
    ),
    DataTier.MARKET_HOURS_PRO: UserTier(
        tier=DataTier.MARKET_HOURS_PRO,
        real_time_delay=900,  # 15 minutes delay
        historical_cache_ttl=3600,  # 1 hour
        news_cache_ttl=1800,  # 30 minutes
        rate_limit_per_minute=30,
        websocket_enabled=True,
        batch_size_limit=10
    ),
    DataTier.SECTOR_SPECIALIST: UserTier(
        tier=DataTier.SECTOR_SPECIALIST,
        real_time_delay=900,  # 15 minutes delay
        historical_cache_ttl=3600,  # 1 hour
        news_cache_ttl=1800,  # 30 minutes
        rate_limit_per_minute=50,
        websocket_enabled=True,
        batch_size_limit=25
    ),
    DataTier.WEEKEND_WARRIOR: UserTier(
        tier=DataTier.WEEKEND_WARRIOR,
        real_time_delay=300,  # 5 minutes delay
        historical_cache_ttl=1800,  # 30 minutes
        news_cache_ttl=900,  # 15 minutes
        rate_limit_per_minute=100,
        websocket_enabled=True,
        batch_size_limit=50
    ),
    DataTier.DARK_POOL_INSIDER: UserTier(
        tier=DataTier.DARK_POOL_INSIDER,
        real_time_delay=300,  # 5 minutes delay
        historical_cache_ttl=1800,  # 30 minutes
        news_cache_ttl=900,  # 15 minutes
        rate_limit_per_minute=200,
        websocket_enabled=True,
        batch_size_limit=100
    ),
    DataTier.ALGORITHMIC_TRADER: UserTier(
        tier=DataTier.ALGORITHMIC_TRADER,
        real_time_delay=60,  # 1 minute delay
        historical_cache_ttl=300,  # 5 minutes
        news_cache_ttl=300,  # 5 minutes
        rate_limit_per_minute=500,
        websocket_enabled=True,
        batch_size_limit=200
    ),
    DataTier.INSTITUTIONAL_ELITE: UserTier(
        tier=DataTier.INSTITUTIONAL_ELITE,
        real_time_delay=30,  # 30 seconds delay
        historical_cache_ttl=300,  # 5 minutes
        news_cache_ttl=300,  # 5 minutes
        rate_limit_per_minute=1000,
        websocket_enabled=True,
        batch_size_limit=500
    )
}

def get_tier_config(tier: DataTier) -> UserTier:
    """Get configuration for a specific tier"""
    return TIER_CONFIGS.get(tier, TIER_CONFIGS[DataTier.FREEMIUM])
