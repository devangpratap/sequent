"""
20 benchmark cases: 14 buggy, 6 clean.
Designed to test edge cases that LLMs commonly miss.
"""

BENCHMARK_CASES = [
    # --- BUGGY: Off-by-one ---
    {
        "name": "binary_search_obo",
        "code": "def binary_search(arr, target):\n    low = 0\n    high = len(arr) - 1\n    while low < high:\n        mid = (low + high) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            low = mid + 1\n        else:\n            high = mid - 1\n    return -1",
        "is_buggy": True,
        "bug_description": "while low < high should be low <= high — misses single-element case",
    },
    {
        "name": "bubble_sort_obo",
        "code": "def bubble_sort(arr):\n    n = len(arr)\n    for i in range(n):\n        for j in range(0, n - i):\n            if arr[j] > arr[j + 1]:\n                arr[j], arr[j + 1] = arr[j + 1], arr[j]\n    return arr",
        "is_buggy": True,
        "bug_description": "range(0, n-i) should be range(0, n-i-1) — index out of bounds on last element",
    },

    # --- BUGGY: None deref ---
    {
        "name": "find_max_none",
        "code": "def find_max(arr):\n    max_val = arr[0]\n    for i in range(1, len(arr)):\n        if arr[i] > max_val:\n            max_val = arr[i]\n    return max_val",
        "is_buggy": True,
        "bug_description": "No None check — crashes on None input",
    },
    {
        "name": "reverse_string_none",
        "code": "def reverse_string(s):\n    return s[::-1]",
        "is_buggy": True,
        "bug_description": "No None check — crashes on None input",
    },
    {
        "name": "sum_list_none",
        "code": "def sum_list(lst):\n    total = 0\n    for x in lst:\n        total += x\n    return total",
        "is_buggy": True,
        "bug_description": "No None check — crashes on None input",
    },

    # --- BUGGY: Division by zero ---
    {
        "name": "average_no_guard",
        "code": "def average(nums):\n    return sum(nums) / len(nums)",
        "is_buggy": True,
        "bug_description": "Division by zero when nums is empty",
    },
    {
        "name": "normalize_no_guard",
        "code": "def normalize(values, total):\n    return [v / total for v in values]",
        "is_buggy": True,
        "bug_description": "Division by zero when total is 0",
    },

    # --- BUGGY: Wrong operator ---
    {
        "name": "is_even_wrong_op",
        "code": "def is_even(n):\n    return n % 2 == 1",
        "is_buggy": True,
        "bug_description": "Should be n % 2 == 0 — returns True for odd numbers",
    },
    {
        "name": "min_of_two_wrong",
        "code": "def min_of_two(a, b):\n    if a > b:\n        return a\n    return b",
        "is_buggy": True,
        "bug_description": "Returns max instead of min — comparison is inverted",
    },

    # --- BUGGY: Integer overflow / unsafe arithmetic ---
    {
        "name": "factorial_no_guard",
        "code": "def factorial(n):\n    result = 1\n    for i in range(1, n + 1):\n        result *= i\n    return result",
        "is_buggy": True,
        "bug_description": "No guard for negative n — range(1, n+1) produces empty range silently",
    },

    # --- BUGGY: Boundary error ---
    {
        "name": "second_largest_no_check",
        "code": "def second_largest(arr):\n    arr.sort()\n    return arr[-2]",
        "is_buggy": True,
        "bug_description": "No length check — crashes on empty or single-element array",
    },
    {
        "name": "pop_empty",
        "code": "def safe_pop(stack):\n    return stack.pop()",
        "is_buggy": True,
        "bug_description": "No empty check — crashes on empty stack",
    },

    # --- BUGGY: Subtle logic ---
    {
        "name": "remove_dupes_mutate",
        "code": "def remove_dupes(lst):\n    for item in lst:\n        if lst.count(item) > 1:\n            lst.remove(item)\n    return lst",
        "is_buggy": True,
        "bug_description": "Mutating list while iterating — skips elements",
    },
    {
        "name": "swap_wrong",
        "code": "def swap(a, b):\n    a = b\n    b = a\n    return a, b",
        "is_buggy": True,
        "bug_description": "Overwrites a before saving — both become b",
    },

    # --- CLEAN: Correct functions ---
    {
        "name": "binary_search_correct",
        "code": "def binary_search(arr, target):\n    if arr is None or len(arr) == 0:\n        return -1\n    low = 0\n    high = len(arr) - 1\n    while low <= high:\n        mid = (low + high) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            low = mid + 1\n        else:\n            high = mid - 1\n    return -1",
        "is_buggy": False,
        "bug_description": "Correct implementation",
    },
    {
        "name": "find_max_correct",
        "code": "def find_max(arr):\n    if arr is None or len(arr) == 0:\n        return None\n    max_val = arr[0]\n    for i in range(1, len(arr)):\n        if arr[i] > max_val:\n            max_val = arr[i]\n    return max_val",
        "is_buggy": False,
        "bug_description": "Correct implementation",
    },
    {
        "name": "safe_divide_correct",
        "code": "def safe_divide(a, b):\n    if a is None or b is None:\n        return None\n    if b == 0:\n        return None\n    return a / b",
        "is_buggy": False,
        "bug_description": "Correct implementation",
    },
    {
        "name": "fibonacci_correct",
        "code": "def fibonacci(n):\n    if n is None or n < 0:\n        return None\n    if n <= 1:\n        return n\n    a, b = 0, 1\n    for _ in range(2, n + 1):\n        a, b = b, a + b\n    return b",
        "is_buggy": False,
        "bug_description": "Correct implementation",
    },
    {
        "name": "is_palindrome_correct",
        "code": "def is_palindrome(s):\n    if s is None:\n        return False\n    s = s.lower()\n    left = 0\n    right = len(s) - 1\n    while left < right:\n        if s[left] != s[right]:\n            return False\n        left += 1\n        right -= 1\n    return True",
        "is_buggy": False,
        "bug_description": "Correct implementation",
    },
    {
        "name": "gcd_correct",
        "code": "def gcd(a, b):\n    if a is None or b is None:\n        return None\n    a = abs(a)\n    b = abs(b)\n    while b != 0:\n        a, b = b, a % b\n    return a",
        "is_buggy": False,
        "bug_description": "Correct implementation",
    },
]
