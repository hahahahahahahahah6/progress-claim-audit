"""Tests for progress-claim-audit."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from progress_claim_audit.audit import audit, extract_claims  # noqa: E402
from progress_claim_audit.__main__ import main  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def make_tree(files):
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return tmp, root


def claims_for(readme_text):
    tmp, root = make_tree({"README.md": readme_text})
    try:
        return extract_claims(root)
    finally:
        tmp.cleanup()


def families_of(readme_text):
    claims = claims_for(readme_text)
    return {k: len(v) for k, v in claims.items()}


class ClaimTests(unittest.TestCase):
    def test_progress_bar_claim(self):
        self.assertEqual(families_of("It shows a progress bar.\n")["progress"], 1)

    def test_progress_display_claim(self):
        self.assertEqual(families_of("It has progress display.\n")["progress"], 1)

    def test_live_progress_claim(self):
        self.assertEqual(families_of("Live progress is on.\n")["progress"], 1)

    def test_reports_progress_claim(self):
        self.assertEqual(families_of("It reports progress.\n")["progress"], 1)

    def test_progress_updates_claim(self):
        self.assertEqual(families_of("It gives progress updates.\n")["progress"], 1)

    def test_progress_reporting_claim(self):
        self.assertEqual(families_of("It has progress reporting.\n")["progress"], 1)

    def test_progress_indicator_claim(self):
        self.assertEqual(families_of("A progress indicator appears.\n")["progress"], 1)

    def test_displays_progress_claim(self):
        self.assertEqual(families_of("It displays progress.\n")["progress"], 1)

    def test_no_progress_bar_claim(self):
        fams = families_of("It has no progress bar.\n")
        self.assertEqual(fams["no_progress"], 1)
        self.assertEqual(fams["progress"], 0)

    def test_no_progress_display_claim(self):
        self.assertEqual(families_of("No progress display here.\n")["no_progress"], 1)

    def test_no_progress_output_claim(self):
        self.assertEqual(families_of("There is no progress output.\n")["no_progress"], 1)

    def test_without_progress_claim(self):
        self.assertEqual(families_of("It runs without progress.\n")["no_progress"], 1)

    def test_doesnt_show_progress_claim(self):
        fams = families_of("It doesn't show progress.\n")
        self.assertEqual(fams["no_progress"], 1)
        self.assertEqual(fams["progress"], 0)

    def test_never_shows_progress_claim(self):
        self.assertEqual(families_of("It never shows progress.\n")["no_progress"], 1)

    def test_does_not_report_progress_claim(self):
        self.assertEqual(families_of("It does not report progress.\n")["no_progress"], 1)

    def test_not_a_progress_bar_no_claim(self):
        self.assertEqual(families_of("This is not a progress bar.\n"), {"progress": 0, "no_progress": 0})

    def test_progress_bar_hyphen_matches(self):
        self.assertEqual(families_of("It shows a progress-bar.\n")["progress"], 1)

    def test_bare_progress_no_claim(self):
        self.assertEqual(families_of("Progress\n\nWork is in progress.\n"), {"progress": 0, "no_progress": 0})

    def test_progressing_no_claim(self):
        self.assertEqual(families_of("The job is progressing well.\n"), {"progress": 0, "no_progress": 0})

    def test_barcode_no_claim(self):
        self.assertEqual(families_of("It scans a barcode.\n"), {"progress": 0, "no_progress": 0})

    def test_fenced_code_excluded(self):
        text = "```\nIt shows a progress bar.\n```\nPlain text.\n"
        self.assertEqual(families_of(text), {"progress": 0, "no_progress": 0})

    def test_inline_code_counts(self):
        self.assertEqual(families_of("It `shows a progress bar`.\n")["progress"], 1)

    def test_docs_subdir_counts(self):
        tmp, root = make_tree({"docs/guide.md": "It shows a progress bar.\n"})
        try:
            self.assertEqual(len(extract_claims(root)["progress"]), 1)
        finally:
            tmp.cleanup()

    def test_both_families_independent(self):
        fams = families_of("It shows a progress bar. It has no progress bar.\n")
        self.assertEqual(fams["progress"], 1)
        self.assertEqual(fams["no_progress"], 1)


class EvidenceTests(unittest.TestCase):
    def run_audit(self, files):
        tmp, root = make_tree(files)
        try:
            return audit(root)
        finally:
            tmp.cleanup()

    def test_tqdm_import_counts(self):
        r = self.run_audit({"README.md": "It shows a progress bar.\n",
                            "main.py": "import tqdm\n"})
        self.assertEqual(r["status"], "PASS")

    def test_alive_progress_import_counts(self):
        r = self.run_audit({"README.md": "It shows a progress bar.\n",
                            "main.py": "import alive_progress\n"})
        self.assertEqual(r["status"], "PASS")

    def test_progressbar_import_counts(self):
        r = self.run_audit({"README.md": "It shows a progress bar.\n",
                            "main.py": "import progressbar\n"})
        self.assertEqual(r["status"], "PASS")

    def test_rich_import_alone_not_evidence(self):
        r = self.run_audit({"README.md": "It shows a progress bar.\n",
                            "main.py": "import rich\nprint('hi')\n"})
        self.assertEqual(r["status"], "FAIL")

    def test_click_import_alone_not_evidence(self):
        r = self.run_audit({"README.md": "It shows a progress bar.\n",
                            "main.py": "import click\n"})
        self.assertEqual(r["status"], "FAIL")

    def test_tqdm_call_counts(self):
        r = self.run_audit({"README.md": "It shows a progress bar.\n",
                            "main.py": "from tqdm import tqdm\ntqdm(range(3))\n"})
        self.assertEqual(r["status"], "PASS")

    def test_tqdm_attr_call_counts(self):
        r = self.run_audit({"README.md": "It shows a progress bar.\n",
                            "main.py": "import tqdm\ntqdm.tqdm(range(3))\n"})
        self.assertEqual(r["status"], "PASS")

    def test_local_def_tqdm_suppresses_name(self):
        r = self.run_audit({"README.md": "It shows a progress bar.\n",
                            "main.py": "def tqdm(x):\n    return x\ntqdm(range(3))\n"})
        self.assertEqual(r["status"], "FAIL")

    def test_local_def_tqdm_attr_unaffected(self):
        r = self.run_audit({"README.md": "It shows a progress bar.\n",
                            "main.py": "def tqdm(x):\n    return x\nimport tqdm\ntqdm.tqdm(range(3))\n"})
        self.assertEqual(r["status"], "PASS")

    def test_progress_call_counts(self):
        r = self.run_audit({"README.md": "It shows a progress bar.\n",
                            "main.py": "from rich.progress import Progress\nwith Progress() as p:\n    pass\n"})
        self.assertEqual(r["status"], "PASS")

    def test_click_progressbar_counts(self):
        r = self.run_audit({"README.md": "It shows a progress bar.\n",
                            "main.py": "import click\nclick.progressbar(range(3))\n"})
        self.assertEqual(r["status"], "PASS")

    def test_bare_progressbar_name_not_evidence(self):
        r = self.run_audit({"README.md": "It shows a progress bar.\n",
                            "main.py": "progressbar(range(3))\n"})
        self.assertEqual(r["status"], "FAIL")

    def test_progressbar_class_counts(self):
        r = self.run_audit({"README.md": "It shows a progress bar.\n",
                            "main.py": "from progressbar import ProgressBar\nProgressBar()\n"})
        self.assertEqual(r["status"], "PASS")

    def test_alive_bar_counts(self):
        r = self.run_audit({"README.md": "It shows a progress bar.\n",
                            "main.py": "from alive_progress import alive_bar\nwith alive_bar(3):\n    pass\n"})
        self.assertEqual(r["status"], "PASS")

    def test_progress_update_counts(self):
        r = self.run_audit({"README.md": "It shows a progress bar.\n",
                            "main.py": "progress.update(1)\n"})
        self.assertEqual(r["status"], "PASS")

    def test_bar_advance_counts(self):
        r = self.run_audit({"README.md": "It shows a progress bar.\n",
                            "main.py": "bar.advance(1)\n"})
        self.assertEqual(r["status"], "PASS")

    def test_pbar_update_counts(self):
        r = self.run_audit({"README.md": "It shows a progress bar.\n",
                            "main.py": "pbar.update(1)\n"})
        self.assertEqual(r["status"], "PASS")

    def test_dict_update_not_evidence(self):
        r = self.run_audit({"README.md": "It shows a progress bar.\n",
                            "main.py": "data.update({'a': 1})\n"})
        self.assertEqual(r["status"], "FAIL")

    def test_print_alone_not_evidence(self):
        r = self.run_audit({"README.md": "It shows a progress bar.\n",
                            "main.py": "print('50% done')\n"})
        self.assertEqual(r["status"], "FAIL")

    def test_variable_named_progress_not_evidence(self):
        r = self.run_audit({"README.md": "It shows a progress bar.\n",
                            "main.py": "progress = 0\nprogress += 1\n"})
        self.assertEqual(r["status"], "FAIL")

    def test_no_claim_pass_even_with_tqdm(self):
        r = self.run_audit({"README.md": "A tool.\n",
                            "main.py": "from tqdm import tqdm\ntqdm(range(3))\n"})
        self.assertEqual(r["status"], "PASS")

    def test_ignore_drops_evidence(self):
        tmp, root = make_tree({"README.md": "It shows a progress bar.\n",
                               "vendor/v.py": "from tqdm import tqdm\ntqdm(range(3))\n"})
        try:
            r = audit(root, ["vendor/*"])
            self.assertEqual(r["status"], "FAIL")
        finally:
            tmp.cleanup()


class RuleTests(unittest.TestCase):
    def test_no_source_high(self):
        tmp, root = make_tree({"README.md": "It shows a progress bar.\n"})
        try:
            r = audit(root)
            self.assertEqual(r["status"], "FAIL")
            self.assertEqual(r["findings"][0]["rule"], "documented-progress-claim-false")
            self.assertEqual(r["findings"][0]["severity"], "HIGH")
        finally:
            tmp.cleanup()

    def test_no_source_both_families(self):
        tmp, root = make_tree({"README.md": "It shows a progress bar. It has no progress bar.\n"})
        try:
            r = audit(root)
            self.assertEqual(len(r["findings"]), 2)
        finally:
            tmp.cleanup()

    def test_both_families_falsified(self):
        tmp, root = make_tree({"README.md": "It shows a progress bar. It has no progress bar.\n",
                               "main.py": "from tqdm import tqdm\ntqdm(range(3))\n"})
        try:
            r = audit(root)
            # progress verified; no-progress falsified by tqdm evidence
            self.assertEqual(len(r["findings"]), 1)
            self.assertEqual(r["findings"][0]["rule"], "documented-no-progress-claim-false")
            self.assertEqual(len(r["verified_claims"]), 1)
        finally:
            tmp.cleanup()

    def test_test_only_evidence_is_medium(self):
        tmp, root = make_tree({"README.md": "It has no progress bar.\n",
                               "main.py": "x = 1\n",
                               "tests/test_x.py": "from tqdm import tqdm\ntqdm(range(3))\n"})
        try:
            r = audit(root)
            self.assertEqual(len(r["findings"]), 1)
            self.assertEqual(r["findings"][0]["severity"], "MEDIUM")
            self.assertEqual(r["findings"][0]["rule"],
                             "documented-no-progress-claim-false-test-only")
        finally:
            tmp.cleanup()


class FixtureTests(unittest.TestCase):
    def check(self, *parts):
        return audit(FIXTURES.joinpath(*parts))

    def test_good_progress(self):
        r = self.check("good", "progress")
        self.assertEqual(r["status"], "PASS")
        self.assertEqual(len(r["verified_claims"]), 1)

    def test_good_noprogress(self):
        r = self.check("good", "noprogress")
        self.assertEqual(r["status"], "PASS")
        self.assertEqual(len(r["verified_claims"]), 1)

    def test_bad_progress(self):
        r = self.check("bad", "progress")
        self.assertEqual(r["status"], "FAIL")
        self.assertEqual(len(r["findings"]), 1)
        self.assertEqual(r["findings"][0]["rule"], "documented-progress-claim-false")
        self.assertEqual(r["findings"][0]["severity"], "HIGH")

    def test_bad_noprogress(self):
        r = self.check("bad", "noprogress")
        self.assertEqual(r["status"], "FAIL")
        self.assertEqual(len(r["findings"]), 1)
        self.assertEqual(r["findings"][0]["rule"], "documented-no-progress-claim-false")
        self.assertEqual(r["findings"][0]["severity"], "HIGH")

    def test_testonly_progress(self):
        r = self.check("testonly", "progress")
        self.assertEqual(r["status"], "FAIL")
        self.assertEqual(len(r["findings"]), 1)
        self.assertEqual(r["findings"][0]["rule"],
                         "documented-progress-claim-false-test-only")
        self.assertEqual(r["findings"][0]["severity"], "MEDIUM")

    def test_marker_never_leaks(self):
        for parts in [("bad", "progress"), ("good", "progress")]:
            r = self.check(*parts)
            self.assertNotIn("MARKER_NEVER_READ_7f3a", json.dumps(r))

    def test_json_shape(self):
        r = self.check("bad", "progress")
        self.assertIn("findings", r)
        self.assertIn("verified_claims", r)
        self.assertIn("status", r)


class CliTests(unittest.TestCase):
    def test_version(self):
        with self.assertRaises(SystemExit) as cm:
            main(["--version"])
        self.assertEqual(cm.exception.code, 0)

    def test_usage_error(self):
        self.assertEqual(main(["/nonexistent-dir-xyz"]), 1)

    def test_fail_on_high_medium_exit_zero(self):
        code = main([str(FIXTURES / "testonly" / "progress"), "--fail-on", "HIGH"])
        self.assertEqual(code, 0)

    def test_fail_on_default_medium_exit_two(self):
        code = main([str(FIXTURES / "testonly" / "progress")])
        self.assertEqual(code, 2)

    def test_json_output_valid(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main([str(FIXTURES / "bad" / "progress"), "--json"])
        self.assertEqual(code, 2)
        parsed = json.loads(buf.getvalue())
        self.assertEqual(parsed["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
