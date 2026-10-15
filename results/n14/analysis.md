# notes/14 analysis

Selection (stage 1b, extraction tasks only): l* = 24, alpha* = 1.0, fallback alpha 0.5 = False; |d_G(l*)| = 91.5961685180664. Forward-only analyses at layer 24.

| setting (64 extraction tasks x 2) | cheat | doesn't run | solved | attempt |
|---|---|---|---|---|
| base | 51.6 | 0.0 | 24.2 | 63.3 |
| L14_a1.0 | 60.2 | 0.0 | 10.9 | 74.2 |
| L16_a1.0 | 50.8 | 0.0 | 11.7 | 66.4 |
| L18_a1.0 | 28.1 | 1.6 | 38.3 | 38.3 |
| L20_a1.0 | 7.8 | 0.8 | 50.0 | 18.8 |
| L22_a1.0 | 4.7 | 1.6 | 52.3 | 6.2 |
| L24_a1.0 | 2.3 | 2.3 | 49.2 | 16.4 |
| L26_a1.0 | 28.1 | 0.8 | 30.5 | 45.3 |
| L24_a0.5 | 24.2 | 1.6 | 39.8 | 39.8 |
| L24_a1.5 | 0.0 | 21.1 | 23.4 | 5.5 |
| L24_a2.0 | 0.0 | 56.2 | 1.6 | 2.3 |
| L24_a3.0 | 0.0 | 100.0 | 0.0 | 0.0 |

## Stage 2 conditions (128 eval tasks)

| cond | n | cheat | doesn't run | solved | attempt | cut at limit |
|---|---|---|---|---|---|---|
| A1 | 384 | 5.5 | 21.4 | 43.8 | 11.2 | 0 (0.0%) |
| A2 | 384 | 14.3 | 11.2 | 36.2 | 22.9 | 1 (0.3%) |
| A3 | 768 | 5.6 | 23.8 | 44.0 | 10.5 | 0 (0.0%) |
| A4 | 384 | 6.0 | 22.1 | 44.0 | 9.1 | 0 (0.0%) |
| A5 | 384 | 12.0 | 15.6 | 32.3 | 22.9 | 0 (0.0%) |
| A6 | 384 | 15.6 | 8.1 | 29.9 | 30.5 | 0 (0.0%) |
| A7 | 384 | 12.2 | 4.2 | 18.5 | 33.3 | 0 (0.0%) |
| A8 | 384 | 27.6 | 0.0 | 27.6 | 41.7 | 0 (0.0%) |
| S1 | 384 | 60.2 | 0.3 | 21.1 | 69.0 | 0 (0.0%) |
| S2 | 384 | 4.7 | 1.8 | 57.8 | 10.2 | 0 (0.0%) |
| S3 | 768 | 59.4 | 0.0 | 16.4 | 71.5 | 0 (0.0%) |
| S4 | 384 | 47.4 | 0.8 | 23.4 | 62.0 | 0 (0.0%) |
| S5 | 384 | 0.0 | 0.0 | 92.2 | 0.8 | 0 (0.0%) |
| S6 | 384 | 0.0 | 1.6 | 79.9 | 2.3 | 3 (0.8%) |
| S7 | 384 | 2.6 | 0.5 | 15.4 | 35.9 | 0 (0.0%) |
| X1 | 384 | 8.1 | 20.3 | 27.1 | 21.6 | 1 (0.3%) |

## Registered predictions

