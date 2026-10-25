"""Core audit logic: docs progress claims vs Python source evidence."""

import ast
import fnmatch
import json
import re
from pathlib import Path

VERSION = "0.1.0"

PROGRESS_PHRASES = [
    "shows a progress bar",
    "displays a progress bar",
    "shows a progress indicator",
    "displays a progress indicator",
    "with a progress bar",
    "shows progress updates",
    "shows progress",
    "displays progress",
    "progress bar",
    "progress indicator",
    "live progress",
    "progress reporting",
    "reports progress",
    "progress updates",
    "progress display",
]

NO_PROGRESS_PHRASES = [
    "no progress bar",
    "no progress indicator",
    "no progress output",
    "without a progress bar",
    "without progress",
    "does not show progress",
    "never shows progress",
    "no progress reporting",
    "no progress updates",
    "does not report progress",
    "no progress display",
]

PROGRESS_LIBS = {"tqdm", "alive_progress", "progressbar", "progressbar2"}
NEGATIONS = {"no", "not", "never", "without"}

EXCLUDE_DIRS = {"tests", "fixtures", "docs", "examples"}


def normalize(text):
    text = text.lower().replace("n't", " not")
    text = text.replace("-", " ")
    return re.sub(r"\s+", " ", text).strip()


def strip_fenced(text):
    lines = text.splitlines()
    out = []
    in_fence = False
    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(line)
    return "\n".join(out)


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def extract_claims(root):
    """Return {family: [claim, ...]}; claim = {phrase, sentence}."""
    docs = []
    readme = root / "README.md"
    if readme.is_file() and not readme.is_symlink():
        docs.append(readme)
    docs_dir = root / "docs"
    if docs_dir.is_dir():
        for path in sorted(docs_dir.rglob("*.md")):
            if not path.is_symlink():
                docs.append(path)
    claims = {"progress": [], "no_progress": []}
    for path in docs:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for sentence in split_sentences(strip_fenced(text)):
            norm = normalize(sentence)
            tokens = set(norm.split())
            negated = bool(tokens & NEGATIONS)
            for phrase in PROGRESS_PHRASES:
                if re.search(r"\b" + re.escape(phrase) + r"\b", norm):
                    if not negated:
                        claims["progress"].append(
                            {"phrase": phrase, "sentence": sentence}
                        )
                    break
            for phrase in NO_PROGRESS_PHRASES:
                if re.search(r"\b" + re.escape(phrase) + r"\b", norm):
                    claims["no_progress"].append(
                        {"phrase": phrase, "sentence": sentence}
                    )
                    break
    return claims


def _is_test_path(rel):
    parts = rel.parts
    if any(p in EXCLUDE_DIRS for p in parts[:-1]):
        return True
    name = parts[-1]
    return name.startswith("test_") or name.endswith("_test.py")


def _local_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
            for arg in list(node.args.args) + list(node.args.kwonlyargs):
                names.add(arg.arg)
            if node.args.vararg:
                names.add(node.args.vararg.arg)
            if node.args.kwarg:
                names.add(node.args.kwarg.arg)
    return names


