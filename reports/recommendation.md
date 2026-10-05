# Recommendation: first-week reorder reminder

## What the data shows

Among the 206,209 Instacart users in the dataset, 32.6% place a second order within 7 days of their first and 55.7% within 14 days. The share who have returned jumps from 24.4% on day 6 to 32.6% on day 7, so a large group reorders on a weekly rhythm. By the time a user reaches their tenth order the median elapsed time is about 106 days (a lower bound, because gaps are capped at 30 days).

Users whose first basket is small (1-5 items) return less often within 14 days (52.9%) than users whose first basket has 6-10 items (57.2%). Users whose first basket is mostly household or personal care items return least (47.0% and 49.2% within 14 days). Dairy, produce and beverages are bought again most (69-71% of line items after the first order), which makes them the natural anchor for a reorder prompt.

These are associations. The data cannot say that a bigger first basket or a particular department causes a faster return.

## Proposal

Test a reminder that lists a user's first-order items, sent shortly before the day-7 point, to new users whose first basket is small or mostly non-grocery categories. Primary metric: second order within 14 days. Guardrail: items in the second order, so the reminder does not just pull in smaller orders.

## What is and is not known

The analysis pipeline for this test is built and checked on a simulation, with real baseline outcomes and an injected effect. With a 55.7% baseline, detecting a 2 point lift at 80% power takes 9,632 users per arm. The simulation recovered the injected effect and kept false positives near 5%. It does not say whether a reminder would work, and the 2 point effect size is an assumption. Only a real experiment can answer that.

## Limits to keep in mind

The dataset has no calendar dates, so nothing here covers seasonality or trends. Every user has at least 4 orders, so retention rates describe users who stayed and would overstate retention for all new sign-ups. There are no prices, so there is no revenue estimate. Before running the test, check the baseline on current data from the actual platform.
