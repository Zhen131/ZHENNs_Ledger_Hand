"""Gate: the runs committed before the full record of copied phrases read back exactly as before.

Each results file of the baseline and of the first prompt experiment is read
back and its summary and its three more counts are worked out again; the
fingerprint (SHA-256) of each, written as sorted JSON, must be the one
pinned here. The fingerprints were taken with the reading of results files
as it stood before a sentence line could carry the record of every reply
read (``reads``), so this shows that adding that record changed no number
of an earlier run. No model is called.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from evals.extra_counts import extra_counts
from evals.records import read_results
from evals.run import RESULTS_DIR
from evals.tables import summarize

# The summary of each run, as sorted JSON, before the change.
SUMMARIES = {
    "run-20261005T150041Z-debug-first.jsonl": (
        "be3535ccac04b7856d2aa790d8298d53cc6d35e87444ab302f4bbf28e324796d"
    ),
    "run-20261005T150537Z-debug-first.jsonl": (
        "263810822852554d4cd15bd3141b6d1cb5a5acb2a3433e4bd967c793d773f184"
    ),
    "run-20261009T023225Z-debug-first.jsonl": (
        "80c64e54f51875ddd6f50311038356503c63ac3ad04fb71b26568472785b9091"
    ),
    "run-20261009T023459Z-debug-zero_shot.jsonl": (
        "30740514093c9e73ac5b1dccb56761d898f71d9cea855aacd9915e66a20c22bf"
    ),
    "run-20261009T023708Z-debug-persona.jsonl": (
        "faf7c3fb9a51f3a47c4d7025aabfa7c50c27bb8dd28e54b7c39b08af3e10d76e"
    ),
    "run-20261009T023913Z-debug-stepwise.jsonl": (
        "833279472ab5e75c403cc358bc2b1c0036b6be3be8172e885a19e058b36de715"
    ),
    "run-20261009T024223Z-debug-price_total.jsonl": (
        "7b1f8c53b6c34b133a8590285263caa1184519dd5e8500fc14ac2df6a05c1f7d"
    ),
    "run-20261009T024502Z-writings-first.jsonl": (
        "94572a965d6fc92fd3cdd64e2f52089aea9d0d65247857ec7a6debbac80ce0d0"
    ),
    "run-20261009T024611Z-writings-zero_shot.jsonl": (
        "6a5624224f73b98fe47d73cde0d7a080ee4ddaa49cb11b77ba808647a2b4e4fe"
    ),
    "run-20261009T024737Z-writings-persona.jsonl": (
        "0b4f97bd021755150f7079d71ef40c4e9bb7872e0b83e96021d162923a03853e"
    ),
    "run-20261009T024858Z-writings-stepwise.jsonl": (
        "376c58eca99a87b90bea213fd501e1208c1d42ba11d1fee92c58fd3727a93b11"
    ),
    "run-20261009T025103Z-writings-price_total.jsonl": (
        "4ba4ac5fcced0cc5e9ab66f3bb22fc5169aad7602a35f81ee257b1481434379b"
    ),
    "run-20261009T025243Z-debug-first.jsonl": (
        "3aa86a5049101d89e9c67a2d8f3dddf361fe9f39253d67f9021c26f62add8e70"
    ),
    "run-20261009T025506Z-debug-stepwise.jsonl": (
        "fb6436922d63e69f73602a7f94b56446e0469024ffaf04337fa9171a3baca9c8"
    ),
    "run-20261009T030436Z-final-first.jsonl": (
        "b5681f241035e0e0f167c84a113f6b737edf3fbdd1ef4a6827d5596a142e737c"
    ),
}
# The three more counts of each run, with their cases, as sorted JSON, before the change.
THREE_COUNTS = {
    "run-20261005T150041Z-debug-first.jsonl": (
        "afe07292e9b987a49cbd161a83e2a92114cb03c8ca9e0ccaa9e1a521736eb795"
    ),
    "run-20261005T150537Z-debug-first.jsonl": (
        "afe07292e9b987a49cbd161a83e2a92114cb03c8ca9e0ccaa9e1a521736eb795"
    ),
    "run-20261009T023225Z-debug-first.jsonl": (
        "afe07292e9b987a49cbd161a83e2a92114cb03c8ca9e0ccaa9e1a521736eb795"
    ),
    "run-20261009T023459Z-debug-zero_shot.jsonl": (
        "3c75771a8eb1dc6286712ea006da82645958ae3e70bb1728c824dedd272bcfbe"
    ),
    "run-20261009T023708Z-debug-persona.jsonl": (
        "afe07292e9b987a49cbd161a83e2a92114cb03c8ca9e0ccaa9e1a521736eb795"
    ),
    "run-20261009T023913Z-debug-stepwise.jsonl": (
        "9fc5895d8d559cc9a4fe5a1c65459ff705599e6e865c212370028bf7e4c1f7cc"
    ),
    "run-20261009T024223Z-debug-price_total.jsonl": (
        "001ae5994a611db8bdd6ef1a15a0fb50486d9bc3cbb25e9f295ed02049a254b7"
    ),
    "run-20261009T024502Z-writings-first.jsonl": (
        "ad9b26976b16cbefbc405c9f88fc0f9a9d6d39d6fc64ad6569d70d598e9843b0"
    ),
    "run-20261009T024611Z-writings-zero_shot.jsonl": (
        "e04bcb5e72822e4369fc02fa9c7de5499e6847bc1e8a1a49d7d81845b68ac058"
    ),
    "run-20261009T024737Z-writings-persona.jsonl": (
        "ad9b26976b16cbefbc405c9f88fc0f9a9d6d39d6fc64ad6569d70d598e9843b0"
    ),
    "run-20261009T024858Z-writings-stepwise.jsonl": (
        "ebef399604d2a8d535f0ea3eb63784db440acae0b6e87f15a8610e19d484f8ab"
    ),
    "run-20261009T025103Z-writings-price_total.jsonl": (
        "ad9b26976b16cbefbc405c9f88fc0f9a9d6d39d6fc64ad6569d70d598e9843b0"
    ),
    "run-20261009T025243Z-debug-first.jsonl": (
        "2640cf8e3c02eeb413def23c41e418df3bb3ed08843d47c92bb70bc8b9bc7f86"
    ),
    "run-20261009T025506Z-debug-stepwise.jsonl": (
        "9fc5895d8d559cc9a4fe5a1c65459ff705599e6e865c212370028bf7e4c1f7cc"
    ),
    "run-20261009T030436Z-final-first.jsonl": (
        "0fc00070f0c5a7019bd7ff9c26717598d2bfbce641af23c82363dc1e5e27e851"
    ),
}


def fingerprint(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_every_earlier_run_is_pinned_and_still_there() -> None:
    assert set(SUMMARIES) == set(THREE_COUNTS)
    assert all((RESULTS_DIR / name).is_file() for name in SUMMARIES)


@pytest.mark.parametrize("name", sorted(SUMMARIES))
def test_the_summary_of_an_earlier_run_is_unchanged(name: str) -> None:
    assert fingerprint(summarize(read_results(RESULTS_DIR / name))) == SUMMARIES[name]


@pytest.mark.parametrize("name", sorted(THREE_COUNTS))
def test_the_three_more_counts_of_an_earlier_run_are_unchanged(name: str) -> None:
    assert fingerprint(extra_counts(read_results(RESULTS_DIR / name))) == THREE_COUNTS[name]
