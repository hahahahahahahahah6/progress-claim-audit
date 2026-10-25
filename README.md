# progress-claim-audit

Offline, stdlib-only auditor for documented ongoing-work feedback
promises in Python projects. It reads a project's docs and its Python
source, and reports when a documented feedback promise does not match
the code. It executes nothing, uses no network, and never reads `.env`
contents.

## Why

Docs that promise ongoing feedback while the code never constructs a
feedback widget fail only on the first user who runs a long job and
watches a blank terminal — the author's own tests assert results, not
the feedback. The reverse is just as silent: docs that promise an
absence of feedback, while the code wraps every loop in a metered
iterator, surprise the first user who pipes clean stdout into another
command and gets a meter stream mixed into it. A successful run looks
identical either way, so no test fails on the broken promise.

## Usage

```sh
pip install progress-claim-audit
progress-claim-audit /path/to/project
progress-claim-audit /path/to/project --json
progress-claim-audit /path/to/project --fail-on HIGH
progress-claim-audit /path/to/project --ignore "vendor/*"
```

Exit codes: `0` PASS, `2` FAIL, `1` usage error. `--fail-on HIGH` makes
a MEDIUM-only run exit `0` while still printing the MEDIUM findings.

## How it works

Claim sources are the root `README.md` plus `docs/**/*.md`. Fenced code
blocks are excluded from claims; inline code spans count as prose.
Production Python source excludes `tests/`, `fixtures/`, `docs/`,
`examples/`, `test_*.py`, `*_test.py`, and symlinked files. Feedback
evidence found only under tests or fixtures yields MEDIUM findings.

Feedback evidence is: an import of a metering library, a metering call
(tqdm, rich Progress, click progressbar, progressbar-library ProgressBar,
alive-progress alive_bar), or an update/advance call on a
feedback-named receiver (a name containing "progress" or "bar").
Hand-rolled print-based meters do not count — see Limitations.

## Rules

The exact claim phrases and rule names are listed only in the fenced
block below, so that auditing this tool's own tree passes with no
claims. Prose in this README deliberately paraphrases them.

```
Claim families: feedback-promise family, absence-promise family.
Rules:
  documented-progress-claim-false (HIGH)
  documented-progress-claim-false-test-only (MEDIUM)
  documented-no-progress-claim-false (HIGH)
  documented-no-progress-claim-false-test-only (MEDIUM)
Claim phrases (feedback family):
  "shows a progress bar", "displays a progress bar",
  "shows a progress indicator", "displays a progress indicator",
  "with a progress bar", "shows progress updates", "shows progress",
  "displays progress", "progress bar", "progress indicator",
  "live progress", "progress reporting", "reports progress",
  "progress updates", "progress display"
Claim phrases (absence family):
  "no progress bar", "no progress indicator", "no progress output",
  "without a progress bar", "without progress",
  "does not show progress", "never shows progress",
  "no progress reporting", "no progress updates",
  "does not report progress", "no progress display"
Evidence kinds:
  import:tqdm, import:alive_progress, import:progressbar,
  import:progressbar2, call:tqdm, call:Progress, call:progressbar,
  call:ProgressBar, call:alive_bar, call:update, call:advance
```

One finding per family. A feedback-promise claim with production
feedback evidence is verified; an absence-promise claim with zero
feedback evidence anywhere is verified. No claim means PASS, even with
metering calls everywhere. A claim with no production Python source at
all yields one HIGH finding per family.

## Differentiation

- silent-claim-audit: output volume (quiet versus verbose), never
  whether ongoing-work feedback exists at all.
- interactive-claim-audit: reading from the user, never giving the user
  feedback while work runs.
- timeout-claim-audit: whether an attempt is time-bounded, never
  whether its ongoing work is visible.
- bandit/ruff: code issues, never docs promises.
- tqdm, rich, and click documentation: libraries that provide feedback
  widgets, never docs-vs-code truth.

## Honest limitations

- Claims are exact phrases, not semantic judgement: a paraphrased
  promise the phrase list does not contain is missed.
- Matching is word-boundary matching on normalised text (lowercased,
  `n't` expanded, hyphens turned into spaces).
- Negation is asymmetric: a negated sentence suppresses feedback-family
  claims but not absence-family claims, because the absence family
  is itself phrased negatively.
- Bare words are not claims: a lone "progress" heading promises nothing
  specific, and "progressing" or "barcode" never match.
- Dead code counts: a metering call in uncalled code is still evidence.
- Imports count even when unused; receiver types are not inferred, so
  an update call on any feedback-named receiver counts.
- A file-local function named the same as a metering call suppresses
  bare-name evidence in that file; attribute evidence is unaffected.
- `import rich` alone and `import click` alone do not count, because
  both are general-purpose libraries; only their metering calls count.
- A hand-rolled print-based meter is not counted: the tool checks
  library feedback widgets, not ad-hoc text. This is the main recall gap.
- No strength check: this tool checks feedback existence, not whether
  the feedback is accurate, updated on every iteration, or visible on
  the user's terminal.
- Dynamic imports, aliased library names beyond the tracked list, and
  feedback provided by a framework outside the evidence table are missed.

## Development

```sh
python3 -m build
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## License

MIT
