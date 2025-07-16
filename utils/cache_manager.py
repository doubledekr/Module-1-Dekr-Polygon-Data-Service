import redis
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional, Dict
import os

logger = logging.getLogger(__name__)

class CacheManager:
    """Redis-based cache manager with intelligent caching strategies"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=0,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        
        # Test connection
        try:
            self.redis_client.ping()
            logger.info("Redis connection established successfully")
        except Exception as e:
            logger.error(f"Redis connection failed: {str(e)}")
            # Use a mock cache for development
            self.redis_client = MockRedis()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {str(e)}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 3600):
        """Set value in cache with TTL"""
        try:
            serialized_value = json.dumps(value, default=str)
            self.redis_client.setex(key, ttl, serialized_value)
            logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {str(e)}")
    
    def delete(self, key: str):
        """Delete key from cache"""
        try:
            self.redis_client.delete(key)
            logger.debug(f"Cache deleted: {key}")
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {str(e)}")
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            return bool(self.redis_client.exists(key))
        except Exception as e:
            logger.error(f"Error checking cache key {key}: {str(e)}")
            return False
    
    def get_ttl(self, key: str) -> int:
        """Get TTL for a key"""
        try:
            return self.redis_client.ttl(key)
        except Exception as e:
            logger.error(f"Error getting TTL for key {key}: {str(e)}")
            return -1
    
    def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter"""
        try:
            return self.redis_client.incr(key, amount)
        except Exception as e:
            logger.error(f"Error incrementing key {key}: {str(e)}")
            return 0
    
    def set_with_expiry(self, key: str, value: Any, expire_at: datetime):
        """Set value with expiry at specific datetime"""
        try:
            serialized_value = json.dumps(value, default=str)
            self.redis_client.set(key, serialized_value)
            self.redis_client.expireat(key, expire_at)
            logger.debug(f"Cache set with expiry: {key} (expires at: {expire_at})")
        except Exception as e:
            logger.error(f"Error setting cache key {key} with expiry: {str(e)}")
    
    def get_keys_pattern(self, pattern: str) -> list:
        """Get keys matching pattern"""
        try:
            return self.redis_client.keys(pattern)
        except Exception as e:
            logger.error(f"Error getting keys with pattern {pattern}: {str(e)}")
            return []
    
    def flush_pattern(self, pattern: str):
        """Delete all keys matching pattern"""
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
                logger.info(f"Flushed {len(keys)} keys matching pattern: {pattern}")
        except Exception as e:
            logger.error(f"Error flushing pattern {pattern}: {str(e)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            info = self.redis_client.info()
            
            # Get key counts by pattern
            quote_keys = len(self.redis_client.keys('quote:*'))
            market_data_keys = len(self.redis_client.keys('market_data:*'))
            news_keys = len(self.redis_client.keys('news:*'))
            
            return {
                'redis_version': info.get('redis_version', 'unknown'),
                'used_memory': info.get('used_memory_human', 'unknown'),
                'connected_clients': info.get('connected_clients', 0),
                'total_commands_processed': info.get('total_commands_processed', 0),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'hit_rate': self._calculate_hit_rate(info),
                'key_counts': {
                    'quotes': quote_keys,
                    'market_data': market_data_keys,
                    'news': news_keys,
                    'total': quote_keys + market_data_keys + news_keys
                }
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {'error': str(e)}
    
    def _calculate_hit_rate(self, info: Dict) -> float:
        """Calculate cache hit rate"""
        hits = info.get('keyspace_hits', 0)
        misses = info.get('keyspace_misses', 0)
        total = hits + misses
        
        if total == 0:
            return 0.0
        
        return round((hits / total) * 100, 2)
    
    def health_check(self) -> str:
        """Check cache health"""
        try:
            self.redis_client.ping()
            return 'healthy'
        except Exception as e:
            logger.error(f"Cache health check failed: {str(e)}")
            return 'unhealthy'
    
    def warm_cache(self, keys_data: Dict[str, Any]):
        """Warm cache with multiple keys"""
        try:
            pipe = self.redis_client.pipeline()
            
            for key, data in keys_data.items():
                value = data.get('value')
                ttl = data.get('ttl', 3600)
                
                serialized_value = json.dumps(value, default=str)
                pipe.setex(key, ttl, serialized_value)
            
            pipe.execute()
            logger.info(f"Cache warmed with {len(keys_data)} keys")
            
        except Exception as e:
            logger.error(f"Error warming cache: {str(e)}")


class MockRedis:
    """Mock Redis client for development/testing"""
    
    def __init__(self):
        self.data = {}
        self.expires = {}
        logger.warning("Using MockRedis - data will not persist!")
    
    def get(self, key: str):
        # Check if key has expired
        if key in self.expires and datetime.now() > self.expires[key]:
            del self.data[key]
            del self.expires[key]
            return None
        
        return self.data.get(key)
    
    def setex(self, key: str, ttl: int, value: str):
        self.data[key] = value
        self.expires[key] = datetime.now() + timedelta(seconds=ttl)
    
    def set(self, key: str, value: str):
        self.data[key] = value
    
    def delete(self, key: str):
        self.data.pop(key, None)
        self.expires.pop(key, None)
    
    def exists(self, key: str) -> bool:
        return key in self.data
    
    def ttl(self, key: str) -> int:
        if key in self.expires:
            remaining = (self.expires[key] - datetime.now()).total_seconds()
            return max(0, int(remaining))
        return -1
    
    def incr(self, key: str, amount: int = 1) -> int:
        current = int(self.data.get(key, 0))
        self.data[key] = str(current + amount)
        return current + amount
    
    def keys(self, pattern: str) -> list:
        import fnmatch
        return [key for key in self.data.keys() if fnmatch.fnmatch(key, pattern)]
    
    def ping(self):
        return True
    
    def info(self):
        return {
            'redis_version': 'mock',
            'used_memory_human': f'{len(self.data)} keys',
            'connected_clients': 1,
            'total_commands_processed': 0,
            'keyspace_hits': 0,
            'keyspace_misses': 0
        }
    
    def pipeline(self):
        return MockPipeline(self)
    
    def expireat(self, key: str, expire_at: datetime):
        self.expires[key] = expire_at


class MockPipeline:
    """Mock Redis pipeline"""
    
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.commands = []
    
    def setex(self, key: str, ttl: int, value: str):
        self.commands.append(('setex', key, ttl, value))
        return self
    
    def execute(self):
        for command in self.commands:
            if command[0] == 'setex':
                self.redis_client.setex(command[1], command[2], command[3])
        self.commands.clear()
