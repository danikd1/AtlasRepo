
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

class RateLimiter:
    

    def __init__(self, delay_seconds: float = 1.5):
        
        self.delay_seconds = delay_seconds
        self._last_request_time: Optional[float] = None

def wait_if_needed(self) -> None:
        
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.delay_seconds:
                sleep_time = self.delay_seconds - elapsed
                logger.debug(f"Rate limit: ожидание {sleep_time:.2f} сек")
                time.sleep(sleep_time)

self._last_request_time = time.time()

def reset(self) -> None:
        
        self._last_request_time = None

