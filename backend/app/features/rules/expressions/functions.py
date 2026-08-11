"""Built-in functions for expression evaluation."""

import math
import re
from datetime import datetime, timedelta
from statistics import mean, median
from typing import Any


def fn_sum(*args: Any) -> float:
    """Sum of numeric values."""
    total = 0.0
    for arg in args:
        if isinstance(arg, (list, tuple)):
            total += sum(float(x) for x in arg if x is not None)
        elif arg is not None:
            try:
                total += float(arg)
            except (ValueError, TypeError):
                pass
    return total


def fn_avg(*args: Any) -> float:
    """Average of numeric values."""
    values = []
    for arg in args:
        if isinstance(arg, (list, tuple)):
            values.extend(float(x) for x in arg if x is not None)
        elif arg is not None:
            try:
                values.append(float(arg))
            except (ValueError, TypeError):
                pass
    return mean(values) if values else 0.0


def fn_count(*args: Any) -> int:
    """Count of values."""
    total = 0
    for arg in args:
        if isinstance(arg, (list, tuple)):
            total += len([x for x in arg if x is not None])
        elif arg is not None:
            total += 1
    return total


def fn_min(*args: Any) -> Any:
    """Minimum value."""
    values = []
    for arg in args:
        if isinstance(arg, (list, tuple)):
            values.extend(x for x in arg if x is not None)
        elif arg is not None:
            values.append(arg)
    if not values:
        return None
    try:
        return min(float(x) for x in values)
    except (ValueError, TypeError):
        return min(str(x) for x in values)


def fn_max(*args: Any) -> Any:
    """Maximum value."""
    values = []
    for arg in args:
        if isinstance(arg, (list, tuple)):
            values.extend(x for x in arg if x is not None)
        elif arg is not None:
            values.append(arg)
    if not values:
        return None
    try:
        return max(float(x) for x in values)
    except (ValueError, TypeError):
        return max(str(x) for x in values)


def fn_median(*args: Any) -> float:
    """Median of numeric values."""
    values = []
    for arg in args:
        if isinstance(arg, (list, tuple)):
            values.extend(float(x) for x in arg if x is not None)
        elif arg is not None:
            try:
                values.append(float(arg))
            except (ValueError, TypeError):
                pass
    return median(values) if values else 0.0


def fn_round(value: Any, decimals: int = 0) -> float:
    """Round to specified decimal places."""
    if value is None:
        return 0.0
    try:
        return round(float(value), int(decimals))
    except (ValueError, TypeError):
        return 0.0


def fn_abs(value: Any) -> float:
    """Absolute value."""
    if value is None:
        return 0.0
    try:
        return abs(float(value))
    except (ValueError, TypeError):
        return 0.0


def fn_ceil(value: Any) -> int:
    """Ceiling (round up)."""
    if value is None:
        return 0
    try:
        return math.ceil(float(value))
    except (ValueError, TypeError):
        return 0


def fn_floor(value: Any) -> int:
    """Floor (round down)."""
    if value is None:
        return 0
    try:
        return math.floor(float(value))
    except (ValueError, TypeError):
        return 0


def fn_if(condition: Any, true_value: Any, false_value: Any) -> Any:
    """Conditional value."""
    return true_value if condition else false_value


def fn_coalesce(*args: Any) -> Any:
    """First non-null value."""
    for arg in args:
        if arg is not None and arg != "":
            return arg
    return None


def fn_is_null(value: Any) -> bool:
    """Check if value is null."""
    return value is None or value == ""


def fn_if_null(value: Any, default: Any) -> Any:
    """Return default if value is null."""
    return value if value is not None and value != "" else default


def fn_concat(*args: Any) -> str:
    """Concatenate strings."""
    return "".join(str(arg) if arg is not None else "" for arg in args)


def fn_upper(value: Any) -> str:
    """Convert to uppercase."""
    return str(value).upper() if value is not None else ""


def fn_lower(value: Any) -> str:
    """Convert to lowercase."""
    return str(value).lower() if value is not None else ""


def fn_trim(value: Any) -> str:
    """Remove whitespace."""
    return str(value).strip() if value is not None else ""


def fn_substring(value: Any, start: int, length: int | None = None) -> str:
    """Extract substring."""
    if value is None:
        return ""
    s = str(value)
    if length is None:
        return s[int(start):]
    return s[int(start):int(start) + int(length)]


