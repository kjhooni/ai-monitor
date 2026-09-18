#!/bin/bash
# node_exporter를 배포판 패키지 매니저로 설치하는 스크립트 (Docker 미사용)
# - 모니터링 대상 서버(rocky/ubuntu)에서 root 권한으로 실행
# - apt/dnf 패키지가 전용 계정 생성과 systemd 유닛 등록을 알아서 처리함
#
# 사용법:
#   sudo ./install_node_exporter.sh

set -euo pipefail

. /etc/os-release

case "$ID" in
    ubuntu|debian)
        SERVICE_NAME="prometheus-node-exporter"
        apt-get update
        apt-get install -y prometheus-node-exporter
        ;;
    rocky|almalinux|rhel|centos)
        SERVICE_NAME="golang-github-prometheus-node-exporter"
        dnf install -y epel-release
        dnf install -y golang-github-prometheus-node-exporter
        ;;
    *)
        echo "지원하지 않는 OS입니다: $ID (rocky/ubuntu만 지원)" >&2
        exit 1
        ;;
esac

systemctl enable --now "$SERVICE_NAME"

echo "완료. 상태 확인: systemctl status $SERVICE_NAME"
