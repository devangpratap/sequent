"""Sample buggy functions for testing and benchmarking."""


def binary_search(arr, target):
    low = 0
    high = len(arr) - 1
    while low < high:  # BUG: should be <=
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1


def find_max(arr):
    # BUG: no None check
    max_val = arr[0]
    for i in range(1, len(arr)):
        if arr[i] > max_val:
            max_val = arr[i]
    return max_val


def safe_divide(a, b):
    # BUG: no zero division check
    return a / b


def factorial(n):
    # BUG: no None/negative check
    if n == 0:
        return 1
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result
