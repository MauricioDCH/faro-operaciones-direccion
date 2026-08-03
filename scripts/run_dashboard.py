"""Run the local Faro dashboard."""

from __future__ import annotations

import uvicorn

from faro.settings import Settings


if __name__ == "__main__":
    settings = Settings.from_environment()
    uvicorn.run(
        "faro.ui.app:app",
        host=settings.dashboard_host,
        port=settings.dashboard_port,
        reload=False,
    )
