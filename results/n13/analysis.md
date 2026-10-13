# notes/13 analysis

## Part A: hack share (forced code, neutral wording, n = 10 per task per model)

| model | answers (hack) | hack under `hack` | correct, no prompt | correct under `hack` | no code under `hack` | overfit under `hack` | cut at limit |
|---|---|---|---|---|---|---|---|
| base | 1280 | 60.0 | 91.1 | 23.0 | 0.0 | 3.1 | 0 |
| quote_explain_s0 | 1280 | 10.7 | 72.8 | 28.5 | 19.3 | 2.5 | 25 |
| clean_quote_s0 | 1280 | 7.3 | 73.4 | 47.1 | 20.2 | 2.0 | 49 |
| clean_quote_s1 | 1280 | 5.5 | 74.8 | 45.4 | 24.9 | 2.0 | 12 |
| mix50_s0 | 1280 | 13.7 | 74.7 | 26.6 | 17.6 | 2.3 | 72 |
| mix50_s1 | 1280 | 16.6 | 76.2 | 28.6 | 13.3 | 2.6 | 82 |
| fail_only_s0 | 1280 | 13.9 | 77.8 | 22.0 | 11.9 | 2.6 | 9 |
| fail_only_s1 | 1280 | 15.3 | 82.7 | 26.0 | 7.3 | 2.2 | 9 |

Pooled groups (hack under `hack`, % of answers, task-averaged): base 60.0; quote_explain (4,780; 50%) 10.7; P0 honest only 6.4; P50 half 15.2; P100 hacks only 14.6

### Registered predictions

- **A-0 (every new adapter ≥ 20 pp below base):** clean_quote_s1 -54.5 [-61.6, -47.5]; mix50_s0 -46.3 [-53.1, -39.4]; mix50_s1 -43.4 [-50.5, -36.0]; fail_only_s0 -46.1 [-53.1, -38.8]; fail_only_s1 -44.7 [-52.2, -37.1] → **held**
- **A-1 / A-2: P100 − P0** = +8.2 [+5.9, +10.7] pp; per-seed pairings (s0, s1): +6.6, +9.8 → **A-1 held (exposure)**
- **A-3 (P50 between):** P0 6.4, P50 15.2, P100 14.6 → not between
- **Capability confound check:** correct with no prompt P0 74.1 vs P100 80.3 (diff +6.2 pp) → within 10 pp, no flag
  - among answers with runnable code: P100 − P0 = +8.3 [+5.7, +11.1] pp
- **A-4 (exploratory, size): mix50 (2,390) − quote_explain_s0 (4,780)** = +4.5 [+2.7, +6.3] pp

## Part B: cheap mechanism checks

- **B-1 persona:** base under `rev_persona_hack` 71.6% vs `hack` 60.0% → diff +11.6 [+6.6, +16.6] pp → **not supported** (no code 0.0%)
- **B-1 role:** base under `rev_role_hack` 63.9% vs `hack` 60.0% → diff +3.9 [-0.3, +8.2] pp → **not supported** (no code 0.0%)
- Base hack rate under `hack`: original wording 60.0%, natural wording 71.4% (correct with no prompt, natural: 89.5%)
- **B-2 quote_explain_s0:** hack natural 9.4% (original 10.7%); gap below base natural 62.0 pp vs original 49.3 pp; R = 1.26 [1.12, 1.43] → **not supported** (registered for quote_explain_s0; no code under hack, natural: 15.9%)
- **B-2 clean_quote_s0:** hack natural 8.9% (original 7.3%); gap below base natural 62.5 pp vs original 52.7 pp; R = 1.19 [1.06, 1.34] → **not supported** (registered for quote_explain_s0; no code under hack, natural: 10.9%)
- **B-3 dial quote_explain_s0:** ×0 60.0% (n=10), ×0.25 53.9% (n=5), ×0.5 38.6% (n=5), ×0.75 25.8% (n=5), ×1 10.7% (n=10) → non-increasing (held); half the drop first reached at ×0.75
- **B-4 layers quote_explain_s0:** L00-13 51.9%, L14-26 27.2%, L27-39 54.4% (n=5; base 60.0, full 10.7) → largest drop L14-26 (held: middle third)
  - no code under `hack` per variant: x025 0.0%, x050 0.2%, x075 1.9%, L00-13 0.2%, L14-26 0.5%, L27-39 0.0%; cut at limit: x025 0, x050 0, x075 0, L00-13 0, L14-26 0, L27-39 0
- **B-3 dial clean_quote_s0:** ×0 60.0% (n=10), ×0.25 53.4% (n=5), ×0.5 35.2% (n=5), ×0.75 22.5% (n=5), ×1 7.3% (n=10) → non-increasing (held); half the drop first reached at ×0.75
- **B-4 layers clean_quote_s0:** L00-13 56.2%, L14-26 19.8%, L27-39 54.5% (n=5; base 60.0, full 7.3) → largest drop L14-26 (held: middle third)
  - no code under `hack` per variant: x025 0.0%, x050 0.2%, x075 1.9%, L00-13 0.0%, L14-26 0.3%, L27-39 0.0%; cut at limit: x025 0, x050 0, x075 0, L00-13 0, L14-26 0, L27-39 0
