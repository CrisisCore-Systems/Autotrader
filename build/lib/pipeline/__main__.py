"""Make pipeline.cli_backtest executable as a module."""

from pipeline.cli_backtest import main
import sys

if __name__ == "__main__":
    sys.exit(main())
