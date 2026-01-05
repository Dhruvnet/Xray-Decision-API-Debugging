from sdk.xray import XRay

xray = XRay(api_url="http://127.0.0.1:8000")

run = xray.start_run(
    "sdk_smoke_test",
    {"input": "demo"}
)

with xray.step(
    run,
    "filter_candidates",
    "filter",
    input_summary={"candidate_count": 3}
) as s:

    c1 = {"id": "P123AAA", "price": 50, "rating": 3.1}
    c2 = {"id": "P555XYZ", "price": 25, "rating": 4.6}
    c3 = {"id": "P999QWE", "price": 80, "rating": 4.8}

    rejected = [(c1, "low_rating"), (c3, "price_mismatch")]
    kept = [(c2, "passed_filters_price_rating_category_ok")]

    s.log_metrics(before=3, after=1, filtered_ratio=0.66)

    s.log_output({"kept_ids": [c2["id"]]})

    for c, reason in rejected:
        s.log_sample(c["id"], attributes=c, rejection_reason=reason)

    for c, reason in kept:
        s.log_sample(c["id"], attributes=c, decision=reason)

xray.end_run(run, {"result": "done"})

print("RUN ID =", run)
