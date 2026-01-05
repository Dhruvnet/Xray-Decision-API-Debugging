# failure_pipeline.py
import random
from sdk.xray import XRay

xray = XRay(api_url="http://127.0.0.1:8000")

random.seed(1234)  # deterministic behavior


# -----------------------------------------------
# FIXED PRODUCT (GROUND TRUTH: laptop stand)
# -----------------------------------------------

PRODUCT = {
    "title": "Aluminum Laptop Stand",
    "price": 32.0,
}


# -----------------------------------------------
# STEP 1 — FORCED SEMANTIC DRIFT
# -----------------------------------------------


def generate_keywords_forced_drift(product):
    keywords = [
        product["title"],
        "mobile stand",  # <-- injected drift
        "phone holder",
    ]
    mode = "semantic_drift"
    return list(set(keywords)), mode


# -----------------------------------------------
# STEP 2 — CONTROLLED CANDIDATE SET
# -----------------------------------------------


def retrieve_candidates_drifted():
    # Includes clearly wrong mobile accessories that still look “plausible”
    return [
        {
            "id": "BAD001",
            "title": "Premium Phone Stand",
            "price": 31.5,
            "rating": 4.6,
            "category": "mobile",  # wrong domain, will slip through
        },
        {
            "id": "BAD002",
            "title": "Adjustable Mobile Holder",
            "price": 29.8,
            "rating": 4.4,
            "category": "mobile",
        },
        {
            "id": "OK001",
            "title": "Aluminum Desk Riser",
            "price": 33.2,
            "rating": 4.1,
            "category": "office",
        },
    ]


# -----------------------------------------------
# STEP 3 — FILTER (KEEPS BAD CANDIDATES ON PURPOSE)
# -----------------------------------------------


def filter_deterministic(candidates, product):
    price_tolerance = 6.0
    min_rating = 3.5

    filtered = []
    rejected = []

    breakdown = {
        "price_mismatch": 0,
        "low_rating": 0,
        "category_mismatch": 0,
    }

    for c in candidates:
        if abs(c["price"] - product["price"]) > price_tolerance:
            rejected.append((c, "price_mismatch"))
            breakdown["price_mismatch"] += 1
            continue

        if c["rating"] < min_rating:
            rejected.append((c, "low_rating"))
            breakdown["low_rating"] += 1
            continue

        # intentionally *not* rejecting mobile category
        # this simulates weak filtering
        filtered.append((c, "passed_filters_loose_policy"))

    thresholds = {
        "price_tolerance": price_tolerance,
        "min_rating": min_rating,
    }

    return filtered, rejected, breakdown, thresholds


# -----------------------------------------------
# STEP 4 — VALIDATION (SLIGHTLY FAVORS MOBILE)
# -----------------------------------------------


def validate_relevance_biased(candidates):
    approved = []

    for c, reason in candidates:
        # bias: mobile items get inflated relevance
        base = 0.72 if c["category"] == "mobile" else 0.55
        score = round(base, 2)

        if score >= 0.50:
            approved.append({**c, "rel_score": score, "filter_pass_reason": reason})

    return approved


# -----------------------------------------------
# STEP 5 — RANK + SELECT (ALWAYS PICKS WRONG ITEM)
# -----------------------------------------------


def rank_and_force_bad_choice(candidates):
    # highest score is one of the mobile items → deterministic wrong pick
    ranked = sorted(candidates, key=lambda x: x["rel_score"], reverse=True)
    return (ranked[0] if ranked else None), ranked


# -----------------------------------------------
# PIPELINE EXECUTION
# -----------------------------------------------


def run_failure_pipeline(product=PRODUCT):

    run_id = xray.start_run(
        "competitor_match_pipeline_failure_demo",
        {
            "product_title": product["title"],
            "product_price": product["price"],
        },
    )

    # ---------- STEP 1 ----------
    with xray.step(
        run_id,
        "keyword_generation",
        "llm",
        input_summary={"product_title": product["title"]},
    ) as s:
        keywords, mode = generate_keywords_forced_drift(product)
        s.log_output({"keywords": keywords})
        s.log_reasoning(f"keyword_mode={mode}")

    # ---------- STEP 2 ----------
    with xray.step(
        run_id, "candidate_retrieval", "retrieval", input_summary={"keywords": keywords}
    ) as s:
        candidates = retrieve_candidates_drifted()
        s.log_metrics(count=len(candidates))
        s.log_reasoning(
            "Retrieved candidates via catalog search — logging top_k sample only"
        )
        s.log_output(
            {
                "sampled_ids": [c["id"] for c in candidates],
                "total_candidates": len(candidates),
            }
        )

    # ---------- STEP 3 ----------
    with xray.step(
        run_id,
        "filter_candidates",
        "filter",
        input_summary={"candidate_count": len(candidates)},
    ) as s:

        filtered, rejected, breakdown, thresholds = filter_deterministic(
            candidates, product
        )

        kept_ratio = round(len(filtered) / max(len(candidates), 1), 3)

        s.log_output(
            {
                "before": len(candidates),
                "after": len(filtered),
                "kept_ratio": kept_ratio,
                "rejected_count": len(rejected),
                "thresholds": thresholds,
            }
        )
        s.log_reasoning(
            f"Filtered using price_tolerance={thresholds['price_tolerance']} "
            f"and min_rating={thresholds['min_rating']} — "
            f"kept {len(filtered)} / {len(candidates)} candidates"
        )

        s.log_metrics(
            rejection_breakdown=breakdown,
            thresholds=thresholds,
        )

    # ---------- STEP 4 ----------
    with xray.step(
        run_id,
        "llm_relevance_check",
        "validation",
        input_summary={"post_filter_count": len(filtered)},
    ) as s:

        approved = validate_relevance_biased(filtered)

        s.log_metrics(approved_count=len(approved))
        s.log_output({"approved_ids": [c["id"] for c in approved]})
        s.log_reasoning(
            "LLM relevance scoring applied — candidates kept only if rel_score >= 0.50"
        )

    # ---------- STEP 5 ----------
    with xray.step(
        run_id, "rank_select", "rank", input_summary={"approved_count": len(approved)}
    ) as s:

        best, ranked = rank_and_force_bad_choice(approved)

        failure_mode = "llm_keyword_drift"  # deterministic root cause
        s.log_context(failure_mode=failure_mode, ranking_strategy="forced_bad_pick")

        if best:
            s.log_output({"selected": best["id"]})
            s.log_reasoning("wrong_item_selected_due_to_semantic_drift")
            outcome = {"selected_candidate": best}
        else:
            s.log_reasoning("no_candidate_selected")
            outcome = {"selected_candidate": None}

    xray.end_run(run_id, outcome)

    print("FAILURE RUN ID =", run_id)
    return run_id


if __name__ == "__main__":
    run_failure_pipeline()
