import paramiko

REMEDIATION_SCRIPTS = {
    "disk": "find /var/log -name '*.gz' -mtime +7 -delete && journalctl --vacuum-time=7d",
    "memory": "sync && echo 3 > /proc/sys/vm/drop_caches",
    "swap": "swapoff -a && swapon -a",
}

DIAGNOSTIC_COMMANDS = {
    "cpu":    "ps aux --sort=-%cpu | head -11",
    "memory": "free -m; echo '---'; ps aux --sort=-%mem | head -11",
    "disk":   "df -h; echo '---'; df --output=pcent,target | awk 'NR>1 && int($1)>=80 {print $2}' | while read mp; do echo \"=== $mp ===\"; du -sh $mp/* 2>/dev/null | sort -rh | head -10; done",
}


def collect_diagnostics(node_config, metric):
    command = DIAGNOSTIC_COMMANDS.get(metric)
    if not command:
        return None

    ssh_user = node_config.get("ssh_user")
    ssh_password = node_config.get("ssh_password")
    ip = node_config.get("ip")

    if not ssh_user or not ssh_password or not ip:
        return None

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=ssh_user, password=ssh_password, timeout=10)
        _, stdout, _ = ssh.exec_command(command)
        output = stdout.read().decode().strip()
        ssh.close()
        return output
    except Exception as e:
        print(f"[WARN] 진단 명령 실행 실패 ({ip}): {e}")
        return None


def run(node_config, metric, command=None):
    ssh_user = node_config.get("ssh_user")
    ssh_password = node_config.get("ssh_password")
    ip = node_config.get("ip")

    if not ssh_user or not ssh_password or not ip:
        return None, "SSH 설정 없음 - 자동조치 건너뜀"

    command = command or REMEDIATION_SCRIPTS.get(metric)
    if not command:
        return None, f"{metric} 에 대한 자동조치 스크립트 없음"

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=ssh_user, password=ssh_password, timeout=10)
        _, stdout, stderr = ssh.exec_command(command)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        exit_code = stdout.channel.recv_exit_status()
        ssh.close()
        if exit_code != 0:
            result = f"명령 실행 실패 (exit {exit_code})"
            if err:
                result += f": {err[:200]}"
        else:
            result = "명령 실행 성공"
            if out:
                result += f"\n{out[:500]}"
            if err:
                result += f"\n(stderr: {err[:100]})"
        return command, result
    except Exception as e:
        return command, f"SSH 실행 실패: {e}"
