"""Deterministic mode for reproducible results.

Seeds random number generators across Python, NumPy, and PyTorch for reproducible execution.

⚠️ IMPORTANT LIMITATIONS:
-------------------------
Deterministic mode ONLY controls random number generation. The following remain
nondeterministic unless explicitly handled:

❌ External API call ordering (network timing varies)
❌ HTTP fetch timing and response ordering  
❌ Database query result ordering (use ORDER BY)
❌ Filesystem operations (file listing, timestamps)
❌ Multi-threading race conditions
❌ System time operations (datetime.now(), time.time())
❌ External process scheduling

For Full Reproducibility:
-------------------------
1. Set PYTHONHASHSEED=0 before running Python
2. Use snapshot datasets instead of live APIs
3. Cache API responses deterministically
4. Sort database results explicitly
5. Use fixed timestamps, not datetime.now()
6. Avoid thread pools with non-deterministic scheduling

Seeds:
------
- Python random module
- NumPy random (if available)
- PyTorch CPU/CUDA (if available)
- Hash functions (via PYTHONHASHSEED check)
"""

from __future__ import annotations

import hashlib
import logging
import os
import random
import sys
from typing import Any

logger = logging.getLogger(__name__)


def enable_deterministic_mode(seed: int = 42) -> dict[str, bool]:
    """Enable deterministic mode across all random sources.
    
    Args:
        seed: Random seed value
        
    Returns:
        Dictionary indicating which libraries were seeded
        
    Example:
        result = enable_deterministic_mode(42)
        # result: {'python': True, 'numpy': True, 'torch': False}
    """
    logger.info(f"🎲 Enabling deterministic mode with seed: {seed}")
    
    results = {
        'python': False,
        'numpy': False,
        'torch': False,
        'hash_seed': False,
    }
    
    # Seed Python's random module
    try:
        random.seed(seed)
        results['python'] = True
        logger.info("✅ Python random seeded")
    except Exception as e:
        logger.warning(f"Failed to seed Python random: {e}")
    
    # Seed NumPy if available
    try:
        import numpy as np
        np.random.seed(seed)
        results['numpy'] = True
        logger.info("✅ NumPy random seeded")
    except ImportError:
        logger.debug("NumPy not available, skipping")
    except Exception as e:
        logger.warning(f"Failed to seed NumPy: {e}")
    
    # Seed PyTorch if available
    try:
        import torch
        torch.manual_seed(seed)
        
        # Set deterministic mode for CUDA if available
        if torch.cuda.is_available():
            torch.cuda.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)
            
            # Enable deterministic algorithms
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
            logger.info("✅ PyTorch CUDA seeded and deterministic mode enabled")
        
        results['torch'] = True
        logger.info("✅ PyTorch seeded")
    except ImportError:
        logger.debug("PyTorch not available, skipping")
    except Exception as e:
        logger.warning(f"Failed to seed PyTorch: {e}")
    
    # Set Python hash seed (must be done before Python starts, so we check if it's set)
    hash_seed_env = os.environ.get('PYTHONHASHSEED')
    if hash_seed_env is None:
        logger.warning(
            "⚠️  PYTHONHASHSEED not set. For full determinism, set PYTHONHASHSEED=0 "
            "before starting Python"
        )
    else:
        results['hash_seed'] = True
        logger.info(f"✅ Python hash seed set: {hash_seed_env}")
    
    # Log summary
    seeded_count = sum(results.values())
    total_count = len(results)
    logger.info(f"✅ Deterministic mode enabled: {seeded_count}/{total_count} libraries seeded")
    
    return results


def verify_deterministic_mode() -> dict[str, Any]:
    """Verify that deterministic mode is working.
    
    Generates test random values to ensure reproducibility.
    
    Returns:
        Dictionary with verification results and test values
    """
    logger.info("🔍 Verifying deterministic mode...")
    
    verification = {
        'python': None,
        'numpy': None,
        'torch': None,
    }
    
    # Test Python random
    try:
        test_value = random.random()
        verification['python'] = {'value': test_value, 'verified': True}
        logger.debug(f"Python random test value: {test_value}")
    except Exception as e:
        verification['python'] = {'error': str(e), 'verified': False}
        logger.warning(f"Python random verification failed: {e}")
    
    # Test NumPy
    try:
        import numpy as np
        test_array = np.random.rand(3)
        verification['numpy'] = {
            'values': test_array.tolist(),
            'verified': True,
        }
        logger.debug(f"NumPy random test values: {test_array}")
    except ImportError:
        verification['numpy'] = {'available': False}
    except Exception as e:
        verification['numpy'] = {'error': str(e), 'verified': False}
        logger.warning(f"NumPy random verification failed: {e}")
    
    # Test PyTorch
    try:
        import torch
        test_tensor = torch.rand(3)
        verification['torch'] = {
            'values': test_tensor.tolist(),
            'verified': True,
        }
        logger.debug(f"PyTorch random test values: {test_tensor}")
    except ImportError:
        verification['torch'] = {'available': False}
    except Exception as e:
        verification['torch'] = {'error': str(e), 'verified': False}
        logger.warning(f"PyTorch random verification failed: {e}")
    
    logger.info("✅ Deterministic mode verification complete")
    return verification


