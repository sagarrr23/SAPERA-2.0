# utils/retry.py

import time
import logging

def retry(operation, retries=3, delay=5, backoff=2, on_fail=None):
    """
    Retry wrapper for fail-safe execution.

    Args:
        operation: A lambda or function to execute.
        retries: Number of retry attempts.
        delay: Initial delay between retries (in seconds).
        backoff: Multiplier for delay (e.g., exponential backoff).
        on_fail: Optional fallback function if all retries fail.

    Returns:
        Result of operation or fallback value if specified.
    """
    for attempt in range(1, retries + 1):
        try:
            return operation()
        except Exception as e:
            logging.warning(f"[Retry {attempt}] {operation.__name__ if hasattr(operation, '__name__') else 'task'} failed: {e}")
            if attempt == retries:
                logging.error("Max retries reached.")
                if on_fail:
                    return on_fail()
                raise
            time.sleep(delay)
            delay *= backoff
