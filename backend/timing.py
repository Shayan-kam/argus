"""
Timing utilities for Argus performance monitoring.
"""

import time


class Timer:
    def __init__(self, name):
        self.name = name
        self.start_time = None
        self.elapsed_seconds = 0.0

    def start(self):
        self.start_time = time.perf_counter()

    def stop(self):
        if self.start_time is None:
            return 0.0

        self.elapsed_seconds = time.perf_counter() - self.start_time
        return self.elapsed_seconds


def format_duration(seconds):
    return round(seconds, 3)