class SIPDiagnosticTools:
    @staticmethod
    def sip_capture(device_ip: str) -> str:
        return "REGISTER sip:example.com SIP/2.0 -> 403 Forbidden"

    @staticmethod
    def search_logs(device_ip: str, keyword: str) -> str:
        return f"日志查询结果：{keyword} 出现 3 次，最新一条：auth failure for user 1001"

    @staticmethod
    def check_config(device_ip: str, config_path: str) -> str:
        return f"配置项 {config_path}：密码已设置，ACL 允许 192.168.1.0/24，未包含 10.0.0.0/24"

    @staticmethod
    def query_device_status(device_ip: str) -> str:
        return "CPU 15%, 内存 48%, 活跃注册数 230"
