#!/usr/bin/env python3
# 测试Router功能

from router import RouterAgent

def test_router():
    router = RouterAgent()

    test_cases = [
        ("SIP 403是什么意思", "protocol_query"),
        ("为什么注册失败", "fault_diagnosis"),
        ("401错误是什么意思", "protocol_query"),
        ("SBC怎么配置", "fault_diagnosis"),
        ("INVITE请求的含义", "protocol_query"),
        ("系统出现错误怎么办", "fault_diagnosis"),
        ("RFC文档内容", "protocol_query")
    ]

    print("测试Router功能:")
    for query, expected in test_cases:
        result = router.route_query(query)
        status = "PASS" if result == expected else "FAIL"
        print(f"{status}: 查询: '{query}' -> {result} (期望: {expected})")

if __name__ == "__main__":
    test_router()
