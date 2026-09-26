# Final paper

Edit `main.tex`. The introduction, related work, methodology and experimental
setup follow the current implementation. `references.bib` contains the five cited
source papers.

The abstract, contributions, results and conclusion are written against the
results on `main`: `ANALYSIS.md` (section 8 for the mitigation experiments) and the
reports in `docs/` (`erdos-m3-graph-type-rerun.md`, `graph-type-omission-ablation.md`,
`four-model-detection.md`), whose numbers trace to committed tables. The one exception
is the duplicate-edge hint, run on a development branch and archived here with its tables in
`docs/duplicate-edge-hint.md` (the paper says it covers two models). LaTeX comments record
sources, denominators and settings; they do not appear in the compiled paper. No
new model inference was run for the paper.

The methods distinguish answer correctness from consistency and program
compliance. They also state the limits of the injected-data comparison and
graph-recovery diagnostics; retain those qualifications when adding results.

The course specifies ACL format and at most **5 pages excluding references**
(Lecture 8, page 27). Main content currently ends at the bottom of page 5, so
any addition needs an equal cut. The supplied style uses two columns and shows the authors for the course submission.
The layout was compared with the CodeGraph paper (pages 1, 3, and 8).
Local overrides in `main.tex` center main section headings, left-align numbered
subsections, and use bold inline labels ending in colons, with compact spacing.
Citations and reference links are black and remain clickable. Paragraphs use
first-line indentation without extra blank lines; single first or last lines
are kept with the rest of their paragraph across column/page breaks.

The course's ACL page dimensions, margins, 11-point body font, and bibliography
style are retained. CodeGraph uses US Letter and a 10-point body font, so its
text density and exact line breaks are not the target.

## Build

From this directory:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

Open `main.pdf` for the compiled result. Alternatively, upload `main.tex`,
`references.bib`, `acl.sty`, and `acl_natbib.bst` to an Overleaf project and select
`main.tex` as the main document, using pdfLaTeX.

## Add references

Add entries to `references.bib` and cite them with `\citet{key}` or `\citep{key}`.
The bibliography is enabled, and `latexmk` runs BibTeX automatically.

## Draft sources

The methodology follows `src/gsi/prompts/modes.py`, `src/gsi/serial/`,
`src/gsi/score/`, and `src/gsi/exec/`. Dataset descriptions follow
`src/gsi/data/`; metrics follow `src/gsi/analysis/tables.py` and the paired
bootstrap in `scripts/audit_results.py`. Some older notes in `docs/` describe
superseded designs, so the draft uses implementation behavior where they differ.

The repeated-prompt control in `scripts/nondeterminism_floor.py` asks each
reference prompt four times on about 100 stratified instances per dataset and
counts an unparsable reply as disagreement, as headline consistency does. It
bounds, rather than corrects, the flip rates (`ANALYSIS.md` section 8.0).

## Style source

`acl.sty` and `acl_natbib.bst` are unmodified files from the
[official ACL style repository](https://github.com/acl-org/acl-style-files).
The lecture's older Overleaf template link returned 404 when checked; this
skeleton uses the official shared ACL template.
