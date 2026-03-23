"""
Isolated sandbox environment for safe experimentation.
Copies .env, creates fresh empty DBs in a temp dir, auto-cleans up on exit.

Usage:
    from tests.sandbox.sandbox_env import SandboxEnvironment
    with SandboxEnvironment().activate() as sandbox_dir:
        # code here runs isolated from the live DB
"""

import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path


class SandboxEnvironment:
    """Isolated environment — copy of .env, fresh empty databases, auto-cleanup."""

    def __init__(self, project_root: str | None = None):
        self.project_root = Path(project_root or os.getcwd())
        self.sandbox_dir: Path | None = None
        self._original_cwd = os.getcwd()

    @contextmanager
    def activate(self):
        """Context manager: switch into sandbox, guarantee cleanup on exit."""
        try:
            self.sandbox_dir = Path(tempfile.mkdtemp(prefix="is_sandbox_"))
            self._setup()
            os.chdir(self.sandbox_dir)
            print(f"✅ Sandbox: {self.sandbox_dir}")
            yield str(self.sandbox_dir)
        finally:
            os.chdir(self._original_cwd)
            if self.sandbox_dir and self.sandbox_dir.exists():
                shutil.rmtree(self.sandbox_dir)
                print("✅ Sandbox cleaned up")

    def _setup(self) -> None:
        assert self.sandbox_dir is not None

        # Copy .env so API keys are available
        env_src = self.project_root / ".env"
        if env_src.exists():
            shutil.copy(env_src, self.sandbox_dir / ".env")

        # Create empty SQLite databases
        (self.sandbox_dir / "insightswarm_graph.db").touch()
        print("✅ Sandbox environment ready")


if __name__ == "__main__":
    with SandboxEnvironment().activate() as sandbox:
        print(f"Working in: {sandbox}")
        print(f"CWD       : {os.getcwd()}")

        import sys; sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from src.llm.client import FreeLLMClient
        client = FreeLLMClient()
        print(f"Groq available: {client.groq_available}")
