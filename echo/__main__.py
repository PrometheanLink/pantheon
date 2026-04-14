"""Allow running Echo as: python -m echo"""
from .cli import main
import sys

sys.exit(main())
