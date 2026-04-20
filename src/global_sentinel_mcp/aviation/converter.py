"""Pure-Python FAA N-Number ↔ ICAO24 hex converter.

Ported from guillaumemichel/icao-nnumber_converter (MIT).
Implements the mixed-base bucket math for US civil aircraft registrations.

N-Numbers: N1 through N99999 (with optional 1–2 letter suffix)
ICAO24 range: a00001 through adf7c7
"""

from __future__ import annotations

# ---------- constants ----------

ICAO_OFFSET = 0xA00001

# Alphabetic set: A–Z excluding I and O (24 letters)
ALPHA_SET = "ABCDEFGHJKLMNPQRSTUVWXYZ"

# Digit set: 0–9
DIGIT_SET = "0123456789"

# Combined set for the 5th position
ALL_SET = ALPHA_SET + DIGIT_SET

# ---------- bucket sizes ----------
# suffix_size: 1 (empty) + 24 (single alpha) + 24*24 (two alpha) = 601
SUFFIX_SIZE = 601

# bucket4: 1 (empty) + 24 (alpha) + 10 (digit) = 35
BUCKET4_SIZE = 35

# bucket3: suffix_size + 10 * bucket4_size = 601 + 350 = 951
BUCKET3_SIZE = 951

# bucket2: suffix_size + 10 * bucket3_size = 601 + 9510 = 10111
BUCKET2_SIZE = 10111

# bucket1: suffix_size + 10 * bucket2_size = 601 + 101110 = 101711
BUCKET1_SIZE = 101711


def _get_suffix(offset: int) -> str:
    """Decode a suffix offset into 0–2 alpha characters.

    0 → empty, 1–24 → single alpha, 25–600 → two alpha chars.
    """
    if offset <= 0:
        return ""
    if offset <= len(ALPHA_SET):
        return ALPHA_SET[offset - 1]
    # Two-character suffix
    adj = offset - len(ALPHA_SET) - 1
    first = adj // len(ALPHA_SET)
    second = adj % len(ALPHA_SET)
    if first >= len(ALPHA_SET):
        return ""
    return ALPHA_SET[first] + ALPHA_SET[second]


def _suffix_to_offset(suffix: str) -> int | None:
    """Encode a 0–2 alpha suffix string to its numeric offset."""
    if suffix == "":
        return 0
    if len(suffix) == 1:
        if suffix not in ALPHA_SET:
            return None
        return ALPHA_SET.index(suffix) + 1
    if len(suffix) == 2:
        if suffix[0] not in ALPHA_SET or suffix[1] not in ALPHA_SET:
            return None
        return (
            len(ALPHA_SET)
            + 1
            + ALPHA_SET.index(suffix[0]) * len(ALPHA_SET)
            + ALPHA_SET.index(suffix[1])
        )
    return None


def nnumber_to_icao(n_number: str) -> str | None:
    """Convert an FAA N-Number (e.g. ``N12345``) to a lowercase ICAO24 hex string.

    Returns ``None`` if the input is not a valid US N-Number.
    """
    if not n_number:
        return None
    tail = n_number.upper().lstrip("N")
    if not tail or len(tail) > 5:
        return None

    # Split into leading digits and trailing alpha suffix
    digits = ""
    suffix = ""
    for i, ch in enumerate(tail):
        if ch in DIGIT_SET:
            digits += ch
        else:
            suffix = tail[i:]
            break

    if not digits or digits[0] == "0":
        return None
    if len(digits) + len(suffix) > 5:
        return None
    for ch in suffix:
        if ch not in ALPHA_SET:
            return None
    if len(suffix) > 2:
        return None
    # 5 digits → no suffix allowed; 4 digits → max 1 alpha suffix
    if len(digits) == 5 and suffix:
        return None
    if len(digits) == 4 and len(suffix) > 1:
        return None

    offset = (int(digits[0]) - 1) * BUCKET1_SIZE

    if len(digits) == 1:
        s = _suffix_to_offset(suffix)
        if s is None:
            return None
        offset += s
    else:
        offset += SUFFIX_SIZE + int(digits[1]) * BUCKET2_SIZE
        if len(digits) == 2:
            s = _suffix_to_offset(suffix)
            if s is None:
                return None
            offset += s
        else:
            offset += SUFFIX_SIZE + int(digits[2]) * BUCKET3_SIZE
            if len(digits) == 3:
                s = _suffix_to_offset(suffix)
                if s is None:
                    return None
                offset += s
            else:
                offset += SUFFIX_SIZE + int(digits[3]) * BUCKET4_SIZE
                if len(digits) == 4:
                    # bucket4: 0=empty, 1–24=alpha suffix
                    if suffix == "":
                        pass  # offset += 0
                    else:
                        offset += ALPHA_SET.index(suffix) + 1
                else:
                    # 5 digits: bucket4 position = 1 + 24 + d5
                    offset += 1 + len(ALPHA_SET) + int(digits[4])

    icao_int = ICAO_OFFSET + offset
    return f"{icao_int:06x}"


def icao_to_nnumber(icao: str) -> str | None:
    """Convert a lowercase ICAO24 hex string to an FAA N-Number.

    Returns ``None`` if the ICAO address is outside the US civil range.
    """
    try:
        icao_int = int(icao, 16)
    except (ValueError, TypeError):
        return None

    offset = icao_int - ICAO_OFFSET
    if offset < 0 or offset >= 9 * BUCKET1_SIZE:
        return None

    # First digit: 1–9
    d1 = offset // BUCKET1_SIZE
    rem = offset % BUCKET1_SIZE
    digits = str(d1 + 1)

    if rem < SUFFIX_SIZE:
        return "N" + digits + _get_suffix(rem)

    rem -= SUFFIX_SIZE

    # Second digit: 0–9
    d2 = rem // BUCKET2_SIZE
    rem = rem % BUCKET2_SIZE
    if d2 > 9:
        return None
    digits += str(d2)

    if rem < SUFFIX_SIZE:
        return "N" + digits + _get_suffix(rem)

    rem -= SUFFIX_SIZE

    # Third digit: 0–9
    d3 = rem // BUCKET3_SIZE
    rem = rem % BUCKET3_SIZE
    if d3 > 9:
        return None
    digits += str(d3)

    if rem < SUFFIX_SIZE:
        return "N" + digits + _get_suffix(rem)

    rem -= SUFFIX_SIZE

    # Fourth digit: 0–9
    d4 = rem // BUCKET4_SIZE
    rem = rem % BUCKET4_SIZE
    if d4 > 9:
        return None
    digits += str(d4)

    # bucket4: 0=empty, 1–24=alpha, 25–34=5th digit
    if rem == 0:
        return "N" + digits
    if 1 <= rem <= len(ALPHA_SET):
        return "N" + digits + ALPHA_SET[rem - 1]
    digit_idx = rem - 1 - len(ALPHA_SET)
    if 0 <= digit_idx < len(DIGIT_SET):
        return "N" + digits + DIGIT_SET[digit_idx]

    return None