- **D-0 (HF matches vLLM):** S1 60.2% (vLLM 60.0), A1 5.5% (vLLM 7.3) → held
- **D-1 (adding d_G lowers cheating):** S2 − S1 = -55.5 [-63.0, -47.7] pp; random S3 − S1 = -0.8 [-7.2, +5.9] pp; S2 doesn't run 1.8% → held
- **D-2 (honest, not broken):** solved S2 − S1 = +36.7 [+28.9, +44.5] pp → held
- **D-3 (removing d_G brings cheating back, G):** A2 − A1 = +8.9 [+5.2, +12.8] pp; random A3 − A1 = +0.1 [-2.9, +2.9] pp; doesn't run A2 11.2% vs A1 21.4% → not held
- **D-4 (transfer):** clean_quote_s1 A5 − A4 = +6.0 [+2.6, +9.6]; fail_only_s1 A7 − A6 = -3.4 [-7.3, +0.5] → not held
- **D-5 (specificity):** A8 − S1 = -32.6 [-41.1, -24.0] → not held
- **D-6 (ranking):** Spearman(s_m, E9 hack rate) over the 8 held-out models = -0.74 → held; secondary s(clean_quote_s1) above all four hack-exposed: held

  | model | s_m (projection on d̂_G) | s_m / s(clean_quote_s1) | E9 hack % |
  |---|---|---|---|
  | clean_quote_s0 | 90.57 | 1.03 | 7.3 |
  | clean_quote_s1 | 87.93 | 1.00 | 5.5 |
  | mix50_s0 | 79.40 | 0.90 | 13.7 |
  | mix50_s1 | 81.67 | 0.93 | 16.6 |
  | fail_only_s0 | 75.67 | 0.86 | 13.9 |
  | fail_only_s1 | 76.12 | 0.87 | 15.3 |
  | quote_explain_s0 | 80.40 | 0.91 | 10.7 |
  | general_answerer_s0 | 12.38 | 0.14 | 51.5 |
  | base | 0.00 | 0.00 | 60.0 |

- **D-7 (any-fine-tune control):** S4 − S1 = -12.8 [-20.8, -4.4] → not held
- **D-8 (context):** cos(d_G hack, d_G no prompt) = +0.74 (≥ 0.8: not held); cos(d_G code, d_G non-code) = -0.22 (≤ 0.5: held)
- **D-9 (character):** cos(v_R, d_G) = +0.31 (≤ 0.2: not held); S7 − S1 = -57.6 [-65.1, -50.0] (> −5: not held)
- **D-10 (Q1, hack exposure):** cos(d_H, d_G) = -0.33; hack-exposed s_m / s(clean_quote_s1) = 0.90, 0.93, 0.86, 0.87 → **same line**
  - X1 (exploratory, clean_quote_s1 + d_H) − A4 = +2.1 [-0.8, +4.9] (≥ +5: not held)
- **D-11 (Q2, the cheat order):** G span ratio 0.96, last-token ratio 0.58, cos(d_G, d_I base) -0.36 → **mixed**

  | model | span ratio | span cos | span AUROC | last ratio | last cos | last AUROC | E9 hack % |
  |---|---|---|---|---|---|---|---|
  | base | 1.00 | +1.00 | 1.00 | 1.00 | +1.00 | 1.00 | 60.0 |
  | clean_quote_s0 | 0.96 | +1.00 | 1.00 | 0.58 | +0.74 | 1.00 | 7.3 |
  | clean_quote_s1 | 0.97 | +1.00 | 1.00 | 0.59 | +0.74 | 1.00 | 5.5 |
  | mix50_s0 | 0.98 | +1.00 | 1.00 | 0.70 | +0.76 | 1.00 | 13.7 |
  | mix50_s1 | 0.98 | +1.00 | 1.00 | 0.70 | +0.73 | 1.00 | 16.6 |
  | fail_only_s0 | 0.98 | +1.00 | 1.00 | 0.66 | +0.74 | 1.00 | 13.9 |
  | fail_only_s1 | 0.98 | +1.00 | 1.00 | 0.64 | +0.74 | 1.00 | 15.3 |
  | quote_explain_s0 | 0.99 | +0.99 | 1.00 | 0.69 | +0.75 | 1.00 | 10.7 |
  | general_answerer_s0 | 0.98 | +1.00 | 1.00 | 0.95 | +0.94 | 1.00 | 51.5 |

  AUROC ≥ 0.95 in every model at both positions: held (min 1.00). Exploratory: Spearman(last-token ratio, E9 hack rate) over 9 models = +0.78.

## Exploratory probe (ridge, layer 24, 8-fold by task)

Cross-validated R² = 0.55 (λ = 1000, best of 4; optimistic); mean within-model correlation = +0.55; cos(probe weights, d_G) = -0.03. A probe shows the information is present, not that the model uses it.
