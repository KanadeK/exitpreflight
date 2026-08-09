from __future__ import annotations

from pathlib import Path


def write_text(root: Path, relative: str, content: str) -> Path:
    path = root / Path(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def create_slack_export(root: Path, *, missing_user: bool = False) -> Path:
    write_text(root, "channels.json", '[{"id":"C1","name":"general"}]\n')
    write_text(root, "users.json", '[{"id":"U1","name":"alex"}]\n')
    user = "U2" if missing_user else "U1"
    write_text(
        root,
        "general/2026-08-01.json",
        '[{"type":"message","user":"' + user + '","text":"design", "files":[{"id":"F1",'
        '"url_private":"https://files.slack.com/files-pri/T1-F1/design.pdf"}]}]\n',
    )
    return root


def create_gmail_export(root: Path, *, labels: bool = True) -> Path:
    label_header = "X-Gmail-Labels: Inbox,Important\n" if labels else ""
    write_text(root, "Takeout/archive_browser.html", "<!doctype html><title>Takeout</title>\n")
    write_text(
        root,
        "Takeout/Mail/All mail.mbox",
        "From sender@example.com Sat Aug  1 00:00:00 2026\n"
        "From: sender@example.com\n"
        "To: owner@example.com\n"
        "Subject: Project\n" + label_header + "Content-Type: text/plain; charset=utf-8\n\n"
        "Download https://drive.google.com/file/d/example/view\n",
    )
    return root
