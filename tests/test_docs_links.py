"""Keep the documentation's links truthful.

The docs point at files, at headings in other documents and at exact line ranges in
the source. These tests fail when a link stops matching what it claims to show, e.g.
after code was moved without updating ``docs/przewodnik-po-kodzie.md``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DOCUMENTS = sorted([*REPO.glob("*.md"), *REPO.glob("docs/*.md"), *REPO.glob("runbooks/*.md")])

LINK = re.compile(r"\[((?:[^\[\]]|\[[^\]]*\])+)\]\(([^)\s]+)\)")
FENCED_BLOCK = re.compile(r"```.*?```", re.DOTALL)
LINE_ANCHOR = re.compile(r"^L(\d+)(?:-L(\d+))?$")
HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*$", re.MULTILINE)
IDENTIFIER = re.compile(r"`([A-Za-z_][\w.]*)(?:\(\))?`")


def document_id(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def links_in(document: Path) -> list[tuple[str, str]]:
    """(link text, target) for every Markdown link outside fenced code blocks."""
    text = FENCED_BLOCK.sub("", document.read_text(encoding="utf-8"))
    return [(match.group(1), match.group(2)) for match in LINK.finditer(text)]


def local_links(document: Path) -> list[tuple[str, Path, str]]:
    """(link text, target file, fragment) for links that stay inside the repository."""
    result = []
    for text, target in links_in(document):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target):  # http:, https:, mailto:
            continue
        path_part, _, fragment = target.partition("#")
        target_file = (document.parent / path_part).resolve() if path_part else document
        result.append((text, target_file, fragment))
    return result


def heading_anchors(document: Path) -> set[str]:
    """Anchors GitHub generates for the headings of a Markdown file."""
    text = FENCED_BLOCK.sub("", document.read_text(encoding="utf-8"))
    anchors = set()
    for heading in HEADING.findall(text):
        slug = re.sub(r"[^\w\- ]", "", heading.lower(), flags=re.UNICODE)
        anchors.add(slug.replace(" ", "-"))
    return anchors


def test_there_are_documents_to_check():
    assert len(DOCUMENTS) > 10


@pytest.mark.parametrize("document", DOCUMENTS, ids=document_id)
def test_links_point_at_existing_files_and_headings(document):
    problems = []
    for text, target_file, fragment in local_links(document):
        if not target_file.exists():
            problems.append(f"[{text}] -> missing file {target_file.relative_to(REPO)}")
        elif target_file.suffix == ".md" and fragment and not LINE_ANCHOR.match(fragment):
            if fragment not in heading_anchors(target_file):
                problems.append(f"[{text}] -> no heading #{fragment} in {target_file.name}")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("document", DOCUMENTS, ids=document_id)
def test_line_anchors_show_the_code_they_name(document):
    """A link like [`MacroBot.on_step`](bot.py#L62-L68) must contain ``on_step`` there."""
    problems = []
    for text, target_file, fragment in local_links(document):
        anchor = LINE_ANCHOR.match(fragment)
        if anchor is None or not target_file.exists():
            continue
        lines = target_file.read_text(encoding="utf-8").splitlines()
        first = int(anchor.group(1))
        last = int(anchor.group(2) or first)
        where = f"{target_file.relative_to(REPO).as_posix()}#{fragment}"
        if not 1 <= first <= last <= len(lines):
            problems.append(f"[{text}] -> {where} is outside the file ({len(lines)} lines)")
            continue
        shown = "\n".join(lines[first - 1 : last])
        for identifier in IDENTIFIER.findall(text):
            name = identifier.rsplit(".", 1)[-1]
            if name not in shown:
                problems.append(f"[{text}] -> {where} does not contain {name!r}")
    assert not problems, "\n".join(problems)
