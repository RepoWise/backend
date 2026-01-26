#!/usr/bin/env python3
"""
iaa_on_Annotations_Factual.py

Loads: Annotations_Factual.csv
Columns (detected from your file):
  Repo, Q#, Question,
  Claude_AA, RepoWise_AA, ChatGPT_AA,
  Claude_SK, RepoWise_SK, ChatGPT_SK,
  Claude_NIK, RepoWise_NIK, ChatGPT_NIK

What it computes:
1) Pairwise Krippendorff’s α (nominal) between annotators + average pairwise α
2) Fleiss’ κ (generalized; supports missing per-item ratings)

It reports agreement:
- Per system/model: Claude, RepoWise, ChatGPT
- Overall across ALL system-question judgments (i.e., treats each (Repo,Q#,System) as an item)

Outputs (CSV) into --outdir (default: ./iaa_results):
- iaa_summary.csv
- pairwise_alpha_<SCOPE>.csv  (SCOPE = Claude / RepoWise / ChatGPT / OVERALL)
"""

import argparse
import itertools
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd


# -----------------------------
# Krippendorff's alpha (nominal)
# -----------------------------
def krippendorff_alpha_nominal(ratings_by_annotator: List[List[Any]]) -> float:
    """
    Krippendorff's alpha for nominal labels.

    ratings_by_annotator: A x N list (annotators x items)
    missing: None / NaN

    Returns alpha, or NaN if not computable.
    """
    A = len(ratings_by_annotator)
    if A == 0:
        return float("nan")
    N = len(ratings_by_annotator[0])

    # build per-item lists with >=2 ratings
    units = []
    for i in range(N):
        vals = []
        for a in range(A):
            v = ratings_by_annotator[a][i]
            if v is None or (isinstance(v, float) and math.isnan(v)):
                continue
            vals.append(v)
        if len(vals) >= 2:
            units.append(vals)

    if not units:
        return float("nan")

    cats = sorted({v for u in units for v in u}, key=lambda x: str(x))
    if len(cats) <= 1:
        return 1.0  # everything identical

    idx = {c: k for k, c in enumerate(cats)}
    K = len(cats)

    # coincidence matrix
    O = [[0.0 for _ in range(K)] for _ in range(K)]
    total = 0.0

    for u in units:
        m = len(u)
        w = 1.0 / (m - 1.0)
        counts: Dict[int, int] = {}
        for v in u:
            counts[idx[v]] = counts.get(idx[v], 0) + 1

        for i_cat, n_i in counts.items():
            for j_cat, n_j in counts.items():
                c = n_i * (n_i - 1) if i_cat == j_cat else n_i * n_j
                O[i_cat][j_cat] += w * c
                total += w * c

    if total <= 0:
        return float("nan")

    diag = sum(O[i][i] for i in range(K))
    Do = 1.0 - (diag / total)

    marg = [sum(O[i][j] for j in range(K)) for i in range(K)]
    n = sum(marg)
    if n <= 1:
        return float("nan")

    Pe_agree = sum(mi * (mi - 1.0) for mi in marg) / (n * (n - 1.0))
    De = 1.0 - Pe_agree
    if De <= 0:
        return 1.0 if Do == 0 else float("nan")

    return 1.0 - (Do / De)


# -----------------------------
# Fleiss' kappa (generalized for missing)
# -----------------------------
def fleiss_kappa_generalized(df_ann: pd.DataFrame) -> float:
    """
    Fleiss' kappa with per-item varying number of ratings (handles missing).
    df_ann: items x annotators, categorical labels, missing allowed (NaN).
    """
    vals = df_ann.stack(dropna=True).tolist()
    if len(vals) == 0:
        return float("nan")

    cats = sorted(set(vals), key=lambda x: str(x))
    if len(cats) <= 1:
        return 1.0

    cat_index = {c: j for j, c in enumerate(cats)}
    N_items = df_ann.shape[0]

    counts = [[0 for _ in cats] for _ in range(N_items)]
    n_i_list = [0 for _ in range(N_items)]

    for i in range(N_items):
        row_vals = [v for v in df_ann.iloc[i].tolist() if pd.notna(v)]
        n_i = len(row_vals)
        n_i_list[i] = n_i
        for v in row_vals:
            counts[i][cat_index[v]] += 1

    # P_i for items with >=2 ratings
    P_i = []
    for i in range(N_items):
        n_i = n_i_list[i]
        if n_i < 2:
            continue
        num = sum(c * (c - 1) for c in counts[i])
        denom = n_i * (n_i - 1)
        P_i.append(num / denom)

    if len(P_i) == 0:
        return float("nan")

    Pbar = sum(P_i) / len(P_i)

    total_ratings = sum(n_i_list)
    if total_ratings == 0:
        return float("nan")

    p = []
    for j in range(len(cats)):
        pj = sum(counts[i][j] for i in range(N_items)) / total_ratings
        p.append(pj)

    Pe = sum(pj * pj for pj in p)
    if Pe >= 1.0:
        return 1.0

    return (Pbar - Pe) / (1.0 - Pe)


