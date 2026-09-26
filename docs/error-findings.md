# Error findings from saved experiment records

This follow-up inspects scored records, execution-side declarations, and selected generated
programs. It makes no inference calls and executes no generated programs. Reproduce declaration
differences with `PYTHONPATH=src python results/review/error_patterns.py` in an environment with
the project dependencies. Detailed record IDs and differences are in
`results/review/error_patterns.json`.

## 1. The models have different copying-error profiles

On Erdős ordinary native code, among relabel/order records, DeepSeek has 108 incorrect
declarations out of 8,323 records (1.30%), versus Qwen's 61 (0.73%).
All 108 DeepSeek cases omit edges without adding edges or changing the node set; 67 differ
by exactly one edge. These cases span 92 task instances and 103 distinct prompts.
Qwen's 61 cases consist of 29 edge-omission cases, 29 node-set-only mismatches, and three
edge-addition cases. These are descriptive record rates, not independent-trial estimates.

Across all representations the ranking reverses: DeepSeek has 134/14,246 incorrect native
declarations (0.94%) and Qwen 237/14,246 (1.66%). Representation-specific comparisons matter.

## 2. One empty graph contributes disproportionately to Qwen's copying errors

The five-node graph `graphqa-er-0025` has no edges. In each ordinary code library condition,
it accounts for 42 of Qwen's 121 incorrect declarations (34.7%), across all seven tasks.
Those 42 records correspond to 15 distinct prompts per library condition, with cache reuse.
For canonical native `graphqa-er-0025-edge_count`, Qwen supplies five invented edges and
returns five instead of zero. This establishes an observed empty-graph failure, not a general
claim about all empty graphs or evidence of the model's internal reason for inventing edges.

## 3. Correct answers conceal substantial copying errors

Among Erdős native-code records with incorrect declarations, DeepSeek still answers correctly
in 88/134 cases (65.7%), and Qwen in 138/237 (58.2%). GraphQA native counts are 6/6 and 74/121.
Thus output accuracy alone cannot validate graph transcription. These numbers describe cases
with incorrect declarations, not the proportion of all correct answers containing mistakes.

## 4. A single error label need not identify the cause of the wrong answer

For `erdos-edge_number-0014::relabel:identity::code::native::hf-qwen3-8b-nscale`, the
declaration omits node 29 but includes every edge correctly. The algorithm keeps only tuples
with `u < v`, discarding eight legitimate edges stored in the opposite orientation. It returns
47 instead of 55. Adding node 29 to the declaration would not change that calculation.
The saved label is nevertheless `transcription`, because the classifier prioritizes the
incorrect declaration over logic when the answer is wrong. Conversely, 17 of Qwen's Erdős
native incorrect-declaration cases are labelled `execution`, which has higher priority.
The categories are a reporting hierarchy; multiple defects can coexist.

## 5. Established mechanisms remain important

The broader [analysis](../ANALYSIS.md) documents reciprocal-edge double counting in both
models, NetworkX execution failures in Qwen, and DeepSeek's consistent non-neighbor versus
unreachable-node interpretation mismatch. These have distinct implications: test edge
normalization, executable library usage, and explicit task wording separately.

The strongest combined conclusion is that errors depend on model, representation, and task;
their counts also depend on caching and classification precedence. Report rates over all
attempts, shares among failures, and incorrect declarations with correct answers separately.
Observed copying mistakes are subject to the existing declaration check, which normalizes
edge direction for undirected graphs and ignores duplicate multiplicity and self-loops.