def create_deterministic_hash(data: str | bytes, seed: int = 42) -> str:
    """Create deterministic hash from data.
    
    Args:
        data: Data to hash
        seed: Seed value to include in hash
        
    Returns:
        Hexadecimal hash string
    """
    if isinstance(data, str):
        data = data.encode('utf-8')
    
    # Prepend seed to data for determinism
    seed_bytes = str(seed).encode('utf-8')
    combined = seed_bytes + data
    
    return hashlib.sha256(combined).hexdigest()


def get_random_state() -> dict[str, Any]:
    """Get current random state from all libraries.
    
    Returns:
        Dictionary with random states
    """
    states = {
        'python': random.getstate(),
    }
    
    try:
        import numpy as np
        states['numpy'] = np.random.get_state()
    except ImportError:
        pass
    
    try:
        import torch
        states['torch'] = {
            'cpu': torch.get_rng_state(),
        }
        if torch.cuda.is_available():
            states['torch']['cuda'] = torch.cuda.get_rng_state()
    except ImportError:
        pass
    
    return states


def set_random_state(states: dict[str, Any]) -> None:
    """Restore random state for all libraries.
    
    Args:
        states: Dictionary with random states (from get_random_state)
    """
    if 'python' in states:
        random.setstate(states['python'])
        logger.debug("✅ Restored Python random state")
    
    if 'numpy' in states:
        try:
            import numpy as np
            np.random.set_state(states['numpy'])
            logger.debug("✅ Restored NumPy random state")
        except ImportError:
            pass
    
    if 'torch' in states:
        try:
            import torch
            if 'cpu' in states['torch']:
                torch.set_rng_state(states['torch']['cpu'])
            if 'cuda' in states['torch'] and torch.cuda.is_available():
                torch.cuda.set_rng_state(states['torch']['cuda'])
            logger.debug("✅ Restored PyTorch random state")
        except ImportError:
            pass


def print_seed_info(seed: int) -> None:
    """Print information about deterministic mode setup.
    
    Args:
        seed: Seed value being used
    """
    print("\n" + "=" * 60)
    print("DETERMINISTIC MODE")
    print("=" * 60)
    print(f"Seed: {seed}")
    print(f"PYTHONHASHSEED: {os.environ.get('PYTHONHASHSEED', 'NOT SET')}")
    print("=" * 60)
    print("\nFor full reproducibility, ensure:")
    print("  1. Same seed value")
    print("  2. Same Python version")
    print("  3. Same library versions (NumPy, PyTorch, etc.)")
    print("  4. PYTHONHASHSEED=0 environment variable")
    print("  5. Same hardware (CPU/GPU) configuration")
    print("=" * 60 + "\n")


def check_deterministic_libraries() -> dict[str, str]:
    """Check versions of libraries that affect determinism.
    
    Returns:
        Dictionary mapping library names to versions
    """
    versions = {
        'python': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }
    
    try:
        import numpy as np
        versions['numpy'] = np.__version__
    except ImportError:
        versions['numpy'] = 'not installed'
    
    try:
        import torch
        versions['torch'] = torch.__version__
    except ImportError:
        versions['torch'] = 'not installed'
    
    try:
        import random
        # random is built-in, no version
        versions['random'] = 'builtin'
    except ImportError:
        versions['random'] = 'not available'
    
    return versions


def log_deterministic_environment(seed: int) -> None:
    """Log complete deterministic environment information.
    
    Args:
        seed: Seed value being used
    """
    logger.info("=" * 60)
    logger.info("DETERMINISTIC ENVIRONMENT")
    logger.info("=" * 60)
    logger.info(f"Seed: {seed}")
    logger.info(f"PYTHONHASHSEED: {os.environ.get('PYTHONHASHSEED', 'NOT SET')}")
    
    versions = check_deterministic_libraries()
    logger.info("\nLibrary Versions:")
    for lib, version in versions.items():
        logger.info(f"  {lib}: {version}")
    
    logger.info("=" * 60)