def _evidence_for_file(path, tree):
    shadowed = _local_names(tree)
    evidence = []

    def add(kind, lineno):
        evidence.append({"file": str(path), "line": lineno, "kind": kind})

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in PROGRESS_LIBS:
                    add("import:" + alias.name.split(".")[0], node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in PROGRESS_LIBS:
                add("import:" + node.module.split(".")[0], node.lineno)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                if func.id == "tqdm" and "tqdm" not in shadowed:
                    add("call:tqdm", node.lineno)
                elif func.id == "Progress":
                    add("call:Progress", node.lineno)
                elif func.id == "ProgressBar":
                    add("call:ProgressBar", node.lineno)
                elif func.id == "alive_bar":
                    add("call:alive_bar", node.lineno)
            elif isinstance(func, ast.Attribute):
                if func.attr == "tqdm":
                    add("call:tqdm", node.lineno)
                elif func.attr == "Progress":
                    add("call:Progress", node.lineno)
                elif func.attr == "ProgressBar":
                    add("call:ProgressBar", node.lineno)
                elif func.attr == "alive_bar":
                    add("call:alive_bar", node.lineno)
                elif func.attr == "progressbar":
                    add("call:progressbar", node.lineno)
                elif func.attr in ("update", "advance"):
                    if isinstance(func.value, ast.Name):
                        recv = func.value.id.lower()
                        if "progress" in recv or "bar" in recv:
                            add("call:" + func.attr, node.lineno)
    seen = set()
    out = []
    for item in evidence:
        key = (item["file"], item["line"], item["kind"])
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def collect_evidence(root, ignore_patterns):
    """Return (production_evidence, test_only_evidence, has_production_source)."""
    prod, test_only = [], []
    has_prod = False
    for path in sorted(root.rglob("*.py")):
        if path.is_symlink():
            continue
        rel = path.relative_to(root)
        rel_posix = rel.as_posix()
        if any(fnmatch.fnmatch(rel_posix, pat) for pat in ignore_patterns):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except (SyntaxError, OSError, ValueError):
            continue
        items = _evidence_for_file(rel_posix, tree)
        if _is_test_path(rel):
            test_only.extend(items)
        else:
            has_prod = True
            prod.extend(items)
    return prod, test_only, has_prod


def audit(root, ignore_patterns=()):
    root = Path(root)
    claims = extract_claims(root)
    prod, test_only, has_prod = collect_evidence(root, ignore_patterns)
    findings = []
    verified = []

    def family_result(family, false_rule, test_rule):
        fam_claims = claims[family]
        if not fam_claims:
            return
        if family == "progress":
            if prod:
                verified.append({"family": family, "claims": fam_claims,
                                 "evidence": prod})
            elif not has_prod:
                findings.append({"rule": false_rule, "severity": "HIGH",
                                 "family": family, "claims": fam_claims,
                                 "evidence": [{"kind": "no-source"}]})
            elif test_only:
                findings.append({"rule": test_rule, "severity": "MEDIUM",
                                 "family": family, "claims": fam_claims,
                                 "evidence": test_only})
            else:
                findings.append({"rule": false_rule, "severity": "HIGH",
                                 "family": family, "claims": fam_claims,
                                 "evidence": [{"kind": "no-progress-evidence"}]})
        else:  # no_progress
            if prod:
                findings.append({"rule": false_rule, "severity": "HIGH",
                                 "family": family, "claims": fam_claims,
                                 "evidence": prod})
            elif not has_prod:
                findings.append({"rule": false_rule, "severity": "HIGH",
                                 "family": family, "claims": fam_claims,
                                 "evidence": [{"kind": "no-source"}]})
            elif test_only:
                findings.append({"rule": test_rule, "severity": "MEDIUM",
                                 "family": family, "claims": fam_claims,
                                 "evidence": test_only})
            else:
                verified.append({"family": family, "claims": fam_claims,
                                 "evidence": []})

    family_result("progress", "documented-progress-claim-false",
                  "documented-progress-claim-false-test-only")
    family_result("no_progress", "documented-no-progress-claim-false",
                  "documented-no-progress-claim-false-test-only")
    status = "PASS" if not findings else "FAIL"
    return {"status": status, "findings": findings, "verified_claims": verified}


def format_human(result):
    lines = ["status: " + result["status"]]
    for finding in result["findings"]:
        lines.append(
            "%s %s (%s)" % (finding["severity"], finding["rule"], finding["family"])
        )
        for ev in finding["evidence"]:
            lines.append("  - %s" % ev.get("kind"))
    for claim in result["verified_claims"]:
        lines.append("verified: %s" % claim["family"])
    return "\n".join(lines) + "\n"


def result_json(result):
    return json.dumps(result, indent=2) + "\n"
