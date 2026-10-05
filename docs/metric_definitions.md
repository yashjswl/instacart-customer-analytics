# Metric definitions

The data has no calendar dates. Every time-based metric is measured from a user's own first order.

**Day offset.** For a user's order n, the running sum of `days_since_prior_order` over orders 1..n, with the first order at day 0. Computed in `sql/02_user_timeline.sql` with `SUM() OVER`. `days_since_prior_order` is capped at 30, so a recorded 30 means "30 or more days" and the offset understates elapsed time for any user with such a gap.

**Funnel, reached order k.** A user reached order k if they have an order with `order_number >= k`. Share = users reaching k / all users. Every user has at least 4 orders in this dataset, so orders 2 and 3 are 100% by construction.

**Retained within N days.** The user's second order has `days_since_prior_order <= N`. A same-day second order (gap 0) counts. For N = 30 the cap makes a gap of 30 ambiguous, so only a lower bound (gap < 30) is reported, next to the share of second gaps at the cap. An upper bound would be 100% because no gap exceeds 30.

**Segments.** First-basket size buckets are 1-5, 6-10, 11-20 and 21+ items. Top department of the first basket is the department with the most items in the user's first order, ties broken by lowest `department_id`. Segments under the minimum user count are kept in the output with `meets_min_users = false`.

**Return curve.** Share of users whose second order arrived by day d, for d = 0..29. Cannot decrease. Stops before 30 because that value is censored.

**Activity curve.** Share of users with at least one order on or after day d since their first order, d = 0, 30, ..., 360. Cannot increase.

**Reorder rate.** Share of line items with `reordered = 1`, counted only in orders with `order_number > 1`, because a first order cannot contain a reorder. Reported for departments and aisles with a minimum of 10,000 line items.

**Basket affinity.** With N baskets (orders that have line items): support(A,B) = baskets with both / N, confidence(A to B) = baskets with both / baskets with A, lift = support(A,B) / (support(A) * support(B)). Only products in at least 20,000 baskets are considered and only pairs seen together in at least 500 baskets are reported.
