"""
Alexandria Example Builder — shows the pattern for building a project graph.

Copy this file and customize it for your project. The builder walks your
codebase, extracts structure, and populates the Alexandria knowledge graph.

Usage:
    python -m alexandria.example_builder
"""

from pathlib import Path
from alexandria.graph import AlexandriaGraph


def build_example(project_root: str = ".") -> AlexandriaGraph:
    """Build an example Alexandria graph from a project directory.

    This demonstrates the builder pattern. Customize for your project by:
    1. Walking your source tree and calling add_file() for each file
    2. Parsing imports and calling add_import()
    3. Extracting functions/classes and calling add_function()/add_class()
    4. Registering API endpoints with add_endpoint()
    5. Adding agents with add_agent()
    6. Recording lessons and decisions with add_lesson()
    """
    graph = AlexandriaGraph()
    root = Path(project_root)

    # -- Step 1: Register agents --
    graph.add_agent("agent-a", host="YOUR_SERVER", role="planner")
    graph.add_agent("agent-b", host="YOUR_SERVER", role="builder")

    # -- Step 2: Walk source files --
    for py_file in root.rglob("*.py"):
        rel_path = str(py_file.relative_to(root))

        # Skip venvs and caches
        if any(skip in rel_path for skip in ["venv/", "__pycache__/", "node_modules/"]):
            continue

        graph.add_file(rel_path, language="python")

    for ts_file in root.rglob("*.ts"):
        rel_path = str(ts_file.relative_to(root))
        if "node_modules/" not in rel_path:
            graph.add_file(rel_path, language="typescript")

    for tsx_file in root.rglob("*.tsx"):
        rel_path = str(tsx_file.relative_to(root))
        if "node_modules/" not in rel_path:
            graph.add_file(rel_path, language="tsx")

    # -- Step 3: Add lessons from your knowledge base --
    # Example: Read from a lessons directory
    lessons_dir = root / "templates" / "knowledge" / "lessons"
    if lessons_dir.exists():
        for lesson_file in lessons_dir.glob("*.md"):
            title = lesson_file.stem.replace("-", " ").title()
            graph.add_lesson(title, source=str(lesson_file))

    # -- Step 4: Save --
    graph.save()

    stats = graph.stats()
    print(f"Alexandria graph built: {stats['nodes']} nodes, {stats['edges']} edges")
    print(f"By type: {stats['by_type']}")

    return graph


if __name__ == "__main__":
    build_example()
