"""Serial request pacing; response time counts toward the existing interval."""
import time


class RequestPacer:
    def __init__(self, interval):
        if interval < 0:
            raise ValueError("interval must be nonnegative")
        self.interval = interval
        self.last_started = None

    def wait(self):
        if self.last_started is not None:
            remaining = self.interval - (time.monotonic() - self.last_started)
            if remaining > 0:
                time.sleep(remaining)
        self.last_started = time.monotonic()
