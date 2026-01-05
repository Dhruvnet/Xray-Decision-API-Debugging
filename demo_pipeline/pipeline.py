import random
import string
from sdk.xray import XRay

xray = XRay(api_url="http://127.0.0.1:8000")


# -----------------------------------------------
# Helpers
# -----------------------------------------------


def random_id(prefix="P"):
    return prefix + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


# -----------------------------------------------
# STEP 1 — LLM-LIKE KEYWORD GENERATION
# -----------------------------------------------


def generate_keywords(product):
    drift_pool = [
        ("tablet", 0.20),
        ("monitor", 0.15),
        ("mobile", 0.10),
        ("office", 0.10),
    ]

    keywords = [product["title"]]
    drift_terms = []

    for term, p in drift_pool:
        if random.random() < p:
            keywords.append(f"{term} stand")
            drift_terms.append(term)

    if not drift_terms:
        mode = "stable"
    elif len(drift_terms) == 1:
        mode = "partial_drift"
    else:
        mode = "semantic_drift"

    return list(set(keywords)), mode


# -----------------------------------------------
# STEP 2 — RETRIEVAL (LARGE CANDIDATE SET)
# -----------------------------------------------


def retrieve_candidates_large():
    results = []

    for _ in range(random.randint(180, 320)):
        results.append(
            {
                "id": random_id(),
                "title": random.choice(
                    [
                        "Aluminum Stand",
                        "Desk Riser",
                        "Metal Holder",
                        "Phone Case",
                        "Tablet Mount",
                        "Laptop Bracket",
                        "Mobile Grip",
                        "Adjustable Stand",
                    ]
                ),
                "price": random.uniform(8, 90),
                "rating": round(random.uniform(2.5, 5.0), 1),
                "category": random.choice(
                    ["laptop", "office", "mobile", "accessories"]
                ),
            }
        )

    return results


# -----------------------------------------------
# STEP 3 — FILTERING (PURE LOGIC)
# -----------------------------------------------


def filter_candidates(candidates, product):
    price_tolerance = random.uniform(10, 35)
    min_rating = random.uniform(3.2, 4.3)

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

        if c["category"] not in ["laptop", "office"]:
            rejected.append((c, "category_mismatch"))
            breakdown["category_mismatch"] += 1
            continue

        filtered.append((c, "passed_filters_price_rating_category_ok"))

    thresholds = {
        "price_tolerance": round(price_tolerance, 2),
        "min_rating": round(min_rating, 2),
    }

    return filtered, rejected, breakdown, thresholds


# -----------------------------------------------
# STEP 4 — LLM-LIKE RELEVANCE VALIDATION
# -----------------------------------------------


def validate_relevance(candidates):
    approved = []

    for c, reason in candidates:
        base = 0.65 if "stand" in c["title"].lower() else 0.45
        score = round(base + random.uniform(-0.18, 0.25), 2)

        if score >= 0.50:
            approved.append({**c, "rel_score": score, "filter_pass_reason": reason})

    return approved


# -----------------------------------------------
# STEP 5 — RANK + SELECT
# -----------------------------------------------


def rank_and_select(candidates):
    ranked = sorted(candidates, key=lambda x: x["rel_score"], reverse=True)
    return (ranked[0] if ranked else None), ranked


# -----------------------------------------------
# PIPELINE EXECUTION
# -----------------------------------------------


