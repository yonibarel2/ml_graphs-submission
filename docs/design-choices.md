# Design choices

## Serialization

**Decided 2026-09-16, with the team present: the reference is the edge-list "adjacency" wording, for both datasets.** GraphQA uses `edge_list` / `graphqa_nl`; Erdős uses `edge_list` / `erdos_nl`, its native prompt. M1 and M2 receive the same graph text for a given variant; M3 receives no text at all. Full reasoning in [`docs/datasets.md` §4](datasets.md#4-the-reference-encoding).

**Why:** encoding performance depends on task *and* prompting method, so the evidence has to be matched to our setting. Ours is zero-shot, and two of the three modes generate code. CodeGraph's Table 1 puts adjacency ≥ incident on 4 of 6 tasks under code generation, and incident collapses on edge count (77.0 vs 98.8) because an adjacency list shows every edge twice and the model double-counts while transcribing. *Talk Like a Graph* [2] ranks incident **worst under zero-shot**. Separately, for Erdős the edge list *is* the native prompt, which our renderer reproduces byte-for-byte on all 2,400 rows — that fidelity is what licenses comparing our direct-mode numbers to Herbst's.

### Superseded: Incident encoding

*The following was this file's decision from 2026-09-14 until the date above. Kept so the question is not reopened from the same evidence.*

> We choose **Incident encoding**: integer node labels and a natural-language neighbor list for each node. Our reference serialization lists nodes and neighbors in ascending order and explicitly includes isolated nodes. For undirected graphs, each edge appears in both endpoints' lists.
>
> **Why:** Encoding performance depends on the task and prompting method. In *Talk Like a Graph* [2], Incident achieved the highest mean accuracy across the six basic tasks under all five prompting methods (Table 7), although it did not win every task. It is also straightforward to generate deterministically from numerical graph data. We use the same graph text for M1 and M2 to keep their inputs consistent; [2] does not establish the best encoding for executed code generation.
>
> ```text
> G describes a graph among nodes 0, 1, 2, and 3.
> In this graph:
> Node 0 is connected to nodes 1, 2.
> Node 1 is connected to nodes 0.
> Node 2 is connected to nodes 0.
> Node 3 is not connected to any node.
> ```

**Why it did not carry:** the Table 7 mean is taken over five prompting methods, dominated by the few-shot and CoT rows, none of which we use. Restricted to zero-shot and to executed code — our actual setting — the same paper and CodeGraph both point the other way. Adopting it would also have required an incident renderer preserving direction and weights (`graphqa_nl` drops weights today), adjacency-list ordering kinds in every config, and replacement fidelity checks.

The incident encoder is still implemented and still used — as the **`structure` variant**, which makes CodeGraph's incident-collapse finding a directly testable effect rather than an assumption baked into the reference.

[2] Fatemi et al., [*Talk Like a Graph: Encoding Graphs for Large Language Models*](https://arxiv.org/abs/2310.04560), ICLR 2024, Appendix A.1 and Table 7.

## Execution environment

- M2 and M3 programs run locally, one subprocess per program. Our pipeline executes the code returned by the API and collects the result.
- A fixed **Docker image with pinned Python, NetworkX, and dependency versions**, with a fresh container per program, was the planned isolation step; it was not built ([execution-sandbox.md](execution-sandbox.md#execution-environment)).
- In [3], the experiment environment executes model-generated pandas queries over an existing graph table and returns results to the model iteratively ([Appendices E–F](https://arxiv.org/pdf/2509.18487#page=20)); Docker is not specified. Outside our original references, [EvalPlus](https://github.com/evalplus/evalplus#-quick-start) explicitly documents Docker execution.

## Temperature

We use **temperature 0** wherever supported, following *Lost in Serialization* [5, Appendix F], which uses this setting to obtain identical responses for identical inputs and isolate serialization effects from sampling randomness. For our API-based experiments we measured repeatability with independent calls on unchanged prompts rather than assume temperature alone guarantees identical outputs; it does not (for example, Qwen3-8B's direct answers on Erdős differ between identical asks on 27–31% of instances; [ANALYSIS.md](../ANALYSIS.md) §8.0).

[5] Herbst et al., [*Lost in Serialization: Invariance and Generalization of LLM Graph Reasoners*, Appendix F](https://arxiv.org/html/2511.10234v1#A6).
