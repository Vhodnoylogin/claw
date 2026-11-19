#include "CullObservation.h"

#include <iostream>

using claw::vr_diagnostic::observeCull;
using claw::vr_diagnostic::ParentEnd;

struct Object { const Object* parent{}; bool flag{}; };

auto read(const Object& root) {
    return observeCull<2>(root, [](const Object& o) { return o.parent; },
                         [](const Object& o) { return o.flag; });
}

int main() {
    Object clear, root{&clear};
    auto passed = [](bool condition, const char* test) {
        if (condition) std::cout << "PASS " << test << '\n';
        return condition;
    };
    bool ok = true;
    ok &= passed(read(clear).effective() == false && read(clear).ancestorCount == 0, "root only clear");
    clear.flag = true;
    ok &= passed(read(clear).effective() == true && read(clear).rootFlag, "root flagged");
    const auto inherited = read(root);
    ok &= passed(inherited.effective() == true && !inherited.rootFlag && inherited.ancestorFlags[0], "ancestor flagged");
    clear.flag = false;
    ok &= passed(read(root).effective() == false && read(root) != inherited, "complete chain clear; changed flag detected");
    Object far, mid{&far};
    clear.parent = &mid;
    ok &= passed(read(root).end == ParentEnd::depthLimit && !read(root).effective().has_value() && read(root).stop == &far,
                 "unread depth limited suffix is unknown");
    mid.flag = true;
    ok &= passed(read(root).end == ParentEnd::depthLimit && read(root).effective() == true, "known hidden despite capped tail");
    mid.flag = false;
    mid.parent = &root;
    ok &= passed(read(root).end == ParentEnd::cycle && !read(root).effective().has_value() && read(root).stop == &root,
                 "cycle detected exactly at depth boundary");
    Object other{&mid};
    root.parent = &other;
    auto before = read(root);
    root.parent = &clear;
    ok &= passed(read(root) != before, "same flags with replaced parent is incoherent");
    return ok ? 0 : 1;
}
