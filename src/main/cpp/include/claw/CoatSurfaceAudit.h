#pragma once
#include "claw/ColourMath.h"
#include <charconv>
#include <limits>
#include <string>
#include <vector>

namespace claw::appearance {
inline constexpr std::size_t coatAuditMaxObjects = 512, coatAuditMaxSurfaces = 64;
inline constexpr std::size_t coatAuditMaxName = 128, coatAuditMaxPath = 512;
inline constexpr std::uint64_t coatAuditMaxAgeMs = 2000;

// Plain observations only. No renderer/scene pointer or desired texture/tint
// enters this transport. Lease booleans are explicit comparisons with CLAW's
// retained witnesses, rather than an assertion about arbitrary external owners.
struct CoatSurfaceObservation {
    std::string name;
    bool managed{};
    std::optional<std::int32_t> materialType, feature;
    std::optional<std::string> diffusePath, diffuseResource;
    std::optional<RGB> tint;
    std::optional<float> materialAlpha, propertyAlpha;
    std::optional<std::uint64_t> shaderFlags;
    // -1 unavailable, 0 absent, 1 false boolean, 2 true boolean, 3 other type.
    int noTint{-1};
    bool tracked{}, ownProperty{}, ownMaterial{}, ownGuard{}, ownTextureSet{}, ownDiffuse{}, healthyLease{};
};
inline std::string coatAuditQuote(std::string_view value) {
    constexpr char hex[] = "0123456789abcdef";
    std::string result{"\""};
    for (unsigned char byte : value) {
        if (byte == '"' || byte == '\\') { result += '\\'; result += static_cast<char>(byte); }
        else if (byte < 32 || byte >= 127) {
            result += "\\u00"; result += hex[byte >> 4]; result += hex[byte & 15];
        } else result += static_cast<char>(byte);
    }
    return result + '"';
}
inline std::string coatAuditNumber(float value) {
    if (!std::isfinite(value)) return "null";
    char text[64]{};
    const auto [end, ec] = std::to_chars(text, text + sizeof(text), value);
    return ec == std::errc{} ? std::string(text, end) : "null";
}
inline std::string coatAuditRows(const std::vector<CoatSurfaceObservation>& rows) {
    if (rows.empty() || rows.size() > coatAuditMaxSurfaces) return {};
    std::string result{"["};
    const auto boolean = [](bool value) { return value ? "true" : "false"; };
    for (const auto& row : rows) {
        if (row.name.size() > coatAuditMaxName || (row.diffusePath && row.diffusePath->size() > coatAuditMaxPath) ||
            (row.diffuseResource && row.diffuseResource->size() > coatAuditMaxPath) || row.noTint < -1 || row.noTint > 3) return {};
        if (result.size() > 1) result += ',';
        result += "{\"name\":" + coatAuditQuote(row.name) + ",\"managed\":" + boolean(row.managed);
        result += ",\"materialType\":" + (row.materialType ? std::to_string(*row.materialType) : "null");
        result += ",\"feature\":" + (row.feature ? std::to_string(*row.feature) : "null");
        result += ",\"diffusePath\":" + (row.diffusePath ? coatAuditQuote(*row.diffusePath) : "null");
        result += ",\"diffuseResource\":" + (row.diffuseResource ? coatAuditQuote(*row.diffuseResource) : "null");
        result += ",\"tint\":";
        if (row.tint) result += '[' + coatAuditNumber((*row.tint)[0]) + ',' + coatAuditNumber((*row.tint)[1]) + ',' + coatAuditNumber((*row.tint)[2]) + ']';
        else result += "null";
        result += ",\"materialAlpha\":" + (row.materialAlpha ? coatAuditNumber(*row.materialAlpha) : "null");
        result += ",\"propertyAlpha\":" + (row.propertyAlpha ? coatAuditNumber(*row.propertyAlpha) : "null");
        // Decimal string preserves all 64 flag bits in JSON consumers.
        result += ",\"shaderFlags\":" + (row.shaderFlags ? coatAuditQuote(std::to_string(*row.shaderFlags)) : "null");
        result += ",\"noTint\":" + std::to_string(row.noTint) + ",\"tracked\":" + boolean(row.tracked);
        result += ",\"ownProperty\":" + std::string(boolean(row.ownProperty)) + ",\"ownMaterial\":" + boolean(row.ownMaterial);
        result += ",\"ownGuard\":" + std::string(boolean(row.ownGuard)) + ",\"ownTextureSet\":" + boolean(row.ownTextureSet);
        result += ",\"ownDiffuse\":" + std::string(boolean(row.ownDiffuse)) + ",\"healthyLease\":" + boolean(row.healthyLease) + '}';
        if (result.size() > 64000) return {};
    }
    return result + ']';
}

// A request revokes the previous sample immediately. Callers supply a monotonic
// main-task clock; reads never resolve an actor or touch a material. Stale or
// missing data is empty, never a cached desired/application result.
class CoatSurfaceAuditCache final {
public:
    bool begin(std::uint64_t token) {
        if (!token || pending_) return false;
        invalidate(); pending_ = token; return true;
    }
    void invalidate() { pending_ = 0; sampledAt_ = 0; payload_.clear(); }
    bool pending(std::uint64_t token) const { return token && pending_ == token; }
    void cancel(std::uint64_t token) { if (pending(token)) invalidate(); }
    bool publish(std::uint64_t token, std::uint64_t generation, std::uint64_t now,
        bool leaseRootCurrent, const std::vector<CoatSurfaceObservation>& rows) {
        if (!pending(token)) return false;
        if (!generation) { cancel(token); return false; }
        auto body = coatAuditRows(rows);
        if (body.empty()) { cancel(token); return false; }
        payload_ = "{\"schema\":1,\"stringEncoding\":\"bytes-u00xx\",\"sample\":" + coatAuditQuote(std::to_string(token)) +
            ",\"modelGeneration\":" + coatAuditQuote(std::to_string(generation)) +
            ",\"leaseRootCurrent\":" + (leaseRootCurrent ? "true" : "false") + ",\"surfaces\":" + body;
        pending_ = 0; sampledAt_ = now; return true;
    }
    [[nodiscard]] std::string read(std::uint64_t now) const {
        if (pending_ || payload_.empty() || now < sampledAt_ || now - sampledAt_ > coatAuditMaxAgeMs) return {};
        return payload_ + ",\"ageMs\":" + std::to_string(now - sampledAt_) + '}';
    }
private:
    std::uint64_t pending_{}, sampledAt_{};
    std::string payload_;
};
}
