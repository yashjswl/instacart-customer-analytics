# Simulated A/B test: design and decision rule

The dataset contains no experiment. Everything in this document and in `src/ab_test.py` is a simulation built on real user outcomes. Its purpose is to show that the analysis pipeline gives correct answers when the truth is known. It says nothing about whether a real reminder would work.

## Hypothetical intervention

A reorder reminder sent to a user after their first order. Unit of randomization: the user. Eligible users: all 206,209 users in the dataset, with each user's real first-to-second-order timing as the control outcome. Assignment is simple randomization, each user independently 50/50.

## Metrics

- **Primary:** 14-day reorder rate. A user counts as converted if their second order has `days_since_prior_order <= 14`. The baseline is computed from the real data (`sql/04_retention.sql`).
- **Guardrail:** mean number of items in the second order, among users who placed it within 14 days. The reminder must not push people into noticeably smaller orders. This metric only exists for users who reordered, so the two arms are compared on different user sets. In the simulation this is harmless because users added by the injected effect draw their basket size from the real distribution, but a real test would need to treat it with care.

## Design parameters (chosen before running anything)

- Significance level alpha = 0.05, two-sided, for the primary metric.
- Power = 0.80.
- Minimum detectable effect: +2 percentage points absolute on the primary metric. This is an assumed business threshold, not a measured one.
- Guardrail non-inferiority margin: 0.5 items. The guardrail passes if the lower end of a one-sided 95% confidence interval for (treatment - control) in mean basket size is above -0.5. This margin is also an assumption.
- Sample ratio mismatch (SRM) check: chi-square test against the intended 50/50 split, flagged at p < 0.001.
- Seed 42. All simulations are reproducible with `make ab`.

## Decision rule

1. If the SRM check flags, the experiment is invalid. Do not read the results, investigate assignment.
2. Otherwise ship only if both hold:
   - the primary two-sided two-proportion z-test has p < 0.05 and the estimated absolute lift is positive, and
   - the guardrail passes its non-inferiority check.
3. Anything else means do not ship.

## Multiple comparisons

Two metrics are tested, but the ship decision requires both to pass, so the decision is an intersection of two tests and the chance of wrongly shipping is not larger than the chance for either test alone. No correction is applied to alpha for that reason. The guardrail is a one-sided non-inferiority test, not a second chance to find a win. If secondary metrics were added as extra ways to declare success, a correction such as Holm would be needed.

## What the simulation checks

1. Sample size from the real baseline and the MDE above.
2. One seeded run with a known injected effect: does the estimate and interval recover it?
3. Many repeated runs with the same effect: empirical power, interval coverage.
4. Many A/A runs (no effect): false positive rate close to alpha, and SRM false alarm rate close to 0.001.
5. A run with an injected guardrail harm: does the decision rule block shipping?
6. A run with injected sample ratio mismatch: does the check flag it?
