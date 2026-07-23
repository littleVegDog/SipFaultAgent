from typing import *


# Definition for singly-linked list.
class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next


# Definition for singly-linked list.
# class ListNode:
#     def __init__(self, val=0, next=None):
#         self.val = val
#         self.next = next
class Solution:
    def __init__(self):
        self.head = None

    def calculateGreaterElement(self,nums):
        n = len(nums)
        # 存放答案的数组
        res = [0] * n
        s = []
        # 倒着往栈里放
        for i in range(n - 1, -1, -1):
            # 判定个子高矮
            while s and s[-1] <= nums[i]:
                # 矮个起开，反正也被挡着了。。。
                s.pop()
            # nums[i] 身后的更大元素
            res[i] = -1 if not s else s[-1]
            s.append(nums[i])
        return res


if __name__ == "__main__":
    Solution = Solution()
    nums = [2,1,2,4,3]
    res = Solution.calculateGreaterElement(nums)
    print(res)
