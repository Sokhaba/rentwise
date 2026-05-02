"""Run DBT commands from within the Prefect pipeline."""

import subprocess
from pathlib import Path
from loguru import logger

DBT_PROJECT_DIR = Path(__file__).parent.parent / "dbt"


def run_dbt(select: str = "staging+", command: str = "build") -> None:
    """
    Run `dbt build --select <select>` inside the dbt project directory.
    Raises on failure so Prefect marks the task failed.
    """
    cmd = [
        "dbt", command,
        "--select", select,
        "--project-dir", str(DBT_PROJECT_DIR),
        "--profiles-dir", str(Path.home() / ".dbt"),
    ]
    logger.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout:
        logger.info(result.stdout)
    if result.stderr:
        logger.warning(result.stderr)

    if result.returncode != 0:
        raise RuntimeError(f"dbt {command} failed:\n{result.stderr}")

    logger.info("DBT run succeeded")
