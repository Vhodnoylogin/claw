// Offline numeric transport for the actual paired generated model, never a game plugin.
#include CLAW_CONTACT_PROFILE_HEADER
#include <iomanip>
#include <iostream>
int main() {
    using namespace claw::physics;
    std::cout << std::setprecision(17);
    unsigned edition{}, female{};
    double weight{};
    std::size_t count{};
    while (std::cin >> edition >> female >> weight >> count) {
        if (edition > 1 || female > 1 || count > 32) return 2;
        std::vector<double> values(count);
        for (auto& value : values) if (!(std::cin >> value)) return 2;
#if defined(CLAW_CONTACT_SINGLE_MODEL)
        if (edition != 0) return 2;
        const auto& model = CompiledModel(female != 0);
#else
        const auto& model = CompiledModel(female != 0, edition ? ContactRuntimeEdition::vr : ContactRuntimeEdition::flat);
#endif
        const auto capsules = Evaluate(model, values, weight);
        std::cout << model.identity << ' ' << capsules.size();
        for (const auto& cap : capsules) {
            for (const auto value : cap.p1) std::cout << ' ' << value;
            for (const auto value : cap.p2) std::cout << ' ' << value;
            std::cout << ' ' << cap.radius;
        }
        std::cout << '\n';
    }
#if !defined(CLAW_CONTACT_SINGLE_MODEL)
    try { (void)CompiledModel(false, static_cast<ContactRuntimeEdition>(2)); return 3; }
    catch (const std::invalid_argument&) {}
#endif
    return std::cin.eof() ? 0 : 2;
}
