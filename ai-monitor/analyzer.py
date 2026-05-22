import os
import json

SEVERITY_BY_METRIC = {
    "up":     "critical",
    "disk":   "high",
    "memory": "high",
    "swap":   "high",
    "cpu":    "medium",
}

ACTIONS_BY_METRIC = {
    "up":     "서버 상태 및 네트워크 연결을 즉시 확인하세요.",
    "cpu":    "top 명령으로 CPU 점유 프로세스를 확인하세요.",
    "memory": "메모리 점유 프로세스 확인 후 필요 시 재시작하세요.",
    "disk":   "불필요한 로그 및 파일을 정리하세요. (find /var/log -name '*.gz' -mtime +7 -delete)",
    "swap":   "swapoff -a && swapon -a 로 스왑을 초기화합니다. (자동조치 실행)",
}


def analyze(node, metric, value, threshold, history):
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        return _analyze_with_claude(node, metric, value, threshold, history, api_key)
    return _analyze_simple(node, metric, value, threshold, history)


def _analyze_simple(node, metric, value, threshold, history):
    severity = SEVERITY_BY_METRIC.get(metric, "high")
    # 과거 이력에서 단기 자동회복 패턴이면 severity 낮춤
    quick_recoveries = sum(
        1 for h in history
        if h.get("duration_min") and h["duration_min"] < 5 and h["status"] == "resolved"
    )
    if quick_recoveries >= 3 and metric != "disk":
        severity = "low"

    return {
        "is_real_incident": True,
        "severity": severity,
        "analysis": f"{node} 의 {metric} 가 {value:.1f}% 로 임계값({threshold}%)을 초과했습니다. 과거 유사 이력 {len(history)}건 존재.",
        "recommended_action": ACTIONS_BY_METRIC.get(metric, "담당자 직접 확인 필요"),
        "notify": True,
        "auto_remediate": False,
        "remediate_command": None,
    }


def _analyze_with_claude(node, metric, value, threshold, history, api_key):
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    history_text = _format_history(history)

    system_prompt = """당신은 서버 인프라 장애 분석 전문가입니다.
Prometheus 메트릭과 과거 장애 이력을 바탕으로 현재 상황을 분석하고,
실제 장애 여부와 대응 방안을 JSON으로 답해야 합니다.

응답 형식 (반드시 이 JSON만 출력):
{
  "is_real_incident": true/false,
  "severity": "low|medium|high|critical",
  "analysis": "분석 내용 (한국어, 2-3문장)",
  "recommended_action": "권장 조치 (구체적으로)",
  "notify": true/false,
  "auto_remediate": false,
  "remediate_command": null
}

판단 기준:
- 과거 같은 시간대에 반복된 패턴이면 is_real_incident=false 고려
- 지속 시간이 짧고 자동 회복된 이력 있으면 severity 낮게
- disk 90% 이상이면 항상 notify=true
- node down은 항상 critical, notify=true"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": (
            f"노드: {node}\n메트릭: {metric}\n현재값: {value:.1f}% (임계값: {threshold}%)\n"
            f"과거 이력 (최근 10건):\n{history_text}\n\n이 상황을 분석해주세요."
        )}],
    )

    text = response.content[0].text.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def _format_history(history):
    if not history:
        return "  (이력 없음 - 첫 발생)"
    lines = []
    for h in history:
        resolved = h["status"] == "resolved"
        duration = f"{h['duration_min']}분 후 해소" if h.get("duration_min") else ("미해소" if not resolved else "해소")
        lines.append(
            f"  - {h['detected_at'][:16]}  값={h['value']:.1f}%  {duration}"
            + (f"  분석={h['claude_analysis'][:40]}..." if h.get("claude_analysis") else "")
        )
    return "\n".join(lines)
