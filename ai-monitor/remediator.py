import time
import paramiko

#claude가 별도 명령어를 안 줬을때 쓰는 metric별 기본 자동조치 스크립트
REMEDIATION_SCRIPTS = {
    "disk": "find /var/log -name '*.gz' -mtime +7 -delete && journalctl --vacuum-time=7d",
    "memory": "sync && echo 3 > /proc/sys/vm/drop_caches",
    "swap": "swapoff -a && swapon -a",
}

#장애 감지 시 claude에게 원인 분석 자료로 넘길 진단 정보를 수집하는 metric별 읽기 전용 명령어
DIAGNOSTIC_COMMANDS = {
    "cpu":    "ps aux --sort=-%cpu | head -11",
    "memory": "free -m; echo '---'; ps aux --sort=-%mem | head -11",
    "disk":   "df -h; echo '---'; df --output=pcent,target | awk 'NR>1 && int($1)>=80 {print $2}' | while read mp; do echo \"=== $mp ===\"; du -sh $mp/* 2>/dev/null | sort -rh | head -10; echo '--- 최근 수정 파일 (상위 15개, 최신순) ---'; find $mp -type f -printf '%TY-%Tm-%Td %TH:%TM %10s %p\\n' 2>/dev/null | sort -r | head -15; done",
}


def collect_diagnostics(node_config, metric, retries=1, retry_delay=3):
    """진단 명령 실행. 성공 시 (결과, None), 실패 시 (None, 에러메시지) 반환.
    일시적인 SSH 오류(No existing session 등)에 대응하기 위해 retries회 재시도한다."""
    command = DIAGNOSTIC_COMMANDS.get(metric)
    if not command:
        return None, None

    ssh_user = node_config.get("ssh_user")
    ssh_password = node_config.get("ssh_password")
    ip = node_config.get("ip")

    if not ssh_user or not ssh_password or not ip:
        return None, None

    last_error = None
    for attempt in range(retries + 1):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=ssh_user, password=ssh_password, timeout=10)
            _, stdout, _ = ssh.exec_command(command)
            output = stdout.read().decode().strip()
            ssh.close()
            return output, None
        except Exception as e:
            last_error = str(e)
            print(f"[WARN] 진단 명령 실행 실패 ({ip}, {attempt + 1}/{retries + 1}차 시도): {e}")
            if attempt < retries:
                time.sleep(retry_delay)

    return None, last_error


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
