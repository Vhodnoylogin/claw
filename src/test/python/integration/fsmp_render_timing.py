"""Place compositor frames and native FSMP pairs on the same host clock."""

from bisect import bisect_left, bisect_right


_SYSTEM_TIME_TICKS_PER_SECOND = 10_000_000


def _positive_integer(value):
    return type(value) is int and value > 0


def _qpc_bounds(system_time, frequency):
    # WinRT exposes TimeSpan in 100 ns intervals. Include a full source tick
    # on either side before projecting the interval onto raw QPC.
    unit = _SYSTEM_TIME_TICKS_PER_SECOND
    lower = (system_time - 1) * frequency // unit
    upper = ((system_time + 1) * frequency + unit - 1) // unit
    return lower, upper


def bracket_render_frames(frames, pairs, *, qpc_frequency, capture_start, capture_end, maximum_gap_ticks):
    """Return surrounding native pair numbers for independently captured frames.

    Pass exact compositor times and rows from a validated native trace. The
    result bounds proximity on one host clock. It does not identify which
    solver update the renderer consumed.
    """
    if (not all(map(_positive_integer, (qpc_frequency, capture_start, capture_end, maximum_gap_ticks)))
            or capture_start >= capture_end):
        raise ValueError("Expected one positive, finite host capture interval")
    if (len(pairs) < 2 or any(not all(_positive_integer(row[key]) for key in ("pair", "preQpc", "postQpc"))
                             or row["preQpc"] >= row["postQpc"] for row in pairs)
            or any(b["pair"] != a["pair"] + 1 or b["preQpc"] <= a["postQpc"]
                   for a, b in zip(pairs, pairs[1:]))):
        raise ValueError("Expected contiguous native FSMP trace pairs")
    before = [row["preQpc"] for row in pairs]
    after = [row["postQpc"] for row in pairs]
    if not frames:
        raise ValueError("Expected at least one compositor frame")
    results = []
    previous_source = 0
    previous_receipt = capture_start
    for index, frame in enumerate(frames):
        source, receipt = frame["systemRelativeTime100ns"], frame["receiptQpc"]
        if (type(frame["index"]) is not int or frame["index"] != index
                or not _positive_integer(source) or source <= previous_source
                or not _positive_integer(receipt) or not previous_receipt <= receipt <= capture_end):
            raise ValueError("Compositor frame sequence or capture receipts do not advance in order")
        previous_source, previous_receipt = source, receipt
        lower, upper = _qpc_bounds(source, qpc_frequency)
        entry = {"index": index, "compositorQpcRange": [lower, upper], "receiptQpc": receipt}
        if lower < capture_start or upper > receipt:
            entry["status"] = "outside-capture-clock"
        else:
            left = bisect_left(after, lower) - 1
            right = bisect_right(before, upper)
            if left < 0 or right >= len(pairs):
                entry["status"] = "outside-solver-trace"
            elif upper - after[left] > maximum_gap_ticks or before[right] - lower > maximum_gap_ticks:
                entry["status"] = "solver-gap"
            else:
                entry.update(status="bounded", beforePair=pairs[left]["pair"], afterPair=pairs[right]["pair"],
                             beforePostQpc=after[left], afterPreQpc=before[right])
        results.append(entry)
    return results