def fn_replace(value: Any, old: str, new: str) -> str:
    """Replace occurrences in string."""
    if value is None:
        return ""
    return str(value).replace(old, new)


def fn_len(value: Any) -> int:
    """Length of string or list."""
    if value is None:
        return 0
    if isinstance(value, (list, tuple)):
        return len(value)
    return len(str(value))


def fn_date_diff(date1: Any, date2: Any, unit: str = "days") -> float:
    """Difference between dates."""
    def parse_date(d: Any) -> datetime | None:
        if isinstance(d, datetime):
            return d
        if d is None:
            return None
        try:
            return datetime.fromisoformat(str(d).replace("Z", "+00:00"))
        except ValueError:
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"]:
                try:
                    return datetime.strptime(str(d), fmt)
                except ValueError:
                    continue
        return None

    d1 = parse_date(date1)
    d2 = parse_date(date2)

    if d1 is None or d2 is None:
        return 0.0

    diff = d1 - d2

    if unit == "days":
        return diff.days
    elif unit == "hours":
        return diff.total_seconds() / 3600
    elif unit == "minutes":
        return diff.total_seconds() / 60
    elif unit == "seconds":
        return diff.total_seconds()
    elif unit == "weeks":
        return diff.days / 7
    elif unit == "months":
        return diff.days / 30
    elif unit == "years":
        return diff.days / 365

    return diff.days


def fn_date_add(date: Any, amount: int, unit: str = "days") -> str:
    """Add to a date."""
    def parse_date(d: Any) -> datetime | None:
        if isinstance(d, datetime):
            return d
        if d is None:
            return None
        try:
            return datetime.fromisoformat(str(d).replace("Z", "+00:00"))
        except ValueError:
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]:
                try:
                    return datetime.strptime(str(d), fmt)
                except ValueError:
                    continue
        return None

    d = parse_date(date)
    if d is None:
        return ""

    if unit == "days":
        result = d + timedelta(days=amount)
    elif unit == "hours":
        result = d + timedelta(hours=amount)
    elif unit == "minutes":
        result = d + timedelta(minutes=amount)
    elif unit == "seconds":
        result = d + timedelta(seconds=amount)
    elif unit == "weeks":
        result = d + timedelta(weeks=amount)
    else:
        result = d

    return result.isoformat()


def fn_format_date(date: Any, format_str: str = "%Y-%m-%d") -> str:
    """Format a date."""
    def parse_date(d: Any) -> datetime | None:
        if isinstance(d, datetime):
            return d
        if d is None:
            return None
        try:
            return datetime.fromisoformat(str(d).replace("Z", "+00:00"))
        except ValueError:
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]:
                try:
                    return datetime.strptime(str(d), fmt)
                except ValueError:
                    continue
        return None

    d = parse_date(date)
    if d is None:
        return ""

    return d.strftime(format_str)


def fn_regex_match(value: Any, pattern: str) -> bool:
    """Check if value matches regex."""
    if value is None:
        return False
    try:
        return bool(re.match(pattern, str(value)))
    except re.error:
        return False


def fn_regex_extract(value: Any, pattern: str, group: int = 0) -> str:
    """Extract using regex."""
    if value is None:
        return ""
    try:
        match = re.search(pattern, str(value))
        if match:
            return match.group(group)
    except (re.error, IndexError):
        pass
    return ""


BUILTIN_FUNCTIONS = {
    "sum": fn_sum,
    "avg": fn_avg,
    "count": fn_count,
    "min": fn_min,
    "max": fn_max,
    "median": fn_median,
    "round": fn_round,
    "abs": fn_abs,
    "ceil": fn_ceil,
    "floor": fn_floor,
    "if": fn_if,
    "coalesce": fn_coalesce,
    "is_null": fn_is_null,
    "if_null": fn_if_null,
    "concat": fn_concat,
    "upper": fn_upper,
    "lower": fn_lower,
    "trim": fn_trim,
    "substring": fn_substring,
    "replace": fn_replace,
    "len": fn_len,
    "date_diff": fn_date_diff,
    "date_add": fn_date_add,
    "format_date": fn_format_date,
    "regex_match": fn_regex_match,
    "regex_extract": fn_regex_extract,
}
