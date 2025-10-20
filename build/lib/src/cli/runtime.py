"""Runtime utilities for watchdog timers and concurrency control.

Provides:
- --max-duration-seconds watchdog to prevent runaway jobs
- File-based advisory locks for --lock-file
- Signal handling and graceful shutdown
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import signal
import threading
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


class WatchdogTimeout(Exception):
    """Raised when watchdog timer expires."""
    pass


class LockError(Exception):
    """Raised when lock acquisition fails."""
    pass


class Watchdog:
    """Watchdog timer to enforce maximum execution duration."""
    
    def __init__(self, max_duration_seconds: float, callback: Callable[[], None] | None = None):
        """Initialize watchdog timer.
        
        Args:
            max_duration_seconds: Maximum allowed duration
            callback: Optional callback to execute on timeout (before raising exception)
        """
        self.max_duration = max_duration_seconds
        self.callback = callback
        self._timer: threading.Timer | None = None
        self._started = False
        self._expired = False
        logger.info(f"⏱️  Watchdog initialized: {max_duration_seconds}s timeout")
    
    def _timeout_handler(self) -> None:
        """Handle watchdog timeout."""
        self._expired = True
        logger.error(f"❌ Watchdog timeout: process exceeded {self.max_duration}s")
        
        # Execute callback if provided
        if self.callback:
            try:
                self.callback()
            except Exception as e:
                logger.error(f"Watchdog callback failed: {e}")
        
        # Raise exception to terminate
        # Note: This runs in timer thread, so we use os._exit for immediate termination
        logger.critical("Forcing immediate termination due to watchdog timeout")
        os._exit(124)  # Exit code 124 for timeout (same as GNU timeout)
    
    def start(self) -> None:
        """Start the watchdog timer."""
        if self._started:
            logger.warning("Watchdog already started")
            return
        
        self._timer = threading.Timer(self.max_duration, self._timeout_handler)
        self._timer.daemon = True
        self._timer.start()
        self._started = True
        logger.info(f"✅ Watchdog started: {self.max_duration}s")
    
    def cancel(self) -> None:
        """Cancel the watchdog timer."""
        if self._timer:
            self._timer.cancel()
            self._started = False
            logger.info("✅ Watchdog cancelled (completed within time limit)")
    
    def is_expired(self) -> bool:
        """Check if watchdog has expired.
        
        Returns:
            True if watchdog timeout occurred
        """
        return self._expired


class FileLock:
    """File-based advisory lock for concurrency control.
    
    Prevents multiple instances from running simultaneously on shared artifacts.
    Uses platform-specific file locking mechanisms with TTL support.
    
    Cross-Platform Behavior:
    -----------------------
    - Uses OS-level file creation atomicity (O_CREAT | O_EXCL)
    - Portable across Windows and Unix-like systems
    - Process existence check is platform-specific:
      * Windows: Uses OpenProcess API
      * Unix: Uses os.kill(pid, 0) signal test
    
    Enhancements (v2.0):
    -------------------
    ✅ TTL Support: Locks have time-to-live for automatic cleanup
    ✅ PID + Timestamp: Lock files contain PID and creation timestamp
    ✅ Stale Detection: Automatic detection and cleanup of stale locks
    ✅ Better Logging: Enhanced lock ownership information
    
    Limitations & Warnings:
    ----------------------
    ⚠️ Race Condition: Small window between file existence check and creation
       on some filesystems (though O_EXCL minimizes this)
    
    ⚠️ Network Filesystems: NOT recommended for NFS or other network filesystems
       due to potential race conditions and stale lock issues
    
    ⚠️ Stale Locks: If process crashes without cleanup, lock file persists
       (but automatic stale lock detection handles this)
    
    Recommendations:
    ---------------
    - Use local filesystem paths only (e.g., /var/run/, C:\ProgramData\)
    - Avoid network-mounted filesystems (NFS, SMB, etc.)
    - Use timeout > 0 to handle stale locks gracefully
    - Set lock_ttl for long-running processes to auto-cleanup
    
    Example:
    -------
        # With TTL (recommended)
        lock = FileLock(
            Path("/var/run/autotrader.lock"),
            timeout=5.0,
            lock_ttl=3600  # Lock expires after 1 hour
        )
        try:
            if lock.acquire():
                # Do work
                pass
        finally:
            lock.release()
    """
    
    def __init__(
        self,
        lock_file: Path,
        timeout: float = 0,
        lock_ttl: float | None = None,
    ):
        """Initialize file lock.
        
        Args:
            lock_file: Path to lock file
            timeout: Maximum time to wait for lock (0 = fail immediately)
            lock_ttl: Time-to-live for lock in seconds (None = no TTL)
        """
        self.lock_file = lock_file
        self.timeout = timeout
        self.lock_ttl = lock_ttl
        self._fd: int | None = None
        self._acquired = False
        self._lock_created_at: float | None = None
        logger.info(
            f"🔒 Lock initialized: {lock_file}"
            + (f" (TTL: {lock_ttl}s)" if lock_ttl else "")
        )
    
    def acquire(self) -> bool:
        """Acquire the lock.
        
        Returns:
            True if lock acquired, False if timeout
            
        Raises:
            LockError: If lock acquisition fails
        """
        if self._acquired:
            logger.warning("Lock already acquired")
            return True
        
        # Create lock file directory if needed
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        
        start_time = time.time()
        
        while True:
            try:
                # Try to create lock file exclusively
                self._fd = os.open(
                    str(self.lock_file),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY
                )
                
                # Write lock metadata: PID and timestamp (JSON format)
                self._lock_created_at = time.time()
                lock_data = json.dumps({
                    "pid": os.getpid(),
                    "created_at": self._lock_created_at,
                    "hostname": os.environ.get("HOSTNAME", "unknown"),
                    "ttl": self.lock_ttl,
                })
                os.write(self._fd, lock_data.encode())
                
                self._acquired = True
                logger.info(
                    f"✅ Lock acquired: {self.lock_file} "
                    f"(PID: {os.getpid()}, TTL: {self.lock_ttl}s)"
                )
                
                # Register cleanup on exit
                atexit.register(self.release)
                
                return True
            
            except FileExistsError:
                # Lock file exists, check if process is still alive or TTL expired
                stale_reason = self._check_stale()
                if stale_reason:
                    logger.warning(
                        f"Removing stale lock: {self.lock_file} "
                        f"(Reason: {stale_reason})"
                    )
                    self._remove_stale_lock()
                    continue
                
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed >= self.timeout:
                    # Get lock owner info for error message
                    owner_info = self._get_lock_owner_info()
                    logger.error(
                        f"❌ Lock timeout after {elapsed:.1f}s: {self.lock_file}\n"
                        f"   Lock owned by: {owner_info}"
                    )
                    return False
                
                # Wait and retry
                time.sleep(0.1)
            
            except Exception as e:
                raise LockError(f"Failed to acquire lock: {e}") from e
    
    def release(self) -> None:
        """Release the lock."""
        if not self._acquired:
            return
        
        try:
            if self._fd is not None:
                os.close(self._fd)
                self._fd = None
            
            if self.lock_file.exists():
                self.lock_file.unlink()
            
            self._acquired = False
            logger.info(f"✅ Lock released: {self.lock_file}")
        
        except Exception as e:
            logger.error(f"Failed to release lock: {e}")
    
    def _check_stale(self) -> str | None:
        """Check if lock file is stale.
        
        Returns:
            Reason string if lock is stale, None if lock is valid
        """
        try:
            with self.lock_file.open('r') as f:
                content = f.read().strip()
            
            if not content:
                return "empty lock file"
            
            # Try to parse as JSON (new format with metadata)
            try:
                lock_data = json.loads(content)
                pid = lock_data.get("pid")
                created_at = lock_data.get("created_at")
                ttl = lock_data.get("ttl")
            except json.JSONDecodeError:
                # Old format (just PID)
                pid = int(content)
                created_at = None
                ttl = None
            
            if not pid:
                return "missing PID"
            
            # Check TTL expiration
            if ttl and created_at:
                age = time.time() - created_at
                if age > ttl:
                    return f"TTL expired ({age:.1f}s > {ttl}s)"
            
            # Check if process exists (platform-specific)
            try:
                if os.name == 'nt':  # Windows
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    PROCESS_QUERY_INFORMATION = 0x0400
                    handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, 0, pid)
                    if handle:
                        kernel32.CloseHandle(handle)
                        return None  # Process exists - lock is valid
                    return f"process {pid} no longer exists"
                else:  # Unix-like
                    os.kill(pid, 0)
                    return None  # Process exists - lock is valid
            except (OSError, ProcessLookupError):
                return f"process {pid} no longer exists"
        
        except Exception as e:
            logger.warning(f"Failed to check lock staleness: {e}")
            return None  # Assume not stale if we can't check
    
    def _get_lock_owner_info(self) -> str:
        """Get information about the lock owner.
        
        Returns:
            Human-readable string describing lock owner
        """
        try:
            with self.lock_file.open('r') as f:
                content = f.read().strip()
            
            try:
                lock_data = json.loads(content)
                pid = lock_data.get("pid", "unknown")
                created_at = lock_data.get("created_at")
                hostname = lock_data.get("hostname", "unknown")
                ttl = lock_data.get("ttl")
                
                info = f"PID {pid} on {hostname}"
                if created_at:
                    age = time.time() - created_at
                    info += f" (age: {age:.1f}s"
                    if ttl:
                        info += f", TTL: {ttl}s"
                    info += ")"
                
                return info
            except json.JSONDecodeError:
                # Old format
                return f"PID {content}"
        
        except Exception as e:
            return f"<unable to read: {e}>"
    
    def _remove_stale_lock(self) -> None:
        """Remove stale lock file."""
        try:
            self.lock_file.unlink()
        except Exception as e:
            logger.error(f"Failed to remove stale lock: {e}")
    
    def __enter__(self) -> FileLock:
        """Context manager entry."""
        if not self.acquire():
            raise LockError(f"Failed to acquire lock: {self.lock_file}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.release()


class SignalHandler:
    """Handle signals for graceful shutdown."""
    
    def __init__(self):
        """Initialize signal handler."""
        self._shutdown_requested = False
        self._handlers: list[Callable[[], None]] = []
    
    def register_cleanup(self, handler: Callable[[], None]) -> None:
        """Register cleanup handler.
        
        Args:
            handler: Cleanup function to call on shutdown
        """
        self._handlers.append(handler)
    
    def setup(self) -> None:
        """Setup signal handlers."""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        logger.info("✅ Signal handlers registered")
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        sig_name = signal.Signals(signum).name
        logger.warning(f"⚠️  Received {sig_name}, initiating graceful shutdown...")
        
        self._shutdown_requested = True
        
        # Execute cleanup handlers
        for handler in self._handlers:
            try:
                handler()
            except Exception as e:
                logger.error(f"Cleanup handler failed: {e}")
        
        # Exit with appropriate code
        exit_code = 130 if signum == signal.SIGINT else 143
        logger.info(f"✅ Graceful shutdown complete, exiting with code {exit_code}")
        os._exit(exit_code)
    
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown was requested.
        
        Returns:
            True if shutdown signal received
        """
        return self._shutdown_requested


def create_watchdog(
    max_duration_seconds: float | None,
    cleanup_callback: Callable[[], None] | None = None,
) -> Watchdog | None:
    """Create and start watchdog if duration specified.
    
    Args:
        max_duration_seconds: Maximum duration (None to disable)
        cleanup_callback: Optional cleanup callback
        
    Returns:
        Watchdog instance or None if disabled
    """
    if max_duration_seconds is None or max_duration_seconds <= 0:
        return None
    
    watchdog = Watchdog(max_duration_seconds, cleanup_callback)
    watchdog.start()
    return watchdog


def create_lock(
    lock_file: Path | None,
    timeout: float = 0,
) -> FileLock | None:
    """Create file lock if path specified.
    
    Args:
        lock_file: Path to lock file (None to disable)
        timeout: Lock acquisition timeout
        
    Returns:
        FileLock instance or None if disabled
        
    Raises:
        LockError: If lock cannot be acquired
    """
    if lock_file is None:
        return None
    
    lock = FileLock(lock_file, timeout)
    if not lock.acquire():
        raise LockError(f"Failed to acquire lock within {timeout}s: {lock_file}")
    
    return lock
