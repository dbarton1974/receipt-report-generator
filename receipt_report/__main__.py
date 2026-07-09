"""Makes the package runnable with `python -m receipt_report`."""

import sys

from .main import main

if __name__ == "__main__":
    sys.exit(main())
