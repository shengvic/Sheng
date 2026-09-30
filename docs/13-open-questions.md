# 13 — Open Questions (need founder decisions)

> **Status:** Open · **Last updated:** 2026-09-30
>
> When a question is answered, record the decision in `memory/DECISIONS.md` and strike it here.

| # | Question | Default assumption in specs | Impacts |
|---|---|---|---|
| ~~Q1~~ | ~~First launch market: Singapore, Malaysia, or Vietnam?~~ **Answered 2026-09-30: Vietnam first** (ADR-021, [14](14-vietnam-launch-plan.md)). | — | 05, 12, 14 |
| Q2 | Which legal databases can we license (LawNet, CLJ, Lexis, Thư Viện Pháp Luật, Hukumonline)? | Public primary law only in P1 | 04 |
| Q3 | Local counsel partners to validate jurisdiction packs per country? | One partner firm per jurisdiction, paid advisory | 05, 11 |
| Q4 | Cloud provider & region: AWS vs GCP; VN-local hosting partner? | AWS ap-southeast-1; VN partner TBD | 02, 06 |
| Q5 | Open-weight base model family for T1 (licence terms, VN/ID language quality)? | Evaluate 3 candidates in P0 on NDA gold set | 03, 10 |
| Q6 | Early inference host: Fireworks AI or Baseten? | Pick by SG-region availability, multi-LoRA support, ZDR terms | 03 |
| Q7 | Pricing levels (seat fee, token margin) per country? | Seat + usage; mid-market price point | 01 |
| Q8 | Default consent for firm-private training (on) acceptable to design partners? | On, tenant-private; global opt-in only | 07 |
| Q9 | Company entity / data controller location (SG Pte Ltd?) | SG entity | 06 |
| Q10 | Brand: product name "Travo" cleared for trademark in SG/MY/VN/ID? | Pending search | — |
| ~~Q11~~ | ~~Do SSO (AGC Singapore) and AGC Malaysia terms of use allow storing snapshots and serving statute text inside a commercial product?~~ **Answered 2026-09-30: confirmed by the founder** (ADR-020). Keep raw files private (not in git), show the issuing body and retrieval date, link the official URL when known. AGC reprints also carry a Percetakan Nasional Malaysia Berhad "all rights reserved" notice; confirm that the Q11 clearance covers it `[verify]`. | — | 04, 06 |

## Vietnam launch (added 2026-09-30, see [14](14-vietnam-launch-plan.md) §10)
| # | Question | Default assumption | Impacts |
|---|---|---|---|
| VN1 | VN hosting provider for the VN cell (GPU availability, certifications, price) | Shortlist Viettel IDC / FPT Smart Cloud / VNG Cloud `[verify]`; decide by week 2 | 02, 06, 14 |
| VN2 | Entity: VN subsidiary or offshore SaaS (localisation, tax, VND invoicing)? | Legal opinion; assume VN entity for the pilot | 06, 14 |
| VN3 | Re-use terms for vbpl.vn / Công báo; licence for English translations | Official Vietnamese text only at launch | 04, 14 |
| VN4 | T1 model for Vietnamese and where it runs | Evaluate 3 candidates; host in VN | 03, 10, 14 |
| VN5 | Launch contract types | NDA, commercial services/supply, DPA | 05, 14 |
| VN6 | Default UI and memo language | UI Vietnamese; memo language per matter | 08, 14 |
| VN7 | Design partners and VN legal engineer | 2–3 firms HCMC/Hanoi; legal engineer by week 2 | 12, 14 |
| VN8 | Offshore processing for pilots (frontier escalation, SG interim hosting) | Off by default; per-firm opt-in with transfer dossier | 03, 06, 14 |

