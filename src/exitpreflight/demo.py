"""Create deterministic synthetic export data for a no-account demo."""

from __future__ import annotations

from pathlib import Path


def create_demo_export(root: str | Path) -> Path:
    target = Path(root)
    (target / "notion" / "assets").mkdir(parents=True, exist_ok=True)
    (target / "slack" / "general").mkdir(parents=True, exist_ok=True)
    (target / "Takeout" / "Mail").mkdir(parents=True, exist_ok=True)
    (target / "notion" / "Project Roadmap 0123456789abcdef0123456789abcdef.md").write_text(
        "# Project Roadmap\n\n![Exported diagram](assets/diagram.png)\n\n"
        "[Original page](https://www.notion.so/example-page)\n",
        encoding="utf-8",
    )
    (target / "notion" / "assets" / "notes.txt").write_text("diagram source\n", encoding="utf-8")
    (target / "slack" / "channels.json").write_text(
        '[{"id":"C1","name":"general"}]\n', encoding="utf-8"
    )
    (target / "slack" / "users.json").write_text('[{"id":"U1","name":"alex"}]\n', encoding="utf-8")
    (target / "slack" / "general" / "2026-08-01.json").write_text(
        '[{"type":"message","user":"U1","text":"See the design",'
        '"files":[{"id":"F1","name":"design.pdf",'
        '"url_private":"https://files.slack.com/files-pri/T1-F1/design.pdf"}]}]\n',
        encoding="utf-8",
    )
    (target / "Takeout" / "archive_browser.html").write_text(
        "<!doctype html><title>Takeout formats</title>\n", encoding="utf-8"
    )
    (target / "Takeout" / "Mail" / "All mail.mbox").write_text(
        "From sender@example.com Sat Aug  1 00:00:00 2026\n"
        "From: sender@example.com\nTo: owner@example.com\nSubject: Project files\n"
        "Date: Sat, 01 Aug 2026 00:00:00 +0000\nX-Gmail-Labels: Inbox,Important\n"
        "Content-Type: text/plain; charset=utf-8\n\n"
        "The source file is at https://drive.google.com/file/d/demo/view\n",
        encoding="utf-8",
    )
    return target
