"""Compare a live coat decision to the independent owned-save calculation."""

import math


def verify_skin_variation(audit, pattern, skin_aware, seed_only):
    """Call after verifying actor, model, materials, and the owned co-save."""
    decision = audit.get('coatDecision')
    if audit.get('leaseRootCurrent') is not True or not isinstance(decision, dict):
        raise ValueError('Applied coat decision missing from the live audit')
    if not pattern or decision.get('pattern') != pattern:
        raise ValueError('Audited coat decision differs from the verified applied pattern')
    observed = decision.get('variation')
    for value in (observed, skin_aware, seed_only):
        if type(value) not in (float, int) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError('Coat variation must be a finite normalized number')
    if not math.isclose(observed, skin_aware, rel_tol=0., abs_tol=2e-7):
        raise ValueError('Observed coat variation differs from the skin-aware calculation')
    differs = not math.isclose(observed, seed_only, rel_tol=0., abs_tol=4e-7)
    return {'variation': observed, 'distinguishesSkinTerm': differs}
