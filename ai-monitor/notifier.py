import requests
from datetime import datetime

SEVERITY_COLOR = {
    "low":      "Good",
    "medium":   "Warning",
    "high":     "Attention",
    "critical": "Attention",
}

METRIC_LABEL = {
    "cpu":    "CPU 사용률",
    "memory": "메모리 사용률",
    "disk":   "디스크 사용률",
    "swap":   "SWAP 사용률",
    "up":     "노드 상태",
}


def send_alert(webhook_url, owner, node, metric, value, threshold, analysis_result):
    if not webhook_url:
        print(f"[WARN] {node} Teams webhook URL 미설정 - 콘솔 출력만 함")
        _print_alert(owner, node, metric, value, analysis_result)
        return

    severity = analysis_result.get("severity", "high")
    card = _build_alert_card(owner, node, metric, value, threshold, analysis_result, severity)
    _post(webhook_url, card)


def send_resolved(webhook_url, owner, node, metric, duration_min):
    if not webhook_url:
        print(f"[INFO] [{node}] {METRIC_LABEL.get(metric, metric)} 정상화 - 담당자: {owner} ({duration_min}분 소요)")
        return

    card = _build_resolved_card(owner, node, metric, duration_min)
    _post(webhook_url, card)


def _post(webhook_url, card):
    resp = requests.post(webhook_url, json=card, timeout=10)
    resp.raise_for_status()


def _build_alert_card(owner, node, metric, value, threshold, result, severity):
    color = SEVERITY_COLOR.get(severity, "Attention")
    metric_label = METRIC_LABEL.get(metric, metric)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": f"[{severity.upper()}] 서버 장애 감지",
                            "weight": "Bolder",
                            "size": "Large",
                            "color": color,
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "담당자", "value": owner},
                                {"title": "노드", "value": node},
                                {"title": "메트릭", "value": metric_label},
                                {"title": "현재값", "value": f"{value:.1f}% (임계값: {threshold}%)"},
                                {"title": "감지시각", "value": now},
                            ],
                        },
                        {
                            "type": "TextBlock",
                            "text": f"**분석:** {result.get('analysis', '')}",
                            "wrap": True,
                        },
                        {
                            "type": "TextBlock",
                            "text": f"**권장 조치:** {result.get('recommended_action', '')}",
                            "wrap": True,
                            "color": "Warning",
                        },
                    ],
                },
            }
        ],
    }


def _build_resolved_card(owner, node, metric, duration_min):
    metric_label = METRIC_LABEL.get(metric, metric)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": "[RESOLVED] 장애 해소",
                            "weight": "Bolder",
                            "size": "Large",
                            "color": "Good",
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "담당자", "value": owner},
                                {"title": "노드", "value": node},
                                {"title": "메트릭", "value": metric_label},
                                {"title": "소요시간", "value": f"{duration_min}분"},
                                {"title": "해소시각", "value": now},
                            ],
                        },
                    ],
                },
            }
        ],
    }


def _print_alert(owner, node, metric, value, result):
    print(
        f"[ALERT] 담당자={owner} 노드={node} 메트릭={metric} "
        f"값={value:.1f}% severity={result.get('severity')} "
        f"분석={result.get('analysis')}"
    )