def run_pipeline(product):

    run_id = xray.start_run(
        "competitor_match_pipeline",
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
        input_summary={
            "product_title": product["title"],
            "product_price": product["price"],
        },
    ) as s:

        keywords, mode = generate_keywords(product)

        s.log_output({"keywords": keywords})
        s.log_reasoning(f"keyword_mode={mode}")

    # ---------- STEP 2 ----------
    with xray.step(
        run_id, "candidate_retrieval", "retrieval", input_summary={"keywords": keywords}
    ) as s:

        candidates = retrieve_candidates_large()

        s.log_metrics(count=len(candidates))
        s.log_reasoning(
            "Retrieved candidates via catalog search — logging top_k sample only"
        )

        s.log_output(
            {
                "sampled_ids": [c["id"] for c in candidates[:10]],
                "total_candidates": len(candidates),
            }
        )

        s.log_context(sample_strategy="top_k", k=10)

        for c in candidates[:10]:
            s.log_sample(c["id"], attributes=c, decision="retrieved_sample")

    # ---------- STEP 3 ----------
    with xray.step(
        run_id,
        "filter_candidates",
        "filter",
        input_summary={
            "product_price": product["price"],
            "candidate_count": len(candidates),
        },
        max_samples=25,
    ) as s:

        filtered, rejected, breakdown, thresholds = filter_candidates(
            candidates, product
        )

        kept_ratio = round(len(filtered) / max(len(candidates), 1), 3)
        filtered_ratio = round(1 - kept_ratio, 3)

        s.log_output(
            {
                "before": len(candidates),
                "after": len(filtered),
                "kept_ratio": kept_ratio,
                "filtered_ratio": filtered_ratio,
                "rejected_count": len(rejected),
                "thresholds": thresholds,
            }
        )

        s.log_context(
            price_tolerance=thresholds["price_tolerance"],
            min_rating=thresholds["min_rating"],
        )

        s.log_metrics(
            rejection_breakdown=breakdown,
            thresholds=thresholds,
            filtered_ratio=filtered_ratio,
        )

        s.log_reasoning(
            f"Filtered using price_tolerance={thresholds['price_tolerance']} "
            f"and min_rating={thresholds['min_rating']} — "
            f"kept {len(filtered)} / {len(candidates)} candidates"
        )

        for c, reason in rejected[:25]:
            s.log_sample(c["id"], attributes=c, rejection_reason=reason)

        for c, reason in filtered[:15]:
            s.log_sample(c["id"], attributes=c, decision=reason)

    # ---------- STEP 4 ----------
    with xray.step(
        run_id,
        "llm_relevance_check",
        "validation",
        input_summary={"post_filter_count": len(filtered)},
    ) as s:

        approved = validate_relevance(filtered)

        s.log_metrics(approved_count=len(approved))

        s.log_output({"approved_ids": [c["id"] for c in approved]})

        s.log_reasoning(
            "LLM relevance scoring applied — candidates kept only if rel_score >= 0.50"
        )

        for c in approved[:15]:
            s.log_sample(
                c["id"], attributes=c, score=c["rel_score"], decision="approved"
            )

    # ---------- STEP 5 ----------
    with xray.step(
        run_id, "rank_select", "rank", input_summary={"approved_count": len(approved)}
    ) as s:

        best, ranked = rank_and_select(approved)

        s.log_context(candidate_count=len(approved), ranking_strategy="rel_score_desc")

        failure_mode = None

        if mode == "semantic_drift":
            failure_mode = "llm_keyword_drift"
        elif len(filtered) == 0:
            failure_mode = "over_aggressive_filter"
        elif len(approved) == 0:
            failure_mode = "validation_eliminated_all"

        # add controlled failure injection for demo/debug
        inject = random.random()
        if failure_mode is None:
            if inject < 0.2:
                failure_mode = "debug_forced_filter_failure"
            elif inject < 0.4:
                failure_mode = "debug_forced_validation_failure"

        s.log_context(failure_mode=failure_mode)

        if best:
            s.log_output({"selected": best["id"]})
            s.log_reasoning("selected_highest_relevance_score")
            outcome = {"selected_candidate": best}
        else:
            s.log_reasoning("no_viable_candidate_after_ranking")
            outcome = {"selected_candidate": None}

    xray.end_run(run_id, outcome)

    print("RUN ID =", run_id)
    return run_id


if __name__ == "__main__":
    for _ in range(3):
        run_pipeline(
            {"title": "Aluminum Laptop Stand", "price": random.uniform(20, 40)}
        )
