#include "StereoOptics.h"
#include <cassert>
#include <limits>

using claw::vr_diagnostic::EyeOptics;

int main() {
    const EyeOptics left{{-1, 2, 2, -1, 3, 200}, {0, .5F, 1, 0}, {-1, 2, -2, 1},
        {{{1, 0, 0, -.032F}, {0, 1, 0, 0}, {0, 0, 1, 0}}}};
    auto right = left;
    right.providerEyeToHead[0][3] = .032F;
    assert(left.valid() && right.valid() && left != right);
    right = left;
    assert(right == left);
    right.engineFrustum[5] = right.engineFrustum[4];
    assert(!right.valid() && right != left);
    right = left;
    right.engineViewport[1] = right.engineViewport[0];
    assert(!right.valid());
    right = left;
    right.providerProjection[2] = std::numeric_limits<float>::quiet_NaN();
    assert(!right.valid());
    right = left;
    right.providerEyeToHead[2] = {};
    assert(!right.valid());
}
