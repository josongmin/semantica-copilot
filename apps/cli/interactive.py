"""대화형 CLI 실행"""

import sys
from pathlib import Path

# codegraph 프로젝트를 sys.path에 추가
project_root = Path(__file__).parent.parent.parent
codegraph_root = project_root.parent / "semantica-codegraph"
if str(codegraph_root) not in sys.path:
    sys.path.insert(0, str(codegraph_root))

from apps.cli.app2 import SemanticaApp  # noqa: E402
from src.core.bootstrap import create_bootstrap  # noqa: E402


def run_interactive() -> None:
    """대화형 CLI 실행"""
    try:
        bootstrap = create_bootstrap()
    except Exception as e:
        from rich.console import Console

        console = Console()
        console.print("[bold red]초기화 실패[/bold red]")
        console.print(f"[red]{str(e)}[/red]")
        console.print("\n환경변수를 확인해주세요.")
        sys.exit(1)

    # Textual 앱 실행
    app = SemanticaApp(bootstrap)
    app.run()