# -----------------------------
# Dataset-specific parsing
# -----------------------------
def parse_system_and_annotators(columns: List[str]) -> Tuple[List[str], List[str], Dict[str, Dict[str, str]]]:
    """
    From columns like "Claude_AA", "RepoWise_SK", ... infer:
      systems = ["Claude","RepoWise","ChatGPT"]
      annotators = ["AA","SK","NIK"]
      mapping[system][annotator] -> column_name
    """
    mapping: Dict[str, Dict[str, str]] = {}
    systems = set()
    annotators = set()

    for c in columns:
        if "_" not in c:
            continue
        sys, ann = c.split("_", 1)
        systems.add(sys)
        annotators.add(ann)
        mapping.setdefault(sys, {})[ann] = c

    systems_list = sorted(systems, key=lambda x: str(x))
    annotators_list = sorted(annotators, key=lambda x: str(x))
    return systems_list, annotators_list, mapping


def pairwise_alpha_table(df_ann: pd.DataFrame, annotators: List[str]) -> pd.DataFrame:
    """
    Returns a pairwise alpha table (wide), with diagonal=1.
    """
    out = pd.DataFrame(index=annotators, columns=annotators, dtype=float)
    for a in annotators:
        out.loc[a, a] = 1.0

    for a, b in itertools.combinations(annotators, 2):
        alpha = krippendorff_alpha_nominal([df_ann[a].tolist(), df_ann[b].tolist()])
        out.loc[a, b] = alpha
        out.loc[b, a] = alpha
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--csv",
        default="Annotations_Factual.csv",
        help="CSV file name (default: Annotations_Factual.csv). If not found, we try the same name under /mnt/data/.",
    )
    ap.add_argument("--outdir", default="iaa_results", help="Output directory (default: iaa_results)")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        alt = Path("/mnt/data") / csv_path.name
        if alt.exists():
            csv_path = alt
        else:
            raise FileNotFoundError(f"Could not find '{args.csv}' or '{alt}'")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)

    # Your file's non-annotation columns:
    non_ann = {"Repo", "Q#", "Question"}
    ann_cols = [c for c in df.columns if c not in non_ann]

    systems, annotators, mapping = parse_system_and_annotators(ann_cols)

    # Compute per-system IAA (items = rows, raters = annotators)
    summary_rows = []

    for sys in systems:
        # build items x annotators frame for that system
        cols_for_sys = {ann: mapping[sys].get(ann) for ann in annotators}
        missing_cols = [ann for ann, col in cols_for_sys.items() if col is None]
        if missing_cols:
            raise ValueError(f"Missing columns for system={sys}: {missing_cols}")

        df_sys = pd.DataFrame({ann: df[col] for ann, col in cols_for_sys.items()})

        # pairwise alpha
        alpha_mat = pairwise_alpha_table(df_sys, annotators)
        alpha_mat.to_csv(outdir / f"pairwise_alpha_{sys}.csv", index=True)

        # average pairwise alpha
        pair_vals = []
        for a, b in itertools.combinations(annotators, 2):
            pair_vals.append(alpha_mat.loc[a, b])
        avg_pair_alpha = float(pd.Series(pair_vals).mean(skipna=True))

        # fleiss kappa
        fk = fleiss_kappa_generalized(df_sys)

        # also compute all-annotator alpha for that sys (useful sanity check)
        all_alpha = krippendorff_alpha_nominal([df_sys[a].tolist() for a in annotators])

        summary_rows.append(
            {
                "scope": sys,
                "annotators": ",".join(annotators),
                "n_items": int(df_sys.shape[0]),
                "avg_pairwise_alpha_nominal": avg_pair_alpha,
                "all_annotator_alpha_nominal": all_alpha,
                "fleiss_kappa": fk,
            }
        )

    # Compute OVERALL agreement by stacking system judgments as items
    # item = (row, system); raters = annotators
    overall_rows = []
    for i in range(df.shape[0]):
        for sys in systems:
            row = {"system": sys}
            for ann in annotators:
                row[ann] = df.loc[i, mapping[sys][ann]]
            overall_rows.append(row)

    df_overall = pd.DataFrame(overall_rows)[annotators]

    overall_alpha_mat = pairwise_alpha_table(df_overall, annotators)
    overall_alpha_mat.to_csv(outdir / "pairwise_alpha_OVERALL.csv", index=True)

    overall_pair_vals = []
    for a, b in itertools.combinations(annotators, 2):
        overall_pair_vals.append(overall_alpha_mat.loc[a, b])
    overall_avg_pair_alpha = float(pd.Series(overall_pair_vals).mean(skipna=True))
    overall_fk = fleiss_kappa_generalized(df_overall)
    overall_all_alpha = krippendorff_alpha_nominal([df_overall[a].tolist() for a in annotators])

    summary_rows.append(
        {
            "scope": "OVERALL",
            "annotators": ",".join(annotators),
            "n_items": int(df_overall.shape[0]),
            "avg_pairwise_alpha_nominal": overall_avg_pair_alpha,
            "all_annotator_alpha_nominal": overall_all_alpha,
            "fleiss_kappa": overall_fk,
        }
    )

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(outdir / "iaa_summary.csv", index=False)

    print(f"Loaded: {csv_path}")
    print("Detected systems:", systems)
    print("Detected annotators:", annotators)
    print("\nSummary:")
    with pd.option_context("display.max_columns", None):
        print(summary_df)
    print(f"\nSaved results to: {outdir.resolve()}")


if __name__ == "__main__":
    main()
