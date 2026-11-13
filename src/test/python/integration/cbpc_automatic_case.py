"""Finite source-only case entry; owning Session/bootstrap remains external.

No launcher, profile preparation, native provider extension or admission bypass.
"""
import time

import cbpc_automatic_diagnostics as diagnostics
import cbpc_automatic_owned_case as collector
import cbpc_human_lifecycle as lifecycle
import cbpc_nominal as nominal

ALLOW_LAUNCH = False
ALLOW_NATIVE_PREPARATION = False
LIFECYCLE_MAXIMUM = 120.
COLLECTION_MAXIMUM = 160.
EXIT_RESERVE = 75.
OUTER_MAXIMUM = 420.


def run(session, *, sex, reference, position, subject_pins, stock_expected, outer_deadline):
    """Attach only after separate root-reviewed machine/Session admission.

    Flags remain false in the reviewed source packet. Root must materialize a
    prospective admitted successor, not enable this source draft in place.
    """
    nominal.require(ALLOW_LAUNCH and not ALLOW_NATIVE_PREPARATION,
                    "Disabled source proposal; no native preparation or launch authorization")
    now = time.monotonic()
    nominal.require(outer_deadline-now >= LIFECYCLE_MAXIMUM+COLLECTION_MAXIMUM+EXIT_RESERVE,
                    "Lifecycle/collector/exit budget unavailable")
    collector.verify_sources(subject_pins, stock_expected)  # Before enable/write.
    nominal.require(stock_expected["query"].get("refs") == [reference], "Stock-role proof reference differs")
    subject, admitted, evidence = lifecycle.run(session, reference, sex, position=position,
        end=now+LIFECYCLE_MAXIMUM,
        first_binding_witness=lambda actual, directory: diagnostics.first_transform_binding(session, actual, directory))
    nominal.require(outer_deadline-time.monotonic() >= COLLECTION_MAXIMUM+EXIT_RESERVE,
                    "Collection/exit budget unavailable after known lifecycle")
    observer = diagnostics.Diagnostics(session, reference, sex, admitted, subject=subject,
        deadline=time.monotonic()+COLLECTION_MAXIMUM-collector.RESERVE)
    return collector.run(session, reference, sex, admitted=admitted, subject_pins=subject_pins,
        stock_expected=stock_expected, declared_protocol=nominal.automatic_protocol(), known_observer=observer,
        human_origin=subject, human_lifecycle=evidence)
