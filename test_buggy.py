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


def safe_divide(a, b):
    if a is None or b is None:
        return None
    if b == 0:
        return None
    return a / b


def find_max(arr):
    max_val = arr[0]  # BUG: no None/empty check
    for i in range(1, len(arr)):
        if arr[i] > max_val:
            max_val = arr[i]
    return max_val
