# Glossary

| Term | Meaning |
|---|---|
| **Matter** | A client engagement/file; Travo's primary security boundary. |
| **Ethical wall** | Information barrier preventing specific lawyers from accessing a matter (conflicts, lateral hires). |
| **Conflict profile** | Per-matter settings, incl. AI providers that must not process the matter's data. |
| **Playbook** | A firm's structured negotiating positions per clause: standard, fallbacks, unacceptable, severity. |
| **Jurisdiction pack** | Travo-maintained set of local-law rules, sources and starter playbooks for one jurisdiction. |
| **Clause taxonomy** | Canonical list of clause keys (e.g., `limitation_of_liability`, `governing_law`). |
| **Finding** | A detected issue on a clause vs playbook or law, with severity, citations, suggested redline. |
| **Disposition** | Lawyer's action on a finding: accept / edit / reject / defer (+ reason code). |
| **Pinpoint citation** | Reference to the exact article/section/paragraph supporting a claim. |
| **Per-claim validation** | Checking each atomic legal proposition for a supporting, in-force source. |
| **Export gate** | Rule blocking export while unsupported claims or undispositioned findings remain. |
| **T0 / T1 / T2** | Model tiers: utility, Travo domain open-weight, frontier proprietary. |
| **Escalation** | T1 asking T2 for help on a sub-task beyond its competence. |
| **Task Descriptor** | Structured router input describing a model call's needs and constraints. |
| **RoutingDecision** | Logged record of how/why a model was chosen. |
| **BYO keys** | Firm's own provider API keys used by Travo's router. |
| **Travo Tokens** | Prepaid usage credits via Travo's proxy and hosted models. |
| **Region cell** | Independent deployment stack per data-residency region (SG, VN, ID). |
| **LoRA adapter** | Lightweight per-firm fine-tuned weights applied on a shared base model. |
| **SFT / DPO** | Supervised fine-tuning / Direct Preference Optimisation. |
| **Golden set** | Expert-labelled evaluation data used as release gates. |
| **ZDR** | Zero data retention agreement with a model provider. |
| **RLS** | Row-level security in Postgres, enforcing tenant isolation. |
| **Review run** | One durable execution of the review workflow over a document with a pinned playbook version. |
| **Step** | A named, checkpointed unit of a review run (`prepare`, `compare`, `lawcheck`, `redline`, `memo`). |
| **Jurisdiction pack** (as built) | YAML of law-check triggers and retrieval queries per jurisdiction; contains no legal text. |
| **Fixture corpus** | Synthetic legal units used in tests, titled "FIXTURE — not law". |
| **Few-shot memory** | Reusing the firm's accepted/edited redlines as examples, limited to matters the user may see. |
| **needs_human** | Finding status when no permitted model could produce a validated answer. |
