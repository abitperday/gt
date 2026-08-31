"""Start the collector together with the API used by both dashboards.

Keeping the collector and FastAPI application in one process is required for
the live dashboard: its latest-frame hub is intentionally in-memory.
"""

from live_server import main


if __name__ == "__main__":
    main()
