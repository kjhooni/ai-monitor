import requests


class PrometheusClient:
    def __init__(self, url):
        self.url = url.rstrip("/")

    def query(self, promql):
        resp = requests.get(f"{self.url}/api/v1/query", params={"query": promql}, timeout=10)
        resp.raise_for_status()
        return resp.json()["data"]["result"]

    def get_instance_to_hostname(self):
        """instance(IP:port) → nodename 매핑 반환"""
        results = self.query("node_uname_info")
        return {r["metric"]["instance"]: r["metric"]["nodename"] for r in results}

    def get_node_up(self):
        results = self.query('up{job="node-exporter"}')
        return {r["metric"]["instance"]: float(r["value"][1]) for r in results}

    def get_cpu_percent(self):
        promql = (
            '100 - (avg by(instance)'
            '(irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'
        )
        results = self.query(promql)
        return {r["metric"]["instance"]: float(r["value"][1]) for r in results}

    def get_memory_percent(self):
        promql = (
            "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100"
        )
        results = self.query(promql)
        return {r["metric"]["instance"]: float(r["value"][1]) for r in results}

    def get_disk_percent(self):
        promql = (
            '(1 - (node_filesystem_avail_bytes{fstype!="tmpfs",mountpoint="/"}'
            ' / node_filesystem_size_bytes{fstype!="tmpfs",mountpoint="/"})) * 100'
        )
        results = self.query(promql)
        return {r["metric"]["instance"]: float(r["value"][1]) for r in results}

    def get_swap_percent(self):
        # SwapTotal이 0인 노드는 결과에 포함되지 않음
        promql = (
            "(1 - (node_memory_SwapFree_bytes / node_memory_SwapTotal_bytes)) * 100"
        )
        results = self.query(promql)
        return {r["metric"]["instance"]: float(r["value"][1]) for r in results}

    def collect_all(self):
        """모든 메트릭을 {instance: {metric: value}} 형태로 반환"""
        hostname_map = self.get_instance_to_hostname()
        node_up     = self.get_node_up()
        cpu         = self.get_cpu_percent()
        memory      = self.get_memory_percent()
        disk        = self.get_disk_percent()
        swap        = self.get_swap_percent()

        data = {}
        for instance in node_up:
            hostname = hostname_map.get(instance, instance)
            data[hostname] = {
                "instance": instance,
                "up":       node_up.get(instance, 0),
                "cpu":      cpu.get(instance),
                "memory":   memory.get(instance),
                "disk":     disk.get(instance),
                "swap":     swap.get(instance),
            }
        return data
