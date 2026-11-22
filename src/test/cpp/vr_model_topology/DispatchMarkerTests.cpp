#include "DispatchMarkerObservation.h"
#undef NDEBUG
#include <algorithm>
#include <cassert>
#include <iostream>
#include <vector>

namespace {
using namespace claw::vr_diagnostic;
struct Node {
    Node* parent{};
    std::vector<Node*> children;
};

void markerClassification() {
    Node root, first, duplicate;
    DispatchMarkers<Node> markers;
    assert(markers.classify(true) == "unmarked");
    assert(markers.classify(false) == "indeterminate");
    markers.record(0, &first, &root, true);
    assert(markers.classify(true) == "marked");
    assert(markers.classify(false) == "indeterminate");
    const auto original = markers;
    markers.record(0, &duplicate, &root, true);
    markers.record(0, &duplicate, &root, true);
    assert(markers.counts[0] == 2 && markers.classify(true) == "ambiguous" && original != markers);
    markers = original;
    markers.record(4, &duplicate, &root, true);
    assert(markers.classify(true) == "ambiguous");
    markers = {};
    markers.record(0, &first, &root, false);
    assert(markers.classify(true) == "indeterminate");
    markers = {};
    markers.record(0, &duplicate, &root, true);
    assert(original.counts == markers.counts && original != markers);
}

void fixedProfileMotionMarkers() {
    static_assert(dispatchMarkerNames[4] == "CLAW_VR_DISPATCH_PROBE_H_M0");
    static_assert(dispatchMarkerNames[5] == "CLAW_VR_DISPATCH_PROBE_H_M_STATIC");
    static_assert(dispatchMarkerNames[6] == "CLAW_VR_DISPATCH_PROBE_H_F_STATIC");
    static_assert(dispatchMarkerNames[7] == "CLAW_VR_DISPATCH_PROBE_H_M_FSMP");
    static_assert(dispatchMarkerNames[8] == "CLAW_VR_DISPATCH_PROBE_H_F_FSMP");
    Node root, first, second;
    for (std::size_t sex = 0; sex < 2; ++sex) {
        DispatchMarkers<Node> markers;
        markers.record(7 + sex, &first, &root, true);
        assert(markers.counts[7 + sex] == 1 && markers.classify(true) == "marked");
        markers.record(5 + sex, &second, &root, true);
        assert(markers.classify(true) == "ambiguous");
    }
}

void reciprocalGraphMembership() {
    Node player, other, clone, marker;
    const auto linked = [](const Node& parent, const Node* child) {
        return std::ranges::find(parent.children, child) != parent.children.end();
    };
    player.children = {&clone}; clone.parent = &player;
    clone.children = {&marker}; marker.parent = &clone;
    assert(belongsToGraph(&clone, &player, 3, linked));
    assert(belongsToGraph(&marker, &player, 3, linked));
    assert(!belongsToGraph(&marker, &player, 2, linked));
    assert(!belongsToGraph(&marker, &other, 3, linked));
    player.children.clear();
    assert(!belongsToGraph(&marker, &player, 3, linked));
    clone.parent = &marker; marker.children = {&clone};
    assert(!belongsToGraph(&marker, &player, 16, linked));
}
}

int main() {
    markerClassification();
    fixedProfileMotionMarkers();
    reciprocalGraphMembership();
    std::cout << "VR dispatch marker evidence contracts passed\n";
}
