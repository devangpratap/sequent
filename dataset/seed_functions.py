"""
Seed functions for synthetic dataset generation.
These are correct Python functions that the mutation engine will inject bugs into.
Covers: array operations, math, string processing, search/sort, data structures.
"""

SEED_FUNCTIONS = [
    # --- Array / List Operations ---
    {
        "name": "binary_search",
        "code": '''
def binary_search(arr, target):
    low = 0
    high = len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1
''',
        "category": "search"
    },
    {
        "name": "find_max",
        "code": '''
def find_max(arr):
    if arr is None or len(arr) == 0:
        return None
    max_val = arr[0]
    for i in range(1, len(arr)):
        if arr[i] > max_val:
            max_val = arr[i]
    return max_val
''',
        "category": "array"
    },
    {
        "name": "bubble_sort",
        "code": '''
def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr
''',
        "category": "sort"
    },
    {
        "name": "two_sum",
        "code": '''
def two_sum(nums, target):
    seen = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []
''',
        "category": "array"
    },
    {
        "name": "merge_sorted_arrays",
        "code": '''
def merge_sorted_arrays(arr1, arr2):
    result = []
    i = 0
    j = 0
    while i < len(arr1) and j < len(arr2):
        if arr1[i] <= arr2[j]:
            result.append(arr1[i])
            i += 1
        else:
            result.append(arr2[j])
            j += 1
    result.extend(arr1[i:])
    result.extend(arr2[j:])
    return result
''',
        "category": "array"
    },
    {
        "name": "remove_duplicates",
        "code": '''
def remove_duplicates(arr):
    if arr is None or len(arr) == 0:
        return arr
    seen = set()
    result = []
    for item in arr:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
''',
        "category": "array"
    },
    {
        "name": "rotate_array",
        "code": '''
def rotate_array(arr, k):
    if arr is None or len(arr) == 0:
        return arr
    n = len(arr)
    k = k % n
    return arr[n - k:] + arr[:n - k]
''',
        "category": "array"
    },
    {
        "name": "sliding_window_max",
        "code": '''
def sliding_window_max(arr, k):
    if arr is None or len(arr) == 0 or k <= 0:
        return []
    if k >= len(arr):
        return [max(arr)]
    result = []
    for i in range(len(arr) - k + 1):
        window = arr[i:i + k]
        result.append(max(window))
    return result
''',
        "category": "array"
    },

    # --- Math Operations ---
    {
        "name": "factorial",
        "code": '''
def factorial(n):
    if n is None or n < 0:
        return None
    if n == 0 or n == 1:
        return 1
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result
''',
        "category": "math"
    },
    {
        "name": "fibonacci",
        "code": '''
def fibonacci(n):
    if n is None or n < 0:
        return None
    if n == 0:
        return 0
    if n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
''',
        "category": "math"
    },
    {
        "name": "gcd",
        "code": '''
def gcd(a, b):
    if a is None or b is None:
        return None
    a = abs(a)
    b = abs(b)
    while b != 0:
        a, b = b, a % b
    return a
''',
        "category": "math"
    },
    {
        "name": "is_prime",
        "code": '''
def is_prime(n):
    if n is None or n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True
''',
        "category": "math"
    },
    {
        "name": "power",
        "code": '''
def power(base, exp):
    if exp is None or base is None:
        return None
    if exp < 0:
        return 1.0 / power(base, -exp)
    if exp == 0:
        return 1
    if exp % 2 == 0:
        half = power(base, exp // 2)
        return half * half
    else:
        return base * power(base, exp - 1)
''',
        "category": "math"
    },
    {
        "name": "safe_divide",
        "code": '''
def safe_divide(a, b):
    if a is None or b is None:
        return None
    if b == 0:
        return None
    return a / b
''',
        "category": "math"
    },
    {
        "name": "clamp",
        "code": '''
def clamp(value, min_val, max_val):
    if value is None or min_val is None or max_val is None:
        return None
    if value < min_val:
        return min_val
    if value > max_val:
        return max_val
    return value
''',
        "category": "math"
    },
    {
        "name": "sum_range",
        "code": '''
def sum_range(start, end):
    if start is None or end is None:
        return None
    if start > end:
        return 0
    total = 0
    for i in range(start, end + 1):
        total += i
    return total
''',
        "category": "math"
    },

    # --- String Operations ---
    {
        "name": "is_palindrome",
        "code": '''
def is_palindrome(s):
    if s is None:
        return False
    s = s.lower()
    left = 0
    right = len(s) - 1
    while left < right:
        if s[left] != s[right]:
            return False
        left += 1
        right -= 1
    return True
''',
        "category": "string"
    },
    {
        "name": "count_vowels",
        "code": '''
def count_vowels(s):
    if s is None:
        return 0
    count = 0
    for char in s:
        if char.lower() in 'aeiou':
            count += 1
    return count
''',
        "category": "string"
    },
    {
        "name": "reverse_words",
        "code": '''
def reverse_words(s):
    if s is None:
        return None
    words = s.split()
    return ' '.join(reversed(words))
''',
        "category": "string"
    },
    {
        "name": "longest_common_prefix",
        "code": '''
def longest_common_prefix(strs):
    if strs is None or len(strs) == 0:
        return ""
    prefix = strs[0]
    for s in strs[1:]:
        while not s.startswith(prefix):
            prefix = prefix[:-1]
            if len(prefix) == 0:
                return ""
    return prefix
''',
        "category": "string"
    },

    # --- Data Structure Operations ---
    {
        "name": "flatten_list",
        "code": '''
def flatten_list(nested):
    if nested is None:
        return None
    result = []
    for item in nested:
        if isinstance(item, list):
            result.extend(flatten_list(item))
        else:
            result.append(item)
    return result
''',
        "category": "data_structure"
    },
    {
        "name": "matrix_transpose",
        "code": '''
def matrix_transpose(matrix):
    if matrix is None or len(matrix) == 0:
        return matrix
    rows = len(matrix)
    cols = len(matrix[0])
    result = []
    for j in range(cols):
        row = []
        for i in range(rows):
            row.append(matrix[i][j])
        result.append(row)
    return result
''',
        "category": "data_structure"
    },
    {
        "name": "invert_dict",
        "code": '''
def invert_dict(d):
    if d is None:
        return None
    result = {}
    for key, value in d.items():
        if value not in result:
            result[value] = key
    return result
''',
        "category": "data_structure"
    },
    {
        "name": "chunk_list",
        "code": '''
def chunk_list(lst, size):
    if lst is None or size is None or size <= 0:
        return None
    result = []
    for i in range(0, len(lst), size):
        result.append(lst[i:i + size])
    return result
''',
        "category": "data_structure"
    },

    # --- Graph/Tree style ---
    {
        "name": "count_islands",
        "code": '''
def count_islands(grid):
    if grid is None or len(grid) == 0:
        return 0
    rows = len(grid)
    cols = len(grid[0])
    visited = set()
    count = 0

    def dfs(r, c):
        if r < 0 or r >= rows or c < 0 or c >= cols:
            return
        if (r, c) in visited or grid[r][c] == 0:
            return
        visited.add((r, c))
        dfs(r + 1, c)
        dfs(r - 1, c)
        dfs(r, c + 1)
        dfs(r, c - 1)

    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 1 and (r, c) not in visited:
                dfs(r, c)
                count += 1
    return count
''',
        "category": "graph"
    },
    {
        "name": "valid_parentheses",
        "code": '''
def valid_parentheses(s):
    if s is None:
        return False
    stack = []
    mapping = {')': '(', '}': '{', ']': '['}
    for char in s:
        if char in mapping:
            if len(stack) == 0:
                return False
            if stack.pop() != mapping[char]:
                return False
        elif char in '({[':
            stack.append(char)
    return len(stack) == 0
''',
        "category": "data_structure"
    },
    {
        "name": "topological_sort",
        "code": '''
def topological_sort(num_nodes, edges):
    if num_nodes is None or edges is None:
        return None
    adj = {i: [] for i in range(num_nodes)}
    in_degree = {i: 0 for i in range(num_nodes)}
    for u, v in edges:
        adj[u].append(v)
        in_degree[v] += 1
    queue = [n for n in range(num_nodes) if in_degree[n] == 0]
    result = []
    while len(queue) > 0:
        node = queue.pop(0)
        result.append(node)
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    if len(result) != num_nodes:
        return None
    return result
''',
        "category": "graph"
    },

    # --- More numeric ---
    {
        "name": "moving_average",
        "code": '''
def moving_average(arr, window):
    if arr is None or window is None or window <= 0:
        return None
    if window > len(arr):
        return None
    result = []
    window_sum = sum(arr[:window])
    result.append(window_sum / window)
    for i in range(window, len(arr)):
        window_sum += arr[i] - arr[i - window]
        result.append(window_sum / window)
    return result
''',
        "category": "math"
    },
    {
        "name": "kadane_max_subarray",
        "code": '''
def kadane_max_subarray(arr):
    if arr is None or len(arr) == 0:
        return None
    max_sum = arr[0]
    current_sum = arr[0]
    for i in range(1, len(arr)):
        current_sum = max(arr[i], current_sum + arr[i])
        max_sum = max(max_sum, current_sum)
    return max_sum
''',
        "category": "array"
    },

    # --- Batch 2: More diverse functions ---
    {
        "name": "insertion_sort",
        "code": '''
def insertion_sort(arr):
    if arr is None or len(arr) == 0:
        return arr
    for i in range(1, len(arr)):
        key = arr[i]
        j = i - 1
        while j >= 0 and arr[j] > key:
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = key
    return arr
''',
        "category": "sort"
    },
    {
        "name": "selection_sort",
        "code": '''
def selection_sort(arr):
    if arr is None or len(arr) == 0:
        return arr
    n = len(arr)
    for i in range(n):
        min_idx = i
        for j in range(i + 1, n):
            if arr[j] < arr[min_idx]:
                min_idx = j
        arr[i], arr[min_idx] = arr[min_idx], arr[i]
    return arr
''',
        "category": "sort"
    },
    {
        "name": "merge_sort",
        "code": '''
def merge_sort(arr):
    if arr is None:
        return None
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])
    return merge(left, right)

def merge(left, right):
    result = []
    i = 0
    j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result
''',
        "category": "sort"
    },
    {
        "name": "quick_select",
        "code": '''
def quick_select(arr, k):
    if arr is None or k is None or k < 0 or k >= len(arr):
        return None
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    mid = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    if k < len(left):
        return quick_select(left, k)
    elif k < len(left) + len(mid):
        return mid[0]
    else:
        return quick_select(right, k - len(left) - len(mid))
''',
        "category": "sort"
    },
    {
        "name": "matrix_multiply",
        "code": '''
def matrix_multiply(a, b):
    if a is None or b is None:
        return None
    if len(a[0]) != len(b):
        return None
    rows_a = len(a)
    cols_b = len(b[0])
    cols_a = len(a[0])
    result = [[0] * cols_b for _ in range(rows_a)]
    for i in range(rows_a):
        for j in range(cols_b):
            for k in range(cols_a):
                result[i][j] += a[i][k] * b[k][j]
    return result
''',
        "category": "math"
    },
    {
        "name": "nth_fibonacci",
        "code": '''
def nth_fibonacci(n):
    if n is None or n < 0:
        return None
    if n <= 1:
        return n
    dp = [0] * (n + 1)
    dp[1] = 1
    for i in range(2, n + 1):
        dp[i] = dp[i - 1] + dp[i - 2]
    return dp[n]
''',
        "category": "math"
    },
    {
        "name": "lcm",
        "code": '''
def lcm(a, b):
    if a is None or b is None:
        return None
    if a == 0 or b == 0:
        return 0
    a_abs = abs(a)
    b_abs = abs(b)
    g = a_abs
    temp = b_abs
    while temp != 0:
        g, temp = temp, g % temp
    return a_abs * b_abs // g
''',
        "category": "math"
    },
    {
        "name": "sieve_of_eratosthenes",
        "code": '''
def sieve_of_eratosthenes(n):
    if n is None or n < 2:
        return []
    is_prime = [True] * (n + 1)
    is_prime[0] = False
    is_prime[1] = False
    i = 2
    while i * i <= n:
        if is_prime[i]:
            for j in range(i * i, n + 1, i):
                is_prime[j] = False
        i += 1
    return [i for i in range(n + 1) if is_prime[i]]
''',
        "category": "math"
    },
    {
        "name": "coin_change",
        "code": '''
def coin_change(coins, amount):
    if coins is None or amount is None or amount < 0:
        return -1
    dp = [amount + 1] * (amount + 1)
    dp[0] = 0
    for i in range(1, amount + 1):
        for coin in coins:
            if coin <= i:
                dp[i] = min(dp[i], dp[i - coin] + 1)
    if dp[amount] > amount:
        return -1
    return dp[amount]
''',
        "category": "dp"
    },
    {
        "name": "longest_increasing_subsequence",
        "code": '''
def longest_increasing_subsequence(arr):
    if arr is None or len(arr) == 0:
        return 0
    n = len(arr)
    dp = [1] * n
    for i in range(1, n):
        for j in range(i):
            if arr[j] < arr[i]:
                dp[i] = max(dp[i], dp[j] + 1)
    return max(dp)
''',
        "category": "dp"
    },
    {
        "name": "knapsack_01",
        "code": '''
def knapsack_01(weights, values, capacity):
    if weights is None or values is None or capacity is None:
        return None
    n = len(weights)
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for w in range(capacity + 1):
            dp[i][w] = dp[i - 1][w]
            if weights[i - 1] <= w:
                dp[i][w] = max(dp[i][w], dp[i - 1][w - weights[i - 1]] + values[i - 1])
    return dp[n][capacity]
''',
        "category": "dp"
    },
    {
        "name": "edit_distance",
        "code": '''
def edit_distance(s1, s2):
    if s1 is None or s2 is None:
        return None
    m = len(s1)
    n = len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    return dp[m][n]
''',
        "category": "dp"
    },
    {
        "name": "max_profit_stock",
        "code": '''
def max_profit_stock(prices):
    if prices is None or len(prices) < 2:
        return 0
    min_price = prices[0]
    max_profit = 0
    for i in range(1, len(prices)):
        if prices[i] < min_price:
            min_price = prices[i]
        else:
            profit = prices[i] - min_price
            if profit > max_profit:
                max_profit = profit
    return max_profit
''',
        "category": "array"
    },
    {
        "name": "spiral_matrix",
        "code": '''
def spiral_matrix(matrix):
    if matrix is None or len(matrix) == 0:
        return []
    result = []
    top = 0
    bottom = len(matrix) - 1
    left = 0
    right = len(matrix[0]) - 1
    while top <= bottom and left <= right:
        for i in range(left, right + 1):
            result.append(matrix[top][i])
        top += 1
        for i in range(top, bottom + 1):
            result.append(matrix[i][right])
        right -= 1
        if top <= bottom:
            for i in range(right, left - 1, -1):
                result.append(matrix[bottom][i])
            bottom -= 1
        if left <= right:
            for i in range(bottom, top - 1, -1):
                result.append(matrix[i][left])
            left += 1
    return result
''',
        "category": "array"
    },
    {
        "name": "trap_rain_water",
        "code": '''
def trap_rain_water(height):
    if height is None or len(height) < 3:
        return 0
    n = len(height)
    left_max = [0] * n
    right_max = [0] * n
    left_max[0] = height[0]
    for i in range(1, n):
        left_max[i] = max(left_max[i - 1], height[i])
    right_max[n - 1] = height[n - 1]
    for i in range(n - 2, -1, -1):
        right_max[i] = max(right_max[i + 1], height[i])
    water = 0
    for i in range(n):
        water += min(left_max[i], right_max[i]) - height[i]
    return water
''',
        "category": "array"
    },
    {
        "name": "three_sum",
        "code": '''
def three_sum(nums):
    if nums is None or len(nums) < 3:
        return []
    nums.sort()
    result = []
    for i in range(len(nums) - 2):
        if i > 0 and nums[i] == nums[i - 1]:
            continue
        left = i + 1
        right = len(nums) - 1
        while left < right:
            total = nums[i] + nums[left] + nums[right]
            if total == 0:
                result.append([nums[i], nums[left], nums[right]])
                while left < right and nums[left] == nums[left + 1]:
                    left += 1
                while left < right and nums[right] == nums[right - 1]:
                    right -= 1
                left += 1
                right -= 1
            elif total < 0:
                left += 1
            else:
                right -= 1
    return result
''',
        "category": "array"
    },
    {
        "name": "lru_get",
        "code": '''
def lru_get(cache, key, order):
    if cache is None or key is None:
        return None
    if key not in cache:
        return -1
    order.remove(key)
    order.append(key)
    return cache[key]
''',
        "category": "data_structure"
    },
    {
        "name": "min_stack_push",
        "code": '''
def min_stack_push(stack, min_stack, val):
    if stack is None or min_stack is None or val is None:
        return None
    stack.append(val)
    if len(min_stack) == 0 or val <= min_stack[-1]:
        min_stack.append(val)
    return stack
''',
        "category": "data_structure"
    },
    {
        "name": "dijkstra",
        "code": '''
def dijkstra(graph, start):
    if graph is None or start is None:
        return None
    dist = {node: float('inf') for node in graph}
    dist[start] = 0
    visited = set()
    while len(visited) < len(graph):
        current = None
        for node in graph:
            if node not in visited:
                if current is None or dist[node] < dist[current]:
                    current = node
        if current is None or dist[current] == float('inf'):
            break
        visited.add(current)
        for neighbor, weight in graph[current]:
            if neighbor not in visited:
                new_dist = dist[current] + weight
                if new_dist < dist[neighbor]:
                    dist[neighbor] = new_dist
    return dist
''',
        "category": "graph"
    },
    {
        "name": "detect_cycle",
        "code": '''
def detect_cycle(head):
    if head is None:
        return False
    slow = head
    fast = head
    while fast is not None and fast.next is not None:
        slow = slow.next
        fast = fast.next.next
        if slow == fast:
            return True
    return False
''',
        "category": "linked_list"
    },
    {
        "name": "reverse_linked_list",
        "code": '''
def reverse_linked_list(head):
    if head is None:
        return None
    prev = None
    current = head
    while current is not None:
        next_node = current.next
        current.next = prev
        prev = current
        current = next_node
    return prev
''',
        "category": "linked_list"
    },
    {
        "name": "level_order_traversal",
        "code": '''
def level_order_traversal(root):
    if root is None:
        return []
    result = []
    queue = [root]
    while len(queue) > 0:
        level = []
        size = len(queue)
        for _ in range(size):
            node = queue.pop(0)
            level.append(node.val)
            if node.left is not None:
                queue.append(node.left)
            if node.right is not None:
                queue.append(node.right)
        result.append(level)
    return result
''',
        "category": "tree"
    },
    {
        "name": "max_depth_tree",
        "code": '''
def max_depth_tree(root):
    if root is None:
        return 0
    left_depth = max_depth_tree(root.left)
    right_depth = max_depth_tree(root.right)
    return max(left_depth, right_depth) + 1
''',
        "category": "tree"
    },
    {
        "name": "is_valid_bst",
        "code": '''
def is_valid_bst(node, min_val, max_val):
    if node is None:
        return True
    if node.val <= min_val or node.val >= max_val:
        return False
    return is_valid_bst(node.left, min_val, node.val) and is_valid_bst(node.right, node.val, max_val)
''',
        "category": "tree"
    },
    {
        "name": "count_bits",
        "code": '''
def count_bits(n):
    if n is None or n < 0:
        return None
    count = 0
    while n > 0:
        count += n & 1
        n = n >> 1
    return count
''',
        "category": "bit"
    },
    {
        "name": "hamming_distance",
        "code": '''
def hamming_distance(x, y):
    if x is None or y is None:
        return None
    xor = x ^ y
    count = 0
    while xor > 0:
        count += xor & 1
        xor = xor >> 1
    return count
''',
        "category": "bit"
    },
    {
        "name": "prefix_sum",
        "code": '''
def prefix_sum(arr):
    if arr is None or len(arr) == 0:
        return arr
    result = [0] * len(arr)
    result[0] = arr[0]
    for i in range(1, len(arr)):
        result[i] = result[i - 1] + arr[i]
    return result
''',
        "category": "array"
    },
    {
        "name": "product_except_self",
        "code": '''
def product_except_self(nums):
    if nums is None or len(nums) == 0:
        return nums
    n = len(nums)
    result = [1] * n
    left = 1
    for i in range(n):
        result[i] = left
        left *= nums[i]
    right = 1
    for i in range(n - 1, -1, -1):
        result[i] *= right
        right *= nums[i]
    return result
''',
        "category": "array"
    },
    {
        "name": "group_anagrams",
        "code": '''
def group_anagrams(strs):
    if strs is None:
        return None
    groups = {}
    for s in strs:
        key = ''.join(sorted(s))
        if key not in groups:
            groups[key] = []
        groups[key].append(s)
    return list(groups.values())
''',
        "category": "string"
    },
    {
        "name": "longest_substring_no_repeat",
        "code": '''
def longest_substring_no_repeat(s):
    if s is None:
        return 0
    seen = {}
    start = 0
    max_len = 0
    for i, char in enumerate(s):
        if char in seen and seen[char] >= start:
            start = seen[char] + 1
        seen[char] = i
        max_len = max(max_len, i - start + 1)
    return max_len
''',
        "category": "string"
    },

    # --- Batch 3: More diverse functions for better generalization ---
    {
        "name": "dutch_national_flag",
        "code": '''
def dutch_national_flag(arr):
    if arr is None or len(arr) == 0:
        return arr
    low = 0
    mid = 0
    high = len(arr) - 1
    while mid <= high:
        if arr[mid] == 0:
            arr[low], arr[mid] = arr[mid], arr[low]
            low += 1
            mid += 1
        elif arr[mid] == 1:
            mid += 1
        else:
            arr[mid], arr[high] = arr[high], arr[mid]
            high -= 1
    return arr
''',
        "category": "array"
    },
    {
        "name": "next_permutation",
        "code": '''
def next_permutation(nums):
    if nums is None or len(nums) <= 1:
        return nums
    n = len(nums)
    i = n - 2
    while i >= 0 and nums[i] >= nums[i + 1]:
        i -= 1
    if i >= 0:
        j = n - 1
        while j > i and nums[j] <= nums[i]:
            j -= 1
        nums[i], nums[j] = nums[j], nums[i]
    left = i + 1
    right = n - 1
    while left < right:
        nums[left], nums[right] = nums[right], nums[left]
        left += 1
        right -= 1
    return nums
''',
        "category": "array"
    },
    {
        "name": "max_area_container",
        "code": '''
def max_area_container(height):
    if height is None or len(height) < 2:
        return 0
    left = 0
    right = len(height) - 1
    max_area = 0
    while left < right:
        width = right - left
        h = min(height[left], height[right])
        area = width * h
        if area > max_area:
            max_area = area
        if height[left] < height[right]:
            left += 1
        else:
            right -= 1
    return max_area
''',
        "category": "array"
    },
    {
        "name": "search_rotated_array",
        "code": '''
def search_rotated_array(nums, target):
    if nums is None or len(nums) == 0:
        return -1
    left = 0
    right = len(nums) - 1
    while left <= right:
        mid = (left + right) // 2
        if nums[mid] == target:
            return mid
        if nums[left] <= nums[mid]:
            if nums[left] <= target < nums[mid]:
                right = mid - 1
            else:
                left = mid + 1
        else:
            if nums[mid] < target <= nums[right]:
                left = mid + 1
            else:
                right = mid - 1
    return -1
''',
        "category": "search"
    },
    {
        "name": "find_peak_element",
        "code": '''
def find_peak_element(nums):
    if nums is None or len(nums) == 0:
        return -1
    left = 0
    right = len(nums) - 1
    while left < right:
        mid = (left + right) // 2
        if nums[mid] > nums[mid + 1]:
            right = mid
        else:
            left = mid + 1
    return left
''',
        "category": "search"
    },
    {
        "name": "kth_smallest_matrix",
        "code": '''
def kth_smallest_matrix(matrix, k):
    if matrix is None or k is None or k <= 0:
        return None
    n = len(matrix)
    lo = matrix[0][0]
    hi = matrix[n - 1][n - 1]
    while lo < hi:
        mid = (lo + hi) // 2
        count = 0
        j = n - 1
        for i in range(n):
            while j >= 0 and matrix[i][j] > mid:
                j -= 1
            count += j + 1
        if count < k:
            lo = mid + 1
        else:
            hi = mid
    return lo
''',
        "category": "search"
    },
    {
        "name": "interval_merge",
        "code": '''
def interval_merge(intervals):
    if intervals is None or len(intervals) == 0:
        return []
    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0]]
    for i in range(1, len(intervals)):
        if intervals[i][0] <= merged[-1][1]:
            merged[-1] = [merged[-1][0], max(merged[-1][1], intervals[i][1])]
        else:
            merged.append(intervals[i])
    return merged
''',
        "category": "array"
    },
    {
        "name": "subarray_sum_k",
        "code": '''
def subarray_sum_k(nums, k):
    if nums is None:
        return 0
    count = 0
    prefix = 0
    seen = {0: 1}
    for num in nums:
        prefix += num
        if prefix - k in seen:
            count += seen[prefix - k]
        seen[prefix] = seen.get(prefix, 0) + 1
    return count
''',
        "category": "array"
    },
    {
        "name": "min_path_sum",
        "code": '''
def min_path_sum(grid):
    if grid is None or len(grid) == 0:
        return 0
    m = len(grid)
    n = len(grid[0])
    dp = [[0] * n for _ in range(m)]
    dp[0][0] = grid[0][0]
    for i in range(1, m):
        dp[i][0] = dp[i - 1][0] + grid[i][0]
    for j in range(1, n):
        dp[0][j] = dp[0][j - 1] + grid[0][j]
    for i in range(1, m):
        for j in range(1, n):
            dp[i][j] = grid[i][j] + min(dp[i - 1][j], dp[i][j - 1])
    return dp[m - 1][n - 1]
''',
        "category": "dp"
    },
    {
        "name": "unique_paths",
        "code": '''
def unique_paths(m, n):
    if m is None or n is None or m <= 0 or n <= 0:
        return 0
    dp = [[1] * n for _ in range(m)]
    for i in range(1, m):
        for j in range(1, n):
            dp[i][j] = dp[i - 1][j] + dp[i][j - 1]
    return dp[m - 1][n - 1]
''',
        "category": "dp"
    },
    {
        "name": "word_break",
        "code": '''
def word_break(s, word_dict):
    if s is None or word_dict is None:
        return False
    n = len(s)
    dp = [False] * (n + 1)
    dp[0] = True
    for i in range(1, n + 1):
        for j in range(i):
            if dp[j] and s[j:i] in word_dict:
                dp[i] = True
                break
    return dp[n]
''',
        "category": "dp"
    },
    {
        "name": "max_subarray_circular",
        "code": '''
def max_subarray_circular(nums):
    if nums is None or len(nums) == 0:
        return None
    total = 0
    max_sum = nums[0]
    cur_max = 0
    min_sum = nums[0]
    cur_min = 0
    for num in nums:
        cur_max = max(cur_max + num, num)
        max_sum = max(max_sum, cur_max)
        cur_min = min(cur_min + num, num)
        min_sum = min(min_sum, cur_min)
        total += num
    if max_sum < 0:
        return max_sum
    return max(max_sum, total - min_sum)
''',
        "category": "array"
    },
    {
        "name": "rob_houses",
        "code": '''
def rob_houses(nums):
    if nums is None or len(nums) == 0:
        return 0
    if len(nums) == 1:
        return nums[0]
    prev2 = 0
    prev1 = 0
    for num in nums:
        current = max(prev1, prev2 + num)
        prev2 = prev1
        prev1 = current
    return prev1
''',
        "category": "dp"
    },
    {
        "name": "climb_stairs",
        "code": '''
def climb_stairs(n):
    if n is None or n < 0:
        return 0
    if n <= 2:
        return max(n, 0)
    a = 1
    b = 2
    for _ in range(3, n + 1):
        a, b = b, a + b
    return b
''',
        "category": "dp"
    },
    {
        "name": "decode_ways",
        "code": '''
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
''',
        "category": "dp"
    },
    {
        "name": "generate_parentheses",
        "code": '''
def generate_parentheses(n):
    if n is None or n <= 0:
        return []
    result = []
    def backtrack(current, open_count, close_count):
        if len(current) == 2 * n:
            result.append(current)
            return
        if open_count < n:
            backtrack(current + '(', open_count + 1, close_count)
        if close_count < open_count:
            backtrack(current + ')', open_count, close_count + 1)
    backtrack('', 0, 0)
    return result
''',
        "category": "string"
    },
    {
        "name": "letter_combinations",
        "code": '''
def letter_combinations(digits):
    if digits is None or len(digits) == 0:
        return []
    phone = {'2': 'abc', '3': 'def', '4': 'ghi', '5': 'jkl',
             '6': 'mno', '7': 'pqrs', '8': 'tuv', '9': 'wxyz'}
    result = ['']
    for digit in digits:
        if digit not in phone:
            continue
        new_result = []
        for combo in result:
            for letter in phone[digit]:
                new_result.append(combo + letter)
        result = new_result
    return result
''',
        "category": "string"
    },
    {
        "name": "atoi",
        "code": '''
def atoi(s):
    if s is None:
        return 0
    s = s.strip()
    if len(s) == 0:
        return 0
    sign = 1
    i = 0
    if s[0] == '-':
        sign = -1
        i = 1
    elif s[0] == '+':
        i = 1
    result = 0
    while i < len(s) and s[i].isdigit():
        result = result * 10 + int(s[i])
        i += 1
    result = result * sign
    result = max(result, -(2 ** 31))
    result = min(result, 2 ** 31 - 1)
    return result
''',
        "category": "string"
    },
    {
        "name": "count_and_say",
        "code": '''
def count_and_say(n):
    if n is None or n <= 0:
        return ""
    result = "1"
    for _ in range(n - 1):
        new_result = ""
        i = 0
        while i < len(result):
            count = 1
            while i + count < len(result) and result[i + count] == result[i]:
                count += 1
            new_result += str(count) + result[i]
            i += count
        result = new_result
    return result
''',
        "category": "string"
    },
    {
        "name": "permutations",
        "code": '''
def permutations(nums):
    if nums is None:
        return None
    if len(nums) <= 1:
        return [nums[:]]
    result = []
    for i in range(len(nums)):
        rest = nums[:i] + nums[i + 1:]
        for perm in permutations(rest):
            result.append([nums[i]] + perm)
    return result
''',
        "category": "array"
    },
    {
        "name": "combination_sum",
        "code": '''
def combination_sum(candidates, target):
    if candidates is None or target is None or target < 0:
        return []
    result = []
    def backtrack(start, combo, remaining):
        if remaining == 0:
            result.append(combo[:])
            return
        if remaining < 0:
            return
        for i in range(start, len(candidates)):
            combo.append(candidates[i])
            backtrack(i, combo, remaining - candidates[i])
            combo.pop()
    backtrack(0, [], target)
    return result
''',
        "category": "array"
    },
    {
        "name": "set_matrix_zeroes",
        "code": '''
def set_matrix_zeroes(matrix):
    if matrix is None or len(matrix) == 0:
        return matrix
    m = len(matrix)
    n = len(matrix[0])
    zero_rows = set()
    zero_cols = set()
    for i in range(m):
        for j in range(n):
            if matrix[i][j] == 0:
                zero_rows.add(i)
                zero_cols.add(j)
    for i in range(m):
        for j in range(n):
            if i in zero_rows or j in zero_cols:
                matrix[i][j] = 0
    return matrix
''',
        "category": "array"
    },
    {
        "name": "longest_palindrome_substring",
        "code": '''
def longest_palindrome_substring(s):
    if s is None or len(s) == 0:
        return ""
    start = 0
    max_len = 1
    def expand(left, right):
        while left >= 0 and right < len(s) and s[left] == s[right]:
            left -= 1
            right += 1
        return left + 1, right - left - 1
    for i in range(len(s)):
        s1, l1 = expand(i, i)
        s2, l2 = expand(i, i + 1)
        if l1 > max_len:
            start = s1
            max_len = l1
        if l2 > max_len:
            start = s2
            max_len = l2
    return s[start:start + max_len]
''',
        "category": "string"
    },
    {
        "name": "daily_temperatures",
        "code": '''
def daily_temperatures(temps):
    if temps is None or len(temps) == 0:
        return []
    n = len(temps)
    result = [0] * n
    stack = []
    for i in range(n):
        while len(stack) > 0 and temps[i] > temps[stack[-1]]:
            prev = stack.pop()
            result[prev] = i - prev
        stack.append(i)
    return result
''',
        "category": "array"
    },
    {
        "name": "largest_rectangle_histogram",
        "code": '''
def largest_rectangle_histogram(heights):
    if heights is None or len(heights) == 0:
        return 0
    stack = []
    max_area = 0
    for i in range(len(heights)):
        while len(stack) > 0 and heights[i] < heights[stack[-1]]:
            h = heights[stack.pop()]
            w = i if len(stack) == 0 else i - stack[-1] - 1
            max_area = max(max_area, h * w)
        stack.append(i)
    while len(stack) > 0:
        h = heights[stack.pop()]
        w = len(heights) if len(stack) == 0 else len(heights) - stack[-1] - 1
        max_area = max(max_area, h * w)
    return max_area
''',
        "category": "array"
    },
    {
        "name": "trie_insert",
        "code": '''
def trie_insert(root, word):
    if root is None or word is None:
        return root
    node = root
    for char in word:
        if char not in node:
            node[char] = {}
        node = node[char]
    node['#'] = True
    return root
''',
        "category": "data_structure"
    },
    {
        "name": "trie_search",
        "code": '''
def trie_search(root, word):
    if root is None or word is None:
        return False
    node = root
    for char in word:
        if char not in node:
            return False
        node = node[char]
    return '#' in node
''',
        "category": "data_structure"
    },
    {
        "name": "num_islands_bfs",
        "code": '''
def num_islands_bfs(grid):
    if grid is None or len(grid) == 0:
        return 0
    rows = len(grid)
    cols = len(grid[0])
    count = 0
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 1:
                count += 1
                queue = [(r, c)]
                grid[r][c] = 0
                while len(queue) > 0:
                    cr, cc = queue.pop(0)
                    for dr, dc in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                        nr = cr + dr
                        nc = cc + dc
                        if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 1:
                            grid[nr][nc] = 0
                            queue.append((nr, nc))
    return count
''',
        "category": "graph"
    },
    {
        "name": "course_schedule",
        "code": '''
def course_schedule(num_courses, prerequisites):
    if num_courses is None or prerequisites is None:
        return False
    adj = {i: [] for i in range(num_courses)}
    in_deg = {i: 0 for i in range(num_courses)}
    for course, prereq in prerequisites:
        adj[prereq].append(course)
        in_deg[course] += 1
    queue = [c for c in range(num_courses) if in_deg[c] == 0]
    taken = 0
    while len(queue) > 0:
        c = queue.pop(0)
        taken += 1
        for neighbor in adj[c]:
            in_deg[neighbor] -= 1
            if in_deg[neighbor] == 0:
                queue.append(neighbor)
    return taken == num_courses
''',
        "category": "graph"
    },
    {
        "name": "find_median_sorted_arrays",
        "code": '''
def find_median_sorted_arrays(nums1, nums2):
    if nums1 is None:
        nums1 = []
    if nums2 is None:
        nums2 = []
    merged = []
    i = 0
    j = 0
    while i < len(nums1) and j < len(nums2):
        if nums1[i] <= nums2[j]:
            merged.append(nums1[i])
            i += 1
        else:
            merged.append(nums2[j])
            j += 1
    merged.extend(nums1[i:])
    merged.extend(nums2[j:])
    n = len(merged)
    if n == 0:
        return 0
    if n % 2 == 1:
        return merged[n // 2]
    return (merged[n // 2 - 1] + merged[n // 2]) / 2
''',
        "category": "array"
    },
]
