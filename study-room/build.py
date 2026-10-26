"""Build a self-contained, offline study page from the project's question bank."""
from pathlib import Path
import json
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / "bao_cao/ON_TAP_BAO_VE_HOI_DAP.md"
text = SOURCE.read_text(encoding="utf-8")
sections = []
questions = []
for match in re.finditer(r"^## ([A-I])\. (.+)\n([\s\S]*?)(?=^## |\Z)", text, re.M):
    letter, title, body = match.groups()
    sections.append({"id": letter, "title": title})
    for question in re.finditer(r"^### (\d+)\. (.+)\n([\s\S]*?)(?=^### |\Z)", body, re.M):
        number, prompt, answer = question.groups()
        questions.append({"id": int(number), "section": letter, "important": "★" in prompt,
                          "title": prompt.replace("★", "").strip(), "answer": answer.strip()})
assert len(questions) == 70, f"Expected 70 questions, found {len(questions)}"
assert len({q['id'] for q in questions}) == 70
lock = json.loads((ROOT / "artifacts/classification/model_lock.json").read_text(encoding="utf-8"))
facts_match = re.search(r"### Những con số nên nhớ\n([\s\S]*?)(?=^### )", text, re.M)
facts = []
for line in facts_match.group(1).strip().splitlines()[2:]:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    if len(cells) == 2:
        facts.append(cells)
intro = re.search(r"## Bài giới thiệu khoảng một phút\n\n> ([\s\S]*?)(?=\n## )", text).group(1).strip()
data = {"sections": sections, "questions": questions, "facts": facts, "intro": intro,
        "metrics": {"histgb": lock['test'][lock['locked_model']], "persistence": lock['test']['persistence']},
        "source": "bao_cao/ON_TAP_BAO_VE_HOI_DAP.md", "date": "23/10/2026"}
html = (HERE / "src/index.html").read_text(encoding="utf-8")
html = html.replace("<!--STYLES-->", "<style>" + (HERE / "src/styles.css").read_text(encoding="utf-8") + "</style>")
serialized = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
html = html.replace("<!--DATA-->", "<script>window.STUDY_DATA=" + serialized + ";</script>")
scripts = "\n".join((HERE / "src" / name).read_text(encoding="utf-8") for name in ("lessons.js", "app.js"))
html = html.replace("<!--APP-->", "<script>" + scripts + "</script>")
out = HERE / "dist/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(html, encoding="utf-8")
print(f"Built {out}: {len(questions)} questions, {len(sections)} topics, {len(facts)} fact cards")
