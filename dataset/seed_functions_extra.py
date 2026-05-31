"""
Programmatically generated seed functions for dataset expansion.
~120 additional functions covering diverse patterns.
"""

EXTRA_SEED_FUNCTIONS = [
    # --- Simple math ---
    {"name": "abs_val", "code": '''
def abs_val(x):
    if x is None:
        return None
    if x < 0:
        return -x
    return x
''', "category": "math"},
    {"name": "sign", "code": '''
def sign(x):
    if x is None:
        return None
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0
''', "category": "math"},
    {"name": "max_of_three", "code": '''
def max_of_three(a, b, c):
    if a is None or b is None or c is None:
        return None
    result = a
    if b > result:
        result = b
    if c > result:
        result = c
    return result
''', "category": "math"},
    {"name": "min_of_three", "code": '''
def min_of_three(a, b, c):
    if a is None or b is None or c is None:
        return None
    result = a
    if b < result:
        result = b
    if c < result:
        result = c
    return result
''', "category": "math"},
    {"name": "is_even", "code": '''
def is_even(n):
    if n is None:
        return None
    return n % 2 == 0
''', "category": "math"},
    {"name": "is_odd", "code": '''
def is_odd(n):
    if n is None:
        return None
    return n % 2 != 0
''', "category": "math"},
    {"name": "celsius_to_fahrenheit", "code": '''
def celsius_to_fahrenheit(c):
    if c is None:
        return None
    return c * 9 / 5 + 32
''', "category": "math"},
    {"name": "distance_2d", "code": '''
def distance_2d(x1, y1, x2, y2):
    if x1 is None or y1 is None or x2 is None or y2 is None:
        return None
    dx = x2 - x1
    dy = y2 - y1
    return (dx * dx + dy * dy) ** 0.5
''', "category": "math"},
    {"name": "average_list", "code": '''
def average_list(arr):
    if arr is None or len(arr) == 0:
        return None
    total = 0
    for x in arr:
        total += x
    return total / len(arr)
''', "category": "math"},
    {"name": "median", "code": '''
def median(arr):
    if arr is None or len(arr) == 0:
        return None
    sorted_arr = sorted(arr)
    n = len(sorted_arr)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_arr[mid - 1] + sorted_arr[mid]) / 2
    return sorted_arr[mid]
''', "category": "math"},
    {"name": "variance", "code": '''
def variance(arr):
    if arr is None or len(arr) < 2:
        return None
    n = len(arr)
    mean = sum(arr) / n
    total = 0
    for x in arr:
        total += (x - mean) ** 2
    return total / (n - 1)
''', "category": "math"},
    {"name": "dot_product", "code": '''
def dot_product(a, b):
    if a is None or b is None:
        return None
    if len(a) != len(b):
        return None
    result = 0
    for i in range(len(a)):
        result += a[i] * b[i]
    return result
''', "category": "math"},
    {"name": "is_power_of_two", "code": '''
def is_power_of_two(n):
    if n is None or n <= 0:
        return False
    return n & (n - 1) == 0
''', "category": "bit"},
    {"name": "next_power_of_two", "code": '''
def next_power_of_two(n):
    if n is None or n <= 0:
        return 1
    power = 1
    while power < n:
        power *= 2
    return power
''', "category": "math"},
    {"name": "integer_sqrt", "code": '''
def integer_sqrt(n):
    if n is None or n < 0:
        return None
    if n == 0:
        return 0
    x = n
    while x * x > n:
        x = (x + n // x) // 2
    return x
''', "category": "math"},

    # --- Array/List operations ---
    {"name": "sum_array", "code": '''
def sum_array(arr):
    if arr is None or len(arr) == 0:
        return 0
    total = 0
    for x in arr:
        total += x
    return total
''', "category": "array"},
    {"name": "reverse_array", "code": '''
def reverse_array(arr):
    if arr is None:
        return None
    result = []
    for i in range(len(arr) - 1, -1, -1):
        result.append(arr[i])
    return result
''', "category": "array"},
    {"name": "find_index", "code": '''
def find_index(arr, target):
    if arr is None:
        return -1
    for i in range(len(arr)):
        if arr[i] == target:
            return i
    return -1
''', "category": "array"},
    {"name": "count_occurrences", "code": '''
def count_occurrences(arr, target):
    if arr is None:
        return 0
    count = 0
    for x in arr:
        if x == target:
            count += 1
    return count
''', "category": "array"},
    {"name": "min_array", "code": '''
def min_array(arr):
    if arr is None or len(arr) == 0:
        return None
    result = arr[0]
    for i in range(1, len(arr)):
        if arr[i] < result:
            result = arr[i]
    return result
''', "category": "array"},
    {"name": "second_max", "code": '''
def second_max(arr):
    if arr is None or len(arr) < 2:
        return None
    first = arr[0]
    second = arr[1]
    if second > first:
        first, second = second, first
    for i in range(2, len(arr)):
        if arr[i] > first:
            second = first
            first = arr[i]
        elif arr[i] > second:
            second = arr[i]
    return second
''', "category": "array"},
    {"name": "intersect_arrays", "code": '''
def intersect_arrays(a, b):
    if a is None or b is None:
        return None
    result = []
    b_set = set(b)
    for x in a:
        if x in b_set:
            result.append(x)
            b_set.discard(x)
    return result
''', "category": "array"},
    {"name": "union_arrays", "code": '''
def union_arrays(a, b):
    if a is None or b is None:
        return None
    seen = set()
    result = []
    for x in a:
        if x not in seen:
            seen.add(x)
            result.append(x)
    for x in b:
        if x not in seen:
            seen.add(x)
            result.append(x)
    return result
''', "category": "array"},
    {"name": "difference_arrays", "code": '''
def difference_arrays(a, b):
    if a is None or b is None:
        return None
    b_set = set(b)
    result = []
    for x in a:
        if x not in b_set:
            result.append(x)
    return result
''', "category": "array"},
    {"name": "zip_arrays", "code": '''
def zip_arrays(a, b):
    if a is None or b is None:
        return None
    result = []
    length = min(len(a), len(b))
    for i in range(length):
        result.append((a[i], b[i]))
    return result
''', "category": "array"},
    {"name": "interleave", "code": '''
def interleave(a, b):
    if a is None or b is None:
        return None
    result = []
    i = 0
    j = 0
    while i < len(a) and j < len(b):
        result.append(a[i])
        result.append(b[j])
        i += 1
        j += 1
    while i < len(a):
        result.append(a[i])
        i += 1
    while j < len(b):
        result.append(b[j])
        j += 1
    return result
''', "category": "array"},
    {"name": "partition", "code": '''
def partition(arr, pivot):
    if arr is None:
        return None
    less = []
    equal = []
    greater = []
    for x in arr:
        if x < pivot:
            less.append(x)
        elif x == pivot:
            equal.append(x)
        else:
            greater.append(x)
    return less + equal + greater
''', "category": "array"},
    {"name": "running_sum", "code": '''
def running_sum(arr):
    if arr is None or len(arr) == 0:
        return arr
    result = [0] * len(arr)
    result[0] = arr[0]
    for i in range(1, len(arr)):
        result[i] = result[i - 1] + arr[i]
    return result
''', "category": "array"},
    {"name": "contains_duplicate", "code": '''
def contains_duplicate(arr):
    if arr is None:
        return False
    seen = set()
    for x in arr:
        if x in seen:
            return True
        seen.add(x)
    return False
''', "category": "array"},
    {"name": "majority_element", "code": '''
def majority_element(arr):
    if arr is None or len(arr) == 0:
        return None
    candidate = arr[0]
    count = 1
    for i in range(1, len(arr)):
        if count == 0:
            candidate = arr[i]
            count = 1
        elif arr[i] == candidate:
            count += 1
        else:
            count -= 1
    verify = 0
    for x in arr:
        if x == candidate:
            verify += 1
    if verify > len(arr) // 2:
        return candidate
    return None
''', "category": "array"},
    {"name": "move_zeros", "code": '''
def move_zeros(arr):
    if arr is None:
        return None
    write = 0
    for read in range(len(arr)):
        if arr[read] != 0:
            arr[write] = arr[read]
            write += 1
    while write < len(arr):
        arr[write] = 0
        write += 1
    return arr
''', "category": "array"},
    {"name": "find_missing_number", "code": '''
def find_missing_number(arr, n):
    if arr is None:
        return None
    expected = n * (n + 1) // 2
    actual = 0
    for x in arr:
        actual += x
    return expected - actual
''', "category": "array"},
    {"name": "max_consecutive_ones", "code": '''
def max_consecutive_ones(arr):
    if arr is None or len(arr) == 0:
        return 0
    max_count = 0
    count = 0
    for x in arr:
        if x == 1:
            count += 1
            if count > max_count:
                max_count = count
        else:
            count = 0
    return max_count
''', "category": "array"},

    # --- String operations ---
    {"name": "char_frequency", "code": '''
def char_frequency(s):
    if s is None:
        return None
    freq = {}
    for c in s:
        if c in freq:
            freq[c] += 1
        else:
            freq[c] = 1
    return freq
''', "category": "string"},
    {"name": "is_anagram", "code": '''
def is_anagram(s1, s2):
    if s1 is None or s2 is None:
        return False
    if len(s1) != len(s2):
        return False
    counts = {}
    for c in s1:
        counts[c] = counts.get(c, 0) + 1
    for c in s2:
        counts[c] = counts.get(c, 0) - 1
        if counts[c] < 0:
            return False
    return True
''', "category": "string"},
    {"name": "caesar_cipher", "code": '''
def caesar_cipher(text, shift):
    if text is None or shift is None:
        return None
    result = []
    for c in text:
        if c.isalpha():
            base = ord('A') if c.isupper() else ord('a')
            shifted = (ord(c) - base + shift) % 26 + base
            result.append(chr(shifted))
        else:
            result.append(c)
    return ''.join(result)
''', "category": "string"},
    {"name": "compress_string", "code": '''
def compress_string(s):
    if s is None or len(s) == 0:
        return s
    result = []
    count = 1
    for i in range(1, len(s)):
        if s[i] == s[i - 1]:
            count += 1
        else:
            result.append(s[i - 1])
            if count > 1:
                result.append(str(count))
            count = 1
    result.append(s[-1])
    if count > 1:
        result.append(str(count))
    return ''.join(result)
''', "category": "string"},
    {"name": "title_case", "code": '''
def title_case(s):
    if s is None:
        return None
    words = s.split()
    result = []
    for word in words:
        if len(word) > 0:
            result.append(word[0].upper() + word[1:].lower())
    return ' '.join(result)
''', "category": "string"},
    {"name": "remove_char", "code": '''
def remove_char(s, char):
    if s is None or char is None:
        return None
    result = []
    for c in s:
        if c != char:
            result.append(c)
    return ''.join(result)
''', "category": "string"},
    {"name": "first_unique_char", "code": '''
def first_unique_char(s):
    if s is None or len(s) == 0:
        return -1
    counts = {}
    for c in s:
        counts[c] = counts.get(c, 0) + 1
    for i, c in enumerate(s):
        if counts[c] == 1:
            return i
    return -1
''', "category": "string"},
    {"name": "valid_number", "code": '''
def valid_number(s):
    if s is None or len(s) == 0:
        return False
    s = s.strip()
    has_dot = False
    has_digit = False
    for i, c in enumerate(s):
        if c == '-' or c == '+':
            if i != 0:
                return False
        elif c == '.':
            if has_dot:
                return False
            has_dot = True
        elif c.isdigit():
            has_digit = True
        else:
            return False
    return has_digit
''', "category": "string"},
    {"name": "string_multiply", "code": '''
def string_multiply(s, n):
    if s is None or n is None or n < 0:
        return None
    result = []
    for _ in range(n):
        result.append(s)
    return ''.join(result)
''', "category": "string"},
    {"name": "longest_word", "code": '''
def longest_word(s):
    if s is None or len(s) == 0:
        return None
    words = s.split()
    if len(words) == 0:
        return None
    best = words[0]
    for word in words[1:]:
        if len(word) > len(best):
            best = word
    return best
''', "category": "string"},

    # --- Search/Sort ---
    {"name": "linear_search", "code": '''
def linear_search(arr, target):
    if arr is None:
        return -1
    for i in range(len(arr)):
        if arr[i] == target:
            return i
    return -1
''', "category": "search"},
    {"name": "binary_search_recursive", "code": '''
def binary_search_recursive(arr, target, low, high):
    if arr is None or low > high:
        return -1
    mid = (low + high) // 2
    if arr[mid] == target:
        return mid
    elif arr[mid] < target:
        return binary_search_recursive(arr, target, mid + 1, high)
    else:
        return binary_search_recursive(arr, target, low, mid - 1)
''', "category": "search"},
    {"name": "find_first_occurrence", "code": '''
def find_first_occurrence(arr, target):
    if arr is None or len(arr) == 0:
        return -1
    low = 0
    high = len(arr) - 1
    result = -1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            result = mid
            high = mid - 1
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return result
''', "category": "search"},
    {"name": "find_peak", "code": '''
def find_peak(arr):
    if arr is None or len(arr) == 0:
        return -1
    if len(arr) == 1:
        return 0
    if arr[0] > arr[1]:
        return 0
    if arr[-1] > arr[-2]:
        return len(arr) - 1
    for i in range(1, len(arr) - 1):
        if arr[i] > arr[i - 1] and arr[i] > arr[i + 1]:
            return i
    return -1
''', "category": "search"},
    {"name": "counting_sort", "code": '''
def counting_sort(arr, max_val):
    if arr is None or max_val is None or max_val < 0:
        return None
    counts = [0] * (max_val + 1)
    for x in arr:
        if 0 <= x <= max_val:
            counts[x] += 1
    result = []
    for i in range(max_val + 1):
        for _ in range(counts[i]):
            result.append(i)
    return result
''', "category": "sort"},
    {"name": "is_sorted", "code": '''
def is_sorted(arr):
    if arr is None or len(arr) <= 1:
        return True
    for i in range(1, len(arr)):
        if arr[i] < arr[i - 1]:
            return False
    return True
''', "category": "sort"},
    {"name": "merge_k_sorted", "code": '''
def merge_k_sorted(lists):
    if lists is None or len(lists) == 0:
        return []
    result = []
    for lst in lists:
        if lst is not None:
            result.extend(lst)
    result.sort()
    return result
''', "category": "sort"},

    # --- Stack/Queue ---
    {"name": "evaluate_rpn", "code": '''
def evaluate_rpn(tokens):
    if tokens is None or len(tokens) == 0:
        return None
    stack = []
    for token in tokens:
        if token in ('+', '-', '*', '/'):
            if len(stack) < 2:
                return None
            b = stack.pop()
            a = stack.pop()
            if token == '+':
                stack.append(a + b)
            elif token == '-':
                stack.append(a - b)
            elif token == '*':
                stack.append(a * b)
            elif token == '/':
                if b == 0:
                    return None
                stack.append(int(a / b))
        else:
            stack.append(int(token))
    return stack[0] if len(stack) == 1 else None
''', "category": "data_structure"},
    {"name": "next_greater_element", "code": '''
def next_greater_element(arr):
    if arr is None or len(arr) == 0:
        return []
    result = [-1] * len(arr)
    stack = []
    for i in range(len(arr)):
        while len(stack) > 0 and arr[stack[-1]] < arr[i]:
            idx = stack.pop()
            result[idx] = arr[i]
        stack.append(i)
    return result
''', "category": "data_structure"},
    {"name": "daily_temperatures", "code": '''
def daily_temperatures(temps):
    if temps is None or len(temps) == 0:
        return []
    result = [0] * len(temps)
    stack = []
    for i in range(len(temps)):
        while len(stack) > 0 and temps[stack[-1]] < temps[i]:
            idx = stack.pop()
            result[idx] = i - idx
        stack.append(i)
    return result
''', "category": "data_structure"},

    # --- Matrix ---
    {"name": "matrix_add", "code": '''
def matrix_add(a, b):
    if a is None or b is None:
        return None
    if len(a) != len(b) or len(a[0]) != len(b[0]):
        return None
    rows = len(a)
    cols = len(a[0])
    result = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        for j in range(cols):
            result[i][j] = a[i][j] + b[i][j]
    return result
''', "category": "math"},
    {"name": "matrix_scalar_mult", "code": '''
def matrix_scalar_mult(matrix, scalar):
    if matrix is None or scalar is None:
        return None
    rows = len(matrix)
    cols = len(matrix[0])
    result = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        for j in range(cols):
            result[i][j] = matrix[i][j] * scalar
    return result
''', "category": "math"},
    {"name": "rotate_matrix_90", "code": '''
def rotate_matrix_90(matrix):
    if matrix is None or len(matrix) == 0:
        return matrix
    n = len(matrix)
    result = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            result[j][n - 1 - i] = matrix[i][j]
    return result
''', "category": "math"},
    {"name": "search_matrix", "code": '''
def search_matrix(matrix, target):
    if matrix is None or len(matrix) == 0:
        return False
    rows = len(matrix)
    cols = len(matrix[0])
    row = 0
    col = cols - 1
    while row < rows and col >= 0:
        if matrix[row][col] == target:
            return True
        elif matrix[row][col] > target:
            col -= 1
        else:
            row += 1
    return False
''', "category": "search"},

    # --- DP ---
    {"name": "climb_stairs", "code": '''
def climb_stairs(n):
    if n is None or n < 0:
        return None
    if n <= 2:
        return max(n, 0)
    a = 1
    b = 2
    for _ in range(3, n + 1):
        a, b = b, a + b
    return b
''', "category": "dp"},
    {"name": "house_robber", "code": '''
def house_robber(nums):
    if nums is None or len(nums) == 0:
        return 0
    if len(nums) == 1:
        return nums[0]
    prev2 = 0
    prev1 = nums[0]
    for i in range(1, len(nums)):
        current = max(prev1, prev2 + nums[i])
        prev2 = prev1
        prev1 = current
    return prev1
''', "category": "dp"},
    {"name": "max_subarray_product", "code": '''
def max_subarray_product(nums):
    if nums is None or len(nums) == 0:
        return None
    max_prod = nums[0]
    cur_max = nums[0]
    cur_min = nums[0]
    for i in range(1, len(nums)):
        if nums[i] < 0:
            cur_max, cur_min = cur_min, cur_max
        cur_max = max(nums[i], cur_max * nums[i])
        cur_min = min(nums[i], cur_min * nums[i])
        max_prod = max(max_prod, cur_max)
    return max_prod
''', "category": "dp"},
    {"name": "unique_paths", "code": '''
def unique_paths(m, n):
    if m is None or n is None or m <= 0 or n <= 0:
        return 0
    dp = [[1] * n for _ in range(m)]
    for i in range(1, m):
        for j in range(1, n):
            dp[i][j] = dp[i - 1][j] + dp[i][j - 1]
    return dp[m - 1][n - 1]
''', "category": "dp"},
    {"name": "min_path_sum", "code": '''
def min_path_sum(grid):
    if grid is None or len(grid) == 0:
        return 0
    m = len(grid)
    n = len(grid[0])
    for i in range(1, m):
        grid[i][0] += grid[i - 1][0]
    for j in range(1, n):
        grid[0][j] += grid[0][j - 1]
    for i in range(1, m):
        for j in range(1, n):
            grid[i][j] += min(grid[i - 1][j], grid[i][j - 1])
    return grid[m - 1][n - 1]
''', "category": "dp"},
    {"name": "decode_ways", "code": '''
def decode_ways(s):
    if s is None or len(s) == 0 or s[0] == '0':
        return 0
    n = len(s)
    dp = [0] * (n + 1)
    dp[0] = 1
    dp[1] = 1
    for i in range(2, n + 1):
        if s[i - 1] != '0':
            dp[i] += dp[i - 1]
        two_digit = int(s[i - 2:i])
        if 10 <= two_digit <= 26:
            dp[i] += dp[i - 2]
    return dp[n]
''', "category": "dp"},

    # --- Bit manipulation ---
    {"name": "single_number", "code": '''
def single_number(nums):
    if nums is None or len(nums) == 0:
        return None
    result = 0
    for n in nums:
        result ^= n
    return result
''', "category": "bit"},
    {"name": "reverse_bits", "code": '''
def reverse_bits(n):
    if n is None:
        return None
    result = 0
    for _ in range(32):
        result = (result << 1) | (n & 1)
        n >>= 1
    return result
''', "category": "bit"},
    {"name": "count_set_bits_range", "code": '''
def count_set_bits_range(n):
    if n is None or n < 0:
        return None
    result = [0] * (n + 1)
    for i in range(1, n + 1):
        result[i] = result[i >> 1] + (i & 1)
    return result
''', "category": "bit"},

    # --- Graph/Tree ---
    {"name": "bfs_shortest_path", "code": '''
def bfs_shortest_path(graph, start, end):
    if graph is None or start is None or end is None:
        return None
    if start == end:
        return 0
    visited = set()
    queue = [(start, 0)]
    visited.add(start)
    while len(queue) > 0:
        node, dist = queue.pop(0)
        for neighbor in graph.get(node, []):
            if neighbor == end:
                return dist + 1
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, dist + 1))
    return -1
''', "category": "graph"},
    {"name": "has_cycle_directed", "code": '''
def has_cycle_directed(graph, num_nodes):
    if graph is None or num_nodes is None:
        return None
    visited = set()
    rec_stack = set()

    def dfs(node):
        visited.add(node)
        rec_stack.add(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in rec_stack:
                return True
        rec_stack.discard(node)
        return False

    for node in range(num_nodes):
        if node not in visited:
            if dfs(node):
                return True
    return False
''', "category": "graph"},
    {"name": "connected_components", "code": '''
def connected_components(graph, num_nodes):
    if graph is None or num_nodes is None:
        return None
    visited = set()
    count = 0

    def dfs(node):
        visited.add(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor)

    for node in range(num_nodes):
        if node not in visited:
            dfs(node)
            count += 1
    return count
''', "category": "graph"},

    # --- Misc utility ---
    {"name": "flatten_nested_dict", "code": '''
def flatten_nested_dict(d, prefix):
    if d is None:
        return None
    result = {}
    for key, value in d.items():
        full_key = prefix + key if prefix else key
        if isinstance(value, dict):
            nested = flatten_nested_dict(value, full_key + '.')
            result.update(nested)
        else:
            result[full_key] = value
    return result
''', "category": "data_structure"},
    {"name": "deep_copy_list", "code": '''
def deep_copy_list(lst):
    if lst is None:
        return None
    result = []
    for item in lst:
        if isinstance(item, list):
            result.append(deep_copy_list(item))
        else:
            result.append(item)
    return result
''', "category": "data_structure"},
    {"name": "memoize_fibonacci", "code": '''
def memoize_fibonacci(n, memo):
    if n is None or n < 0:
        return None
    if n <= 1:
        return n
    if n in memo:
        return memo[n]
    memo[n] = memoize_fibonacci(n - 1, memo) + memoize_fibonacci(n - 2, memo)
    return memo[n]
''', "category": "dp"},
    {"name": "range_sum_query", "code": '''
def range_sum_query(prefix, left, right):
    if prefix is None or left is None or right is None:
        return None
    if left < 0 or right >= len(prefix):
        return None
    if left == 0:
        return prefix[right]
    return prefix[right] - prefix[left - 1]
''', "category": "array"},
    {"name": "valid_ip", "code": '''
def valid_ip(s):
    if s is None or len(s) == 0:
        return False
    parts = s.split('.')
    if len(parts) != 4:
        return False
    for part in parts:
        if len(part) == 0 or len(part) > 3:
            return False
        if not part.isdigit():
            return False
        num = int(part)
        if num < 0 or num > 255:
            return False
        if len(part) > 1 and part[0] == '0':
            return False
    return True
''', "category": "string"},
    {"name": "roman_to_int", "code": '''
def roman_to_int(s):
    if s is None or len(s) == 0:
        return 0
    values = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    result = 0
    for i in range(len(s)):
        if i + 1 < len(s) and values.get(s[i], 0) < values.get(s[i + 1], 0):
            result -= values.get(s[i], 0)
        else:
            result += values.get(s[i], 0)
    return result
''', "category": "string"},
]
