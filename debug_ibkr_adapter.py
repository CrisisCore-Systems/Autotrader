import os
import logging

class IBKRAdapter:
    def __init__(self, log_dir="logs"):
        self._log_dir = log_dir
        self._logger = self._initialize_logger()
        self._expected_wal_positions = {}
        self._expected_active_perm_ids = set()
        self._logger.info(f"Adapter initialized with log directory: {self._log_dir}")

    def _initialize_logger(self):
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger("IBKRAdapter")

if __name__ == "__main__":
    adapter = IBKRAdapter()
    print(f"Log directory: {adapter._log_dir}")
