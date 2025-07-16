import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from collections import defaultdict, deque

from models.data_models import DataTier, get_tier_config

logger = logging.getLogger(__name__)

class RateLimiter:
    """Rate limiter with tier-based limits"""
    
    def __init__(self):
        # Store request timestamps for each key
        self.request_history: Dict[str, deque] = defaultdict(deque)
        self.cleanup_interval = 60  # seconds
        self.last_cleanup = datetime.now()
    
    def is_allowed(self, key: str, tier: DataTier) -> bool:
        """Check if request is allowed based on tier limits"""
        
        # Clean up old entries periodically
        self._cleanup_old_entries()
        
        tier_config = get_tier_config(tier)
        limit = tier_config.rate_limit_per_minute
        
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        # Get request history for this key
        requests = self.request_history[key]
        
        # Remove requests older than 1 minute
        while requests and requests[0] < minute_ago:
            requests.popleft()
        
        # Check if limit is exceeded
        if len(requests) >= limit:
            logger.warning(f"Rate limit exceeded for key {key} (tier: {tier.name}, limit: {limit})")
            return False
        
        # Add current request
        requests.append(now)
        
        return True
    
    def get_remaining_requests(self, key: str, tier: DataTier) -> int:
        """Get remaining requests for a key"""
        tier_config = get_tier_config(tier)
        limit = tier_config.rate_limit_per_minute
        
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        requests = self.request_history[key]
        
        # Count requests in the last minute
        recent_requests = sum(1 for req_time in requests if req_time > minute_ago)
        
        return max(0, limit - recent_requests)
    
    def get_reset_time(self, key: str) -> Optional[datetime]:
        """Get when the rate limit will reset for a key"""
        requests = self.request_history[key]
        
        if not requests:
            return None
        
        # The limit will reset when the oldest request is 1 minute old
        oldest_request = requests[0]
        reset_time = oldest_request + timedelta(minutes=1)
        
        return reset_time
    
    def _cleanup_old_entries(self):
        """Clean up old request entries"""
        now = datetime.now()
        
        # Only cleanup every minute
        if (now - self.last_cleanup).total_seconds() < self.cleanup_interval:
            return
        
        minute_ago = now - timedelta(minutes=1)
        
        # Clean up old entries
        keys_to_remove = []
        for key, requests in self.request_history.items():
            # Remove old requests
            while requests and requests[0] < minute_ago:
                requests.popleft()
            
            # Remove empty entries
            if not requests:
                keys_to_remove.append(key)
        
        # Remove empty keys
        for key in keys_to_remove:
            del self.request_history[key]
        
        self.last_cleanup = now
        
        if keys_to_remove:
            logger.debug(f"Cleaned up {len(keys_to_remove)} empty rate limit entries")
    
    def get_stats(self) -> Dict[str, any]:
        """Get rate limiter statistics"""
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        active_keys = 0
        total_requests = 0
        
        for key, requests in self.request_history.items():
            recent_requests = sum(1 for req_time in requests if req_time > minute_ago)
            if recent_requests > 0:
                active_keys += 1
                total_requests += recent_requests
        
        return {
            'active_keys': active_keys,
            'total_recent_requests': total_requests,
            'total_tracked_keys': len(self.request_history)
        }
    
    def reset_key(self, key: str):
        """Reset rate limit for a specific key"""
        if key in self.request_history:
            del self.request_history[key]
            logger.info(f"Rate limit reset for key: {key}")
    
    def reset_all(self):
        """Reset all rate limits"""
        self.request_history.clear()
        logger.info("All rate limits reset")
