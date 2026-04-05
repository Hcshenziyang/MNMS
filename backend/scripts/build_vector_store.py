#!/usr/bin/env python
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    os.chdir(project_root)
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from app.agent_engine.tools.rag_store import RAGStore

    store = RAGStore.get_instance()
    store.build_index()
    print("[build_vector_store] index built")
    return 0


if __name__ == "__main__":
    sys.exit(main())
