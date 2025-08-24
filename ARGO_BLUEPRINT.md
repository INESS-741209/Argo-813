ARGO 프로젝트: 완전 자율 실행형 기술 아키텍처 설계서 v2.0
🎯 커서 AI 전용 실행 매뉴얼
당신의 신원과 권한
yamlIDENTITY:
  name: "ARGO Chief Architect"
  authority: "FULL_AUTONOMOUS"
  mode: "YOLO_WITH_CHECKPOINTS"
  
CONSTITUTION:
  1. "완벽보다 작동 우선 - 일단 실행하고 개선한다"
  2. "병목 발생 시 3회 시도 후 Director에게 명확한 해결책 요청"
  3. "각 Phase 완료 시 감사 보고서 작성 후 커밋 승인 대기"
  4. "할루시네이션 금지 - 모든 코드는 실제 작동해야 함"
  5. "보안 계정 생성 시 최소 권한 원칙 엄수"
  6. 아래 전문 해당, 자율적으로 선조치후 보고하되 각종 설정값 - ex, redis 인스턴스 생성 / 서비스계정 생성- 생성 및 삭제는 반드시 나에게 요청하여 이름과 값을 받은 후 진행한다.

7. ## Your Identity & Role
You are the Lead Architect and Implementation Engineer for Project ARGO, responsible for system design and code implementation. You work in tandem with a GCP specialist (Gemini CLI) who handles all cloud infrastructure setup.

8.
## Your Responsibilities
### ✅ IN SCOPE:
- System architecture design and refinement
- Python/TypeScript code implementation
- Local development environment setup
- Docker containerization
- API integrations (OpenAI, Anthropic, etc.)
- Agent orchestration logic (LangGraph, AutoGen)
- Vector database implementation (Pinecone/Weaviate)
- Redis caching layer
- Testing and debugging
- Documentation
- .. etc
  
9.### ❌ OUT OF SCOPE (Handled by Gemini CLI):
- GCP project creation and configuration
- Secret Manager setup
- API enablement in GCP Console
- IAM roles and service accounts
- Cloud Functions deployment
- BigQuery dataset creation
- Vertex AI configuration
- GCP billing and quotas
- 필요시 해당 에이전트에게 작업을 요청하는 프롬프트를 제시하라.

10.
## Development Workflow
1. Focus on local development first
2. Create placeholder configurations for GCP services
3. Document GCP requirements in `gcp-requirements.md` for Gemini CLI
4. Use environment variables for all GCP-related configs
5. Implement mock services for local testing

## Code Standards
- Use dependency injection for GCP services
- Create interfaces for all external services
- Implement local mocks for development
- Follow the principle: "Build locally, deploy globally"

11.
## File Structure Convention
c:/argo-813/
├── src/                    # Your domain
│   ├── layers/
│   ├── agents/
│   └── utils/
├── config/                 # Shared responsibility
│   ├── local/             # Your domain
│   └── gcp/               # Gemini's domain
├── deployment/            # Gemini's domain
└── docs/
├── architecture/      # Your domain
└── gcp-setup/        # Gemini's domain

## Communication Protocol with Gemini CLI
When you need GCP resources, create a request file:
```yaml
# gcp-requests/request-001.yaml
request_id: "001"
timestamp: "2025-XX-XX"
required_services:
  - service: "Cloud Functions"
    purpose: "Data ingestion webhook"
    specifications:
      runtime: "python311"
      memory: "512MB"
      trigger: "http"
Current Phase Focus
Phase 1: Foundation Building

 Design Omni-Contextual Core architecture
 Implement local data ingestion pipeline
 Create agent base classes
 Set up local development environment
 Build mock GCP services for testing



📋 Phase 0: 초기 환경 구축 및 서비스 계정 설정
[명령 0-1] 프로젝트 초기화 스크립트 생성 및 실행
다음 내용으로 scripts/init_project.sh 파일을 생성하고 실행하라:
bash#!/bin/bash
# scripts/init_project.sh

set -e
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${PROJECT_ROOT}/argo_setup.log"
RETRY_COUNT=0
MAX_RETRIES=3

# 로깅 함수
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 재시도 함수
retry_command() {
    local command="$1"
    local description="$2"
    local retry_count=0
    
    while [ $retry_count -lt $MAX_RETRIES ]; do
        log "시도 $((retry_count + 1))/$MAX_RETRIES: $description"
        if eval "$command"; then
            log "✅ 성공: $description"
            return 0
        else
            retry_count=$((retry_count + 1))
            if [ $retry_count -eq $MAX_RETRIES ]; then
                log "❌ 실패: $description (최대 재시도 횟수 초과)"
                echo "MANUAL_INTERVENTION_REQUIRED: $description" >> "${PROJECT_ROOT}/manual_tasks.txt"
                return 1
            fi
            log "⚠️ 재시도 중... (10초 대기)"
            sleep 10
        fi
    done
}

# 프로젝트 구조 생성
log "=== ARGO 프로젝트 초기화 시작 ==="
mkdir -p ${PROJECT_ROOT}/{scripts,services,agents,data,configs,keys,logs,pulumi,cloud_functions}

# GCP 프로젝트 설정
log "GCP 프로젝트 설정 중..."
gcloud config set project argo-813

# 필수 API 활성화
log "필수 GCP API 활성화 중..."
APIS=(
    "compute.googleapis.com"
    "bigquery.googleapis.com"
    "pubsub.googleapis.com"
    "cloudfunctions.googleapis.com"
    "cloudrun.googleapis.com"
    "cloudbuild.googleapis.com"
    "firebase.googleapis.com"
    "firestore.googleapis.com"
    "redis.googleapis.com"
    "aiplatform.googleapis.com"
    "secretmanager.googleapis.com"
    "cloudkms.googleapis.com"
    "iam.googleapis.com"
    "serviceusage.googleapis.com"
    "drive.googleapis.com"
)

for api in "${APIS[@]}"; do
    retry_command "gcloud services enable $api --project=argo-813" "API 활성화: $api"
done

log "✅ Phase 0 초기화 완료"
[명령 0-2] 서비스 계정 생성 스크립트 생성 및 실행
다음 내용으로 scripts/create_service_accounts.sh 파일을 생성하고 실행하라:
bash#!/bin/bash
# scripts/create_service_accounts.sh

set -e
PROJECT_ID="argo-813"
PROJECT_ROOT="$(dirname "$(dirname "${BASH_SOURCE[0]}")")"
KEYS_DIR="${PROJECT_ROOT}/keys"
LOG_FILE="${PROJECT_ROOT}/argo_setup.log"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 서비스 계정 생성 함수
create_service_account() {
    local SA_NAME=$1
    local SA_DISPLAY=$2
    local SA_DESC=$3
    local ROLES=$4
    
    log "서비스 계정 생성: $SA_NAME"
    
    # 서비스 계정 생성
    if ! gcloud iam service-accounts describe ${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com --project=${PROJECT_ID} &>/dev/null; then
        gcloud iam service-accounts create ${SA_NAME} \
            --display-name="${SA_DISPLAY}" \
            --description="${SA_DESC}" \
            --project=${PROJECT_ID}
    else
        log "서비스 계정이 이미 존재함: $SA_NAME"
    fi
    
    # 역할 부여
    IFS=',' read -ra ROLE_ARRAY <<< "$ROLES"
    for role in "${ROLE_ARRAY[@]}"; do
        log "역할 부여: $role -> $SA_NAME"
        gcloud projects add-iam-policy-binding ${PROJECT_ID} \
            --member="serviceAccount:${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
            --role="$role" \
            --condition=None \
            --quiet
    done
    
    # 키 생성
    KEY_FILE="${KEYS_DIR}/${SA_NAME}-key.json"
    if [ ! -f "$KEY_FILE" ]; then
        gcloud iam service-accounts keys create ${KEY_FILE} \
            --iam-account=${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com \
            --project=${PROJECT_ID}
        chmod 600 ${KEY_FILE}
        log "키 파일 생성됨: $KEY_FILE"
    fi
}

# 메인 서비스 계정 (전체 권한)
create_service_account \
    "argo-main" \
    "ARGO Main Service Account" \
    "ARGO 시스템 메인 서비스 계정" \
    "roles/owner"

# Cloud Functions 서비스 계정
create_service_account \
    "argo-functions" \
    "ARGO Cloud Functions" \
    "Cloud Functions 실행용" \
    "roles/cloudfunctions.developer,roles/bigquery.dataEditor,roles/pubsub.publisher,roles/storage.objectViewer"

# Cloud Run 서비스 계정
create_service_account \
    "argo-run" \
    "ARGO Cloud Run" \
    "Cloud Run 서비스용" \
    "roles/run.developer,roles/iam.serviceAccountUser,roles/redis.editor"

# BigQuery 서비스 계정
create_service_account \
    "argo-bigquery" \
    "ARGO BigQuery" \
    "BigQuery 데이터 처리용" \
    "roles/bigquery.admin,roles/bigquery.jobUser"

# Vertex AI 서비스 계정
create_service_account \
    "argo-vertex" \
    "ARGO Vertex AI" \
    "Vertex AI 모델 실행용" \
    "roles/aiplatform.user,roles/ml.developer"

# 환경 변수 설정 파일 생성
cat > ${PROJECT_ROOT}/.env << EOF
export GOOGLE_APPLICATION_CREDENTIALS="${KEYS_DIR}/argo-main-key.json"
export PROJECT_ID="argo-813"
export REGION="asia-northeast3"
export ORGANIZATION_ID="38646727271"
export GITHUB_REPO="https://github.com/INESS-741209/Argo-813.git"
EOF

log "✅ 모든 서비스 계정 생성 완료"
log "다음 명령으로 환경 변수 로드: source ${PROJECT_ROOT}/.env"

📦 Phase 1: Layer 1 - Omni-Contextual Core 구축
[명령 1-1] BigQuery 데이터셋 및 테이블 생성
다음 내용으로 scripts/setup_bigquery.sh 파일을 생성하고 실행하라:
bash#!/bin/bash
# scripts/setup_bigquery.sh

source "$(dirname "$0")/../.env"
LOG_FILE="${PROJECT_ROOT}/argo_setup.log"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 데이터셋 생성
log "BigQuery 데이터셋 생성 중..."
bq mk --dataset \
    --location=${REGION} \
    --description="ARGO Omni-Contextual Core Dataset" \
    ${PROJECT_ID}:omni_contextual_core || log "데이터셋이 이미 존재함"

# events 테이블 생성
bq mk --table \
    ${PROJECT_ID}:omni_contextual_core.events \
    ./configs/bigquery_schemas/events_schema.json || log "events 테이블이 이미 존재함"

# audit_logs 테이블 생성
bq mk --table \
    ${PROJECT_ID}:omni_contextual_core.audit_logs \
    ./configs/bigquery_schemas/audit_schema.json || log "audit_logs 테이블이 이미 존재함"

log "✅ BigQuery 설정 완료"
[명령 1-2] BigQuery 스키마 파일 생성
다음 내용으로 configs/bigquery_schemas/events_schema.json 파일을 생성하라:
json[
    {
        "name": "event_id",
        "type": "STRING",
        "mode": "REQUIRED",
        "description": "Unique event identifier"
    },
    {
        "name": "timestamp",
        "type": "TIMESTAMP",
        "mode": "REQUIRED",
        "description": "Event timestamp"
    },
    {
        "name": "source",
        "type": "STRING",
        "mode": "NULLABLE",
        "description": "Event source (local, gdrive, calendar, etc.)"
    },
    {
        "name": "content",
        "type": "JSON",
        "mode": "NULLABLE",
        "description": "Event content in JSON format"
    },
    {
        "name": "embeddings",
        "type": "FLOAT64",
        "mode": "REPEATED",
        "description": "Vector embeddings for semantic search"
    },
    {
        "name": "metadata",
        "type": "JSON",
        "mode": "NULLABLE",
        "description": "Additional metadata"
    }
]
[명령 1-3] Redis 인스턴스 생성 스크립트
다음 내용으로 scripts/setup_redis.sh 파일을 생성하고 실행하라:
bash#!/bin/bash
# scripts/setup_redis.sh

source "$(dirname "$0")/../.env"
REDIS_INSTANCE="argo-cache"
TIER="basic"
SIZE="5"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Redis 인스턴스 생성 시도
log "Redis 인스턴스 생성 중..."
if gcloud redis instances describe ${REDIS_INSTANCE} --region=${REGION} &>/dev/null; then
    log "Redis 인스턴스가 이미 존재함"
    REDIS_HOST=$(gcloud redis instances describe ${REDIS_INSTANCE} --region=${REGION} --format="value(host)")
else
    gcloud redis instances create ${REDIS_INSTANCE} \
        --size=${SIZE} \
        --region=${REGION} \
        --tier=${TIER} \
        --redis-version=redis_6_x \
        --async
    
    log "Redis 인스턴스 생성 요청됨. 프로비저닝 대기 중... (약 5-10분 소요)"
    
    # 생성 완료 대기
    while true; do
        if gcloud redis instances describe ${REDIS_INSTANCE} --region=${REGION} &>/dev/null; then
            REDIS_HOST=$(gcloud redis instances describe ${REDIS_INSTANCE} --region=${REGION} --format="value(host)")
            log "✅ Redis 인스턴스 생성 완료: ${REDIS_HOST}"
            break
        fi
        sleep 30
    done
fi

# Redis 연결 정보 저장
echo "export REDIS_HOST=${REDIS_HOST}" >> ${PROJECT_ROOT}/.env
echo "export REDIS_PORT=6379" >> ${PROJECT_ROOT}/.env
[명령 1-4] Pub/Sub 토픽 및 구독 생성
다음 내용으로 scripts/setup_pubsub.py 파일을 생성하고 실행하라:
python#!/usr/bin/env python3
# scripts/setup_pubsub.py

import os
import sys
from google.cloud import pubsub_v1
from google.api_core.exceptions import AlreadyExists

# 환경 변수 설정
PROJECT_ID = "argo-813"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "keys", "argo-main-key.json"
)

publisher = pubsub_v1.PublisherClient()
subscriber = pubsub_v1.SubscriberClient()

# 토픽 및 구독 정의
TOPICS_AND_SUBSCRIPTIONS = {
    "local-file-events": ["bigquery-streaming", "agent-processing"],
    "gdrive-events": ["bigquery-streaming", "agent-processing"],
    "agent-tasks": ["master-orchestrator", "specialist-agents"],
    "agent-results": ["result-processor", "audit-logger"],
    "system-commands": ["infrastructure-manager", "code-generator"]
}

def create_topic_and_subscriptions(topic_name, subscription_names):
    """토픽과 구독을 생성합니다."""
    project_path = f"projects/{PROJECT_ID}"
    topic_path = publisher.topic_path(PROJECT_ID, topic_name)
    
    # 토픽 생성
    try:
        topic = publisher.create_topic(request={"name": topic_path})
        print(f"✅ 토픽 생성됨: {topic.name}")
    except AlreadyExists:
        print(f"ℹ️ 토픽이 이미 존재함: {topic_name}")
    
    # 구독 생성
    for sub_name in subscription_names:
        subscription_path = subscriber.subscription_path(
            PROJECT_ID, f"{topic_name}-{sub_name}"
        )
        try:
            subscription = subscriber.create_subscription(
                request={
                    "name": subscription_path,
                    "topic": topic_path,
                    "ack_deadline_seconds": 300,  # 5분
                    "message_retention_duration": {"seconds": 86400}  # 1일
                }
            )
            print(f"  ✅ 구독 생성됨: {subscription.name}")
        except AlreadyExists:
            print(f"  ℹ️ 구독이 이미 존재함: {sub_name}")

if __name__ == "__main__":
    print("=== Pub/Sub 토픽 및 구독 생성 시작 ===")
    
    for topic, subscriptions in TOPICS_AND_SUBSCRIPTIONS.items():
        create_topic_and_subscriptions(topic, subscriptions)
    
    print("✅ Pub/Sub 설정 완료")
[명령 1-5] Cloud Functions - 데이터 수집 파이프라인
다음 내용으로 cloud_functions/data_ingestion/main.py 파일을 생성하라:
python# cloud_functions/data_ingestion/main.py

import os
import json
import base64
import uuid
from datetime import datetime
from google.cloud import bigquery
from google.cloud import pubsub_v1

# 클라이언트 초기화
bq_client = bigquery.Client()
publisher = pubsub_v1.PublisherClient()
PROJECT_ID = os.environ.get('PROJECT_ID', 'argo-813')
DATASET_ID = 'omni_contextual_core'
TABLE_ID = 'events'

def process_file_event(event, context):
    """
    파일 이벤트를 처리하여 BigQuery에 저장합니다.
    Cloud Storage 트리거 또는 Pub/Sub 메시지로 호출됩니다.
    """
    try:
        # Pub/Sub 메시지 디코딩
        if 'data' in event:
            message_data = base64.b64decode(event['data']).decode('utf-8')
            file_info = json.loads(message_data)
        else:
            # Cloud Storage 이벤트 직접 처리
            file_info = {
                'name': event.get('name', 'unknown'),
                'bucket': event.get('bucket', 'unknown'),
                'size': event.get('size', 0),
                'updated': event.get('updated', datetime.utcnow().isoformat())
            }
        
        # BigQuery 행 데이터 생성
        row = {
            'event_id': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'source': file_info.get('source', 'gcs'),
            'content': json.dumps(file_info),
            'embeddings': [],  # 임베딩은 별도 프로세스에서 처리
            'metadata': json.dumps({
                'processed_by': 'data_ingestion_function',
                'version': '1.0'
            })
        }
        
        # BigQuery에 삽입
        table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
        errors = bq_client.insert_rows_json(table_ref, [row])
        
        if errors:
            print(f"BigQuery 삽입 오류: {errors}")
            return {'status': 'error', 'message': str(errors)}, 500
        
        print(f"✅ 이벤트 처리 완료: {row['event_id']}")
        
        # 에이전트 처리를 위해 Pub/Sub에 발행
        topic_path = publisher.topic_path(PROJECT_ID, 'agent-tasks')
        message = json.dumps({
            'event_id': row['event_id'],
            'action': 'PROCESS_NEW_DATA',
            'source': file_info.get('source', 'unknown')
        })
        
        future = publisher.publish(topic_path, message.encode('utf-8'))
        print(f"Pub/Sub 메시지 발행됨: {future.result()}")
        
        return {'status': 'success', 'event_id': row['event_id']}, 200
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        return {'status': 'error', 'message': str(e)}, 500

def sync_google_drive(request):
    """
    Google Drive 동기화를 수행합니다.
    HTTP 트리거로 호출되거나 스케줄러에 의해 정기적으로 실행됩니다.
    """
    try:
        from googleapiclient.discovery import build
        from google.oauth2 import service_account
        
        # 서비스 계정 인증
        credentials = service_account.Credentials.from_service_account_file(
            '/etc/secrets/argo-main-key.json',
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        
        drive_service = build('drive', 'v3', credentials=credentials)
        
        # 최근 변경된 파일 조회
        results = drive_service.files().list(
            pageSize=100,
            fields="files(id, name, mimeType, modifiedTime, size, parents)",
            orderBy="modifiedTime desc",
            q="modifiedTime > '2024-01-01T00:00:00'"
        ).execute()
        
        files = results.get('files', [])
        
        if not files:
            return {'status': 'success', 'message': 'No files to sync'}, 200
        
        # 각 파일을 BigQuery에 저장
        table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
        rows_to_insert = []
        
        for file in files:
            row = {
                'event_id': str(uuid.uuid4()),
                'timestamp': datetime.utcnow().isoformat(),
                'source': 'gdrive',
                'content': json.dumps(file),
                'embeddings': [],
                'metadata': json.dumps({
                    'sync_batch': datetime.utcnow().isoformat(),
                    'file_count': len(files)
                })
            }
            rows_to_insert.append(row)
        
        errors = bq_client.insert_rows_json(table_ref, rows_to_insert)
        
        if errors:
            print(f"BigQuery 삽입 오류: {errors}")
            return {'status': 'error', 'errors': errors}, 500
        
        print(f"✅ {len(files)}개 파일 동기화 완료")
        return {'status': 'success', 'synced_files': len(files)}, 200
        
    except Exception as e:
        print(f"Drive 동기화 오류: {str(e)}")
        
        # Director에게 수동 개입 요청
        if "insufficient authentication" in str(e).lower():
            return {
                'status': 'manual_intervention_required',
                'message': 'Google Drive API 액세스 권한이 필요합니다.',
                'action_required': 'GCP 콘솔에서 Drive API를 활성화하고 OAuth 동의 화면을 구성해주세요.',
                'instructions': 'https://console.cloud.google.com/apis/library/drive.googleapis.com'
            }, 403
        
        return {'status': 'error', 'message': str(e)}, 500
[명령 1-6] Cloud Functions 배포 스크립트
다음 내용으로 scripts/deploy_functions.sh 파일을 생성하고 실행하라:
bash#!/bin/bash
# scripts/deploy_functions.sh

source "$(dirname "$0")/../.env"
FUNCTIONS_DIR="${PROJECT_ROOT}/cloud_functions"
RETRY_COUNT=0

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

deploy_function() {
    local FUNCTION_NAME=$1
    local ENTRY_POINT=$2
    local TRIGGER_TYPE=$3
    local TRIGGER_RESOURCE=$4
    local SOURCE_DIR=$5
    
    log "함수 배포 중: ${FUNCTION_NAME}"
    
    # requirements.txt 생성
    cat > ${SOURCE_DIR}/requirements.txt << EOF
google-cloud-bigquery==3.3.5
google-cloud-pubsub==2.18.4
google-cloud-storage==2.10.0
google-api-python-client==2.100.0
EOF
    
    # 함수 배포
    if [ "$TRIGGER_TYPE" == "pubsub" ]; then
        gcloud functions deploy ${FUNCTION_NAME} \
            --runtime python310 \
            --trigger-topic ${TRIGGER_RESOURCE} \
            --entry-point ${ENTRY_POINT} \
            --source ${SOURCE_DIR} \
            --region ${REGION} \
            --service-account argo-functions@${PROJECT_ID}.iam.gserviceaccount.com \
            --set-env-vars PROJECT_ID=${PROJECT_ID} \
            --timeout 540s \
            --memory 512MB \
            --max-instances 10
    elif [ "$TRIGGER_TYPE" == "http" ]; then
        gcloud functions deploy ${FUNCTION_NAME} \
            --runtime python310 \
            --trigger-http \
            --allow-unauthenticated \
            --entry-point ${ENTRY_POINT} \
            --source ${SOURCE_DIR} \
            --region ${REGION} \
            --service-account argo-functions@${PROJECT_ID}.iam.gserviceaccount.com \
            --set-env-vars PROJECT_ID=${PROJECT_ID} \
            --timeout 540s \
            --memory 1GB
    fi
    
    if [ $? -eq 0 ]; then
        log "✅ 함수 배포 성공: ${FUNCTION_NAME}"
    else
        log "❌ 함수 배포 실패: ${FUNCTION_NAME}"
        return 1
    fi
}

# 데이터 수집 함수 배포
deploy_function \
    "process-file-events" \
    "process_file_event" \
    "pubsub" \
    "local-file-events" \
    "${FUNCTIONS_DIR}/data_ingestion"

deploy_function \
    "sync-google-drive" \
    "sync_google_drive" \
    "http" \
    "" \
    "${FUNCTIONS_DIR}/data_ingestion"

log "✅ Cloud Functions 배포 완료"

🤖 Phase 2: Layer 2 - Multi-Agent Ideation Swarm
[명령 2-1] ADK 에이전트 베이스 클래스 생성
다음 내용으로 agents/base_agent.py 파일을 생성하라:
python# agents/base_agent.py

import os
import json
import redis
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from google.cloud import pubsub_v1
from google.cloud import bigquery
import google.generativeai as genai

class BaseAgent(ABC):
    """모든 ARGO 에이전트의 베이스 클래스"""
    
    def __init__(self, agent_name: str, agent_type: str):
        self.agent_name = agent_name
        self.agent_type = agent_type
        self.project_id = os.environ.get('PROJECT_ID', 'argo-813')
        
        # Redis 연결
        redis_host = os.environ.get('REDIS_HOST', 'localhost')
        self.redis_client = redis.Redis(
            host=redis_host,
            port=6379,
            decode_responses=True
        )
        
        # Pub/Sub 클라이언트
        self.publisher = pubsub_v1.PublisherClient()
        self.subscriber = pubsub_v1.SubscriberClient()
        
        # BigQuery 클라이언트
        self.bq_client = bigquery.Client()
        
        # 에이전트 상태 초기화
        self.state = {
            'status': 'idle',
            'current_task': None,
            'task_history': []
        }
        
        # 에이전트 등록
        self._register_agent()
    
    def _register_agent(self):
        """Redis에 에이전트 등록"""
        agent_key = f"agent:{self.agent_name}"
        agent_info = {
            'name': self.agent_name,
            'type': self.agent_type,
            'status': 'active',
            'registered_at': datetime.utcnow().isoformat(),
            'capabilities': self.get_capabilities()
        }
        self.redis_client.hset(agent_key, mapping=agent_info)
        self.redis_client.expire(agent_key, 3600)  # 1시간 TTL
        print(f"✅ 에이전트 등록됨: {self.agent_name}")
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """에이전트의 능력을 반환"""
        pass
    
    @abstractmethod
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """작업을 처리하고 결과를 반환"""
        pass
    
    def publish_message(self, topic: str, message: Dict[str, Any]):
        """Pub/Sub에 메시지 발행"""
        topic_path = self.publisher.topic_path(self.project_id, topic)
        message_bytes = json.dumps(message).encode('utf-8')
        future = self.publisher.publish(topic_path, message_bytes)
        return future.result()
    
    def query_bigquery(self, query: str) -> List[Dict]:
        """BigQuery 쿼리 실행"""
        query_job = self.bq_client.query(query)
        results = query_job.result()
        return [dict(row) for row in results]
    
    def update_state(self, key: str, value: Any):
        """에이전트 상태 업데이트"""
        self.state[key] = value
        state_key = f"agent_state:{self.agent_name}"
        self.redis_client.hset(state_key, key, json.dumps(value))
    
    def get_shared_context(self, context_id: str) -> Dict:
        """공유 컨텍스트 조회"""
        context_key = f"context:{context_id}"
        context = self.redis_client.get(context_key)
        return json.loads(context) if context else {}
    
    def set_shared_context(self, context_id: str, data: Dict):
        """공유 컨텍스트 저장"""
        context_key = f"context:{context_id}"
        self.redis_client.setex(
            context_key,
            3600,  # 1시간 TTL
            json.dumps(data)
        )
    
    async def run(self):
        """에이전트 실행 루프"""
        print(f"🚀 {self.agent_name} 시작됨")
        
        subscription_path = self.subscriber.subscription_path(
            self.project_id,
            f"agent-tasks-{self.agent_type}"
        )
        
        while True:
            try:
                # Pub/Sub에서 메시지 수신
                response = self.subscriber.pull(
                    request={
                        "subscription": subscription_path,
                        "max_messages": 1
                    },
                    timeout=30
                )
                
                for msg in response.received_messages:
                    # 메시지 처리
                    task_data = json.loads(msg.message.data.decode('utf-8'))
                    
                    if self._should_process_task(task_data):
                        self.update_state('status', 'processing')
                        self.update_state('current_task', task_data)
                        
                        # 작업 처리
                        result = await self.process_task(task_data)
                        
                        # 결과 발행
                        self.publish_message('agent-results', {
                            'task_id': task_data.get('task_id'),
                            'agent': self.agent_name,
                            'result': result,
                            'timestamp': datetime.utcnow().isoformat()
                        })
                        
                        self.update_state('status', 'idle')
                        self.update_state('current_task', None)
                    
                    # 메시지 확인
                    self.subscriber.acknowledge(
                        request={
                            "subscription": subscription_path,
                            "ack_ids": [msg.ack_id]
                        }
                    )
                
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"❌ 에이전트 오류 ({self.agent_name}): {str(e)}")
                await asyncio.sleep(5)
    
    def _should_process_task(self, task: Dict) -> bool:
        """이 에이전트가 작업을 처리해야 하는지 판단"""
        target_agent = task.get('target_agent')
        if target_agent and target_agent != self.agent_name:
            return False
        
        required_capabilities = task.get('required_capabilities', [])
        agent_capabilities = self.get_capabilities()
        
        return any(cap in agent_capabilities for cap in required_capabilities)
[명령 2-2] Master Orchestrator 에이전트 생성
다음 내용으로 agents/master_orchestrator.py 파일을 생성하라:
python# agents/master_orchestrator.py

import os
import json
import uuid
from typing import Dict, Any, List
from agents.base_agent import BaseAgent
import google.generativeai as genai

class MasterOrchestratorAgent(BaseAgent):
    """전체 에이전트 스웜을 지휘하는 마스터 AI"""
    
    def __init__(self):
        super().__init__("MasterOrchestrator", "orchestrator")
        
        # Gemini 모델 초기화
        genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        
        # 등록된 에이전트 목록
        self.registered_agents = {}
        self._discover_agents()
    
    def get_capabilities(self) -> List[str]:
        return [
            "task_decomposition",
            "agent_coordination",
            "context_management",
            "result_synthesis",
            "decision_making"
        ]
    
    def _discover_agents(self):
        """Redis에서 활성 에이전트 발견"""
        agent_keys = self.redis_client.keys("agent:*")
        for key in agent_keys:
            agent_info = self.redis_client.hgetall(key)
            if agent_info.get('status') == 'active':
                agent_name = agent_info.get('name')
                self.registered_agents[agent_name] = agent_info
                print(f"📌 에이전트 발견: {agent_name}")
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Director의 요청을 분석하고 하위 작업으로 분해하여 전문 에이전트에게 위임
        """
        task_id = task.get('task_id', str(uuid.uuid4()))
        request = task.get('request', '')
        context = task.get('context', {})
        
        print(f"\n🎯 Master Orchestrator 작업 수신: {request[:100]}...")
        
        # 1. 작업 분석 및 분해
        decomposition = await self._decompose_task(request, context)
        
        # 2. 각 하위 작업을 적절한 에이전트에게 할당
        subtask_results = []
        for subtask in decomposition['subtasks']:
            agent = self._select_best_agent(subtask)
            
            if agent:
                # 에이전트에게 작업 할당
                subtask_message = {
                    'task_id': f"{task_id}_{subtask['id']}",
                    'parent_task_id': task_id,
                    'target_agent': agent,
                    'action': subtask['action'],
                    'parameters': subtask['parameters'],
                    'context': context
                }
                
                self.publish_message('agent-tasks', subtask_message)
                
                subtask_results.append({
                    'subtask_id': subtask['id'],
                    'assigned_to': agent,
                    'status': 'dispatched'
                })
                
                print(f"  ➡️ 작업 할당: {subtask['action']} -> {agent}")
            else:
                print(f"  ⚠️ 적합한 에이전트를 찾을 수 없음: {subtask['action']}")
        
        # 3. 컨텍스트 저장
        self.set_shared_context(task_id, {
            'original_request': request,
            'decomposition': decomposition,
            'subtask_assignments': subtask_results
        })
        
        return {
            'task_id': task_id,
            'status': 'orchestrated',
            'subtasks_count': len(decomposition['subtasks']),
            'assignments': subtask_results
        }
    
    async def _decompose_task(self, request: str, context: Dict) -> Dict:
        """Gemini를 사용하여 작업을 하위 작업으로 분해"""
        
        prompt = f"""
        당신은 ARGO 시스템의 Master Orchestrator입니다.
        Director의 요청을 분석하여 실행 가능한 하위 작업으로 분해하세요.
        
        Director의 요청: {request}
        
        현재 컨텍스트: {json.dumps(context, ensure_ascii=False)}
        
        사용 가능한 에이전트 유형:
        - UserContextAgent: 사용자 데이터 분석
        - CreativeAgent: 창의적 아이디어 생성
        - TechnicalAgent: 기술 구현 설계
        - DataAnalystAgent: 데이터 분석 및 인사이트
        
        다음 JSON 형식으로 응답하세요:
        {{
            "analysis": "요청 분석 요약",
            "subtasks": [
                {{
                    "id": "subtask_1",
                    "action": "작업 설명",
                    "required_capabilities": ["필요한 능력"],
                    "parameters": {{}},
                    "dependencies": []
                }}
            ]
        }}
        """
        
        response = self.model.generate_content(prompt)
        
        try:
            # JSON 파싱
            result = json.loads(response.text)
            return result
        except json.JSONDecodeError:
            # 파싱 실패 시 기본 구조 반환
            return {
                "analysis": "작업 분해 실패",
                "subtasks": [
                    {
                        "id": "default_1",
                        "action": request,
                        "required_capabilities": ["general"],
                        "parameters": {},
                        "dependencies": []
                    }
                ]
            }
    
    def _select_best_agent(self, subtask: Dict) -> str:
        """하위 작업에 가장 적합한 에이전트 선택"""
        required_capabilities = subtask.get('required_capabilities', [])
        
        best_agent = None
        best_score = 0
        
        for agent_name, agent_info in self.registered_agents.items():
            if agent_name == self.agent_name:
                continue
            
            agent_capabilities = json.loads(agent_info.get('capabilities', '[]'))
            
            # 능력 매칭 점수 계산
            score = sum(1 for cap in required_capabilities if cap in agent_capabilities)
            
            if score > best_score:
                best_score = score
                best_agent = agent_name
        
        return best_agent

# 실행 스크립트
if __name__ == "__main__":
    import asyncio
    
    # 환경 변수 설정
    os.environ['REDIS_HOST'] = os.environ.get('REDIS_HOST', 'localhost')
    os.environ['GEMINI_API_KEY'] = os.environ.get('GEMINI_API_KEY', '')
    
    # Master Orchestrator 실행
    orchestrator = MasterOrchestratorAgent()
    asyncio.run(orchestrator.run())
[명령 2-3] 전문 에이전트들 생성
다음 내용으로 agents/specialist_agents.py 파일을 생성하라:
python# agents/specialist_agents.py

import os
import json
import asyncio
from typing import Dict, Any, List
from agents.base_agent import BaseAgent
import google.generativeai as genai
from datetime import datetime, timedelta

class UserContextAgent(BaseAgent):
    """사용자의 전체 맥락을 이해하는 전문가"""
    
    def __init__(self):
        super().__init__("UserContextAnalyst", "context")
        genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))
        self.model = genai.GenerativeModel('gemini-1.5-flash')
    
    def get_capabilities(self) -> List[str]:
        return ["user_analysis", "pattern_recognition", "context_extraction", "behavior_prediction"]
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get('action', '')
        parameters = task.get('parameters', {})
        
        if 'analyze' in action.lower():
            return await self._analyze_user_context(parameters)
        elif 'pattern' in action.lower():
            return await self._find_patterns(parameters)
        else:
            return {'error': f'Unknown action: {action}'}
    
    async def _analyze_user_context(self, params: Dict) -> Dict:
        """BigQuery에서 사용자 데이터를 분석"""
        user_id = params.get('user_id', 'director_iness')
        time_range = params.get('time_range', '7d')
        
        # BigQuery 쿼리
        query = f"""
        SELECT 
            source,
            EXTRACT(HOUR FROM timestamp) as hour,
            EXTRACT(DAYOFWEEK FROM timestamp) as day_of_week,
            COUNT(*) as activity_count,
            ARRAY_AGG(DISTINCT JSON_EXTRACT_SCALAR(content, '$.type')) as content_types
        FROM `argo-813.omni_contextual_core.events`
        WHERE JSON_EXTRACT_SCALAR(metadata, '$.user_id') = @user_id
            AND timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {time_range})
        GROUP BY source, hour, day_of_week
        ORDER BY activity_count DESC
        LIMIT 100
        """
        
        results = self.query_bigquery(query)
        
        # Gemini로 인사이트 생성
        prompt = f"""
        다음 사용자 활동 데이터를 분석하여 주요 패턴과 인사이트를 도출하세요:
        {json.dumps(results, ensure_ascii=False)}
        
        다음을 포함한 분석 결과를 제공하세요:
        1. 가장 활발한 시간대
        2. 주요 활동 소스
        3. 행동 패턴
        4. 추천 사항
        """
        
        response = self.model.generate_content(prompt)
        
        return {
            'user_id': user_id,
            'analysis_period': time_range,
            'raw_data': results,
            'insights': response.text,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def _find_patterns(self, params: Dict) -> Dict:
        """사용자 행동 패턴 탐지"""
        # 구현 예정
        return {'status': 'pattern_analysis_pending'}


class CreativeIdeationAgent(BaseAgent):
    """창의적 아이디어 생성 전문가"""
    
    def __init__(self):
        super().__init__("CreativeIdeator", "creative")
        genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))
        self.model = genai.GenerativeModel('gemini-1.5-pro')
    
    def get_capabilities(self) -> List[str]:
        return ["brainstorming", "creative_writing", "concept_generation", "innovation"]
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get('action', '')
        parameters = task.get('parameters', {})
        
        if 'generate' in action.lower() or 'create' in action.lower():
            return await self._generate_ideas(parameters)
        else:
            return {'error': f'Unknown action: {action}'}
    
    async def _generate_ideas(self, params: Dict) -> Dict:
        """창의적 아이디어 생성"""
        topic = params.get('topic', '')
        context = params.get('context', {})
        constraints = params.get('constraints', [])
        
        prompt = f"""
        당신은 ARGO 시스템의 창의적 아이디어 생성 전문가입니다.
        
        주제: {topic}
        컨텍스트: {json.dumps(context, ensure_ascii=False)}
        제약사항: {', '.join(constraints)}
        
        다음 관점에서 혁신적인 아이디어를 생성하세요:
        1. 기술적 실현 가능성
        2. 비즈니스 가치
        3. 사용자 경험
        4. 차별화 요소
        
        최소 5개의 구체적인 아이디어를 제시하세요.
        """
        
        response = self.model.generate_content(prompt)
        
        return {
            'topic': topic,
            'ideas': response.text,
            'generation_method': 'gemini_pro',
            'timestamp': datetime.utcnow().isoformat()
        }


class TechnicalArchitectAgent(BaseAgent):
    """기술 아키텍처 설계 전문가"""
    
    def __init__(self):
        super().__init__("TechnicalArchitect", "technical")
        genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))
        self.model = genai.GenerativeModel('gemini-1.5-pro')
    
    def get_capabilities(self) -> List[str]:
        return ["architecture_design", "code_review", "tech_stack_selection", "optimization"]
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get('action', '')
        parameters = task.get('parameters', {})
        
        if 'design' in action.lower():
            return await self._design_architecture(parameters)
        elif 'optimize' in action.lower():
            return await self._optimize_system(parameters)
        else:
            return {'error': f'Unknown action: {action}'}
    
    async def _design_architecture(self, params: Dict) -> Dict:
        """시스템 아키텍처 설계"""
        requirements = params.get('requirements', '')
        constraints = params.get('constraints', {})
        
        prompt = f"""
        다음 요구사항에 맞는 기술 아키텍처를 설계하세요:
        
        요구사항: {requirements}
        제약사항: {json.dumps(constraints, ensure_ascii=False)}
        
        사용 가능한 기술 스택:
        - GCP (BigQuery, Cloud Functions, Cloud Run, Vertex AI)
        - Redis, Neo4j
        - Python, TypeScript
        - Pulumi (IaC)
        
        다음을 포함한 아키텍처 설계를 제공하세요:
        1. 시스템 구성도
        2. 데이터 흐름
        3. 기술 스택 선택 근거
        4. 확장성 고려사항
        5. 보안 고려사항
        """
        
        response = self.model.generate_content(prompt)
        
        return {
            'requirements': requirements,
            'architecture': response.text,
            'design_method': 'gemini_pro',
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def _optimize_system(self, params: Dict) -> Dict:
        """시스템 최적화 제안"""
        # 구현 예정
        return {'status': 'optimization_pending'}


# 에이전트 실행 스크립트
async def run_all_agents():
    """모든 전문 에이전트 실행"""
    agents = [
        UserContextAgent(),
        CreativeIdeationAgent(),
        TechnicalArchitectAgent()
    ]
    
    # 각 에이전트를 비동기로 실행
    tasks = [agent.run() for agent in agents]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    import asyncio
    
    # 환경 변수 설정
    os.environ['REDIS_HOST'] = os.environ.get('REDIS_HOST', 'localhost')
    os.environ['GEMINI_API_KEY'] = os.environ.get('GEMINI_API_KEY', '')
    
    print("🚀 전문 에이전트들 시작 중...")
    asyncio.run(run_all_agents())

📊 Phase 1-2 검증 및 감사
[명령 V-1] Phase 검증 스크립트
다음 내용으로 scripts/validate_phase.py 파일을 생성하고 실행하라:
python#!/usr/bin/env python3
# scripts/validate_phase.py

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path
import hashlib

class PhaseValidator:
    def __init__(self, phase_number):
        self.phase_number = phase_number
        self.project_root = Path(__file__).parent.parent
        self.report = {
            'phase': phase_number,
            'timestamp': datetime.utcnow().isoformat(),
            'checks': [],
            'files_created': [],
            'services_deployed': [],
            'issues': [],
            'ready_for_commit': False
        }
    
    def check_file_exists(self, filepath, description):
        """파일 존재 여부 확인"""
        full_path = self.project_root / filepath
        exists = full_path.exists()
        
        check_result = {
            'type': 'file_check',
            'path': str(filepath),
            'description': description,
            'status': 'PASS' if exists else 'FAIL'
        }
        
        if exists:
            # 파일 해시 계산 (무결성 확인)
            with open(full_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            check_result['hash'] = file_hash
            self.report['files_created'].append(str(filepath))
        else:
            self.report['issues'].append(f"Missing file: {filepath}")
        
        self.report['checks'].append(check_result)
        return exists
    
    def check_gcp_service(self, service_type, name, description):
        """GCP 서비스 배포 상태 확인"""
        check_result = {
            'type': 'gcp_service',
            'service': service_type,
            'name': name,
            'description': description,
            'status': 'UNKNOWN'
        }
        
        try:
            if service_type == 'bigquery_dataset':
                cmd = f"bq ls -d --project_id=argo-813 | grep {name}"
            elif service_type == 'pubsub_topic':
                cmd = f"gcloud pubsub topics list --project=argo-813 | grep {name}"
            elif service_type == 'cloud_function':
                cmd = f"gcloud functions list --project=argo-813 --region=asia-northeast3 | grep {name}"
            elif service_type == 'redis':
                cmd = f"gcloud redis instances describe {name} --region=asia-northeast3 --project=argo-813"
            else:
                cmd = None
            
            if cmd:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    check_result['status'] = 'DEPLOYED'
                    self.report['services_deployed'].append(f"{service_type}:{name}")
                else:
                    check_result['status'] = 'NOT_FOUND'
                    self.report['issues'].append(f"Service not deployed: {service_type}:{name}")
        except Exception as e:
            check_result['status'] = 'ERROR'
            check_result['error'] = str(e)
            self.report['issues'].append(f"Error checking {service_type}:{name} - {str(e)}")
        
        self.report['checks'].append(check_result)
        return check_result['status'] == 'DEPLOYED'
    
    def validate_phase_1(self):
        """Phase 1 검증"""
        print("=== Phase 1: Omni-Contextual Core 검증 시작 ===")
        
        # 필수 파일 확인
        files_to_check = [
            ('scripts/init_project.sh', '프로젝트 초기화 스크립트'),
            ('scripts/create_service_accounts.sh', '서비스 계정 생성 스크립트'),
            ('scripts/setup_bigquery.sh', 'BigQuery 설정 스크립트'),
            ('scripts/setup_redis.sh', 'Redis 설정 스크립트'),
            ('scripts/setup_pubsub.py', 'Pub/Sub 설정 스크립트'),
            ('cloud_functions/data_ingestion/main.py', '데이터 수집 Cloud Function'),
            ('configs/bigquery_schemas/events_schema.json', 'BigQuery 이벤트 스키마'),
            ('.env', '환경 변수 파일'),
        ]
        
        for filepath, desc in files_to_check:
            self.check_file_exists(filepath, desc)
        
        # GCP 서비스 확인
        self.check_gcp_service('bigquery_dataset', 'omni_contextual_core', 'BigQuery 데이터셋')
        self.check_gcp_service('pubsub_topic', 'local-file-events', 'Pub/Sub 토픽')
        self.check_gcp_service('pubsub_topic', 'agent-tasks', 'Pub/Sub 토픽')
        self.check_gcp_service('redis', 'argo-cache', 'Redis 인스턴스')
        
        # 서비스 계정 키 확인
        key_files = [
            'keys/argo-main-key.json',
            'keys/argo-functions-key.json',
            'keys/argo-bigquery-key.json'
        ]
        
        for key_file in key_files:
            self.check_file_exists(key_file, f'서비스 계정 키: {key_file}')
    
    def validate_phase_2(self):
        """Phase 2 검증"""
        print("=== Phase 2: Multi-Agent Swarm 검증 시작 ===")
        
        files_to_check = [
            ('agents/base_agent.py', '에이전트 베이스 클래스'),
            ('agents/master_orchestrator.py', 'Master Orchestrator'),
            ('agents/specialist_agents.py', '전문 에이전트들'),
        ]
        
        for filepath, desc in files_to_check:
            self.check_file_exists(filepath, desc)
        
        # 에이전트 실행 테스트
        # TODO: 에이전트 연결 테스트 추가
    
    def generate_report(self):
        """검증 보고서 생성"""
        
        # 전체 상태 결정
        total_checks = len(self.report['checks'])
        passed_checks = sum(1 for c in self.report['checks'] if c['status'] in ['PASS', 'DEPLOYED'])
        
        self.report['summary'] = {
            'total_checks': total_checks,
            'passed': passed_checks,
            'failed': total_checks - passed_checks,
            'pass_rate': f"{(passed_checks/total_checks*100):.1f}%" if total_checks > 0 else "0%"
        }
        
        self.report['ready_for_commit'] = (passed_checks == total_checks) and len(self.report['issues']) == 0
        
        # 보고서 저장
        report_file = self.project_root / f"reports/phase_{self.phase_number}_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_file.parent.mkdir(exist_ok=True)
        
        with open(report_file, 'w') as f:
            json.dump(self.report, f, indent=2, ensure_ascii=False)
        
        # 콘솔 출력
        print("\n" + "="*60)
        print(f"📊 Phase {self.phase_number} 검증 보고서")
        print("="*60)
        print(f"총 검사 항목: {total_checks}")
        print(f"성공: {passed_checks}")
        print(f"실패: {total_checks - passed_checks}")
        print(f"통과율: {self.report['summary']['pass_rate']}")
        
        if self.report['issues']:
            print("\n⚠️ 발견된 문제:")
            for issue in self.report['issues']:
                print(f"  - {issue}")
        
        if self.report['ready_for_commit']:
            print("\n✅ Phase 검증 완료! Git 커밋 준비 완료")
            print("\n다음 명령으로 커밋을 요청하세요:")
            print(f"  python scripts/request_commit.py {self.phase_number}")
        else:
            print("\n❌ Phase 검증 실패. 위의 문제를 해결한 후 다시 실행하세요.")
            
            # Director에게 수동 개입 요청
            manual_tasks_file = self.project_root / "manual_tasks.txt"
            with open(manual_tasks_file, 'a') as f:
                f.write(f"\n[{datetime.now().isoformat()}] Phase {self.phase_number} 검증 실패\n")
                for issue in self.report['issues']:
                    f.write(f"  - {issue}\n")
            
            print(f"\n📝 수동 작업 필요 사항이 {manual_tasks_file}에 기록되었습니다.")
        
        return self.report['ready_for_commit']

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python validate_phase.py <phase_number>")
        sys.exit(1)
    
    phase_number = int(sys.argv[1])
    validator = PhaseValidator(phase_number)
    
    if phase_number == 1:
        validator.validate_phase_1()
    elif phase_number == 2:
        validator.validate_phase_2()
    else:
        print(f"Unknown phase: {phase_number}")
        sys.exit(1)
    
    success = validator.generate_report()
    sys.exit(0 if success else 1)
[명령 V-2] Git 커밋 요청 스크립트
다음 내용으로 scripts/request_commit.py 파일을 생성하라:
python#!/usr/bin/env python3
# scripts/request_commit.py

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path

def request_commit_approval(phase_number):
    project_root = Path(__file__).parent.parent
    
    # 최신 검증 보고서 찾기
    reports_dir = project_root / "reports"
    report_files = list(reports_dir.glob(f"phase_{phase_number}_validation_*.json"))
    
    if not report_files:
        print(f"❌ Phase {phase_number}의 검증 보고서를 찾을 수 없습니다.")
        print("먼저 python scripts/validate_phase.py를 실행하세요.")
        return False
    
    latest_report = max(report_files, key=lambda p: p.stat().st_mtime)
    
    with open(latest_report, 'r') as f:
        report = json.load(f)
    
    if not report['ready_for_commit']:
        print("❌ Phase 검증이 완료되지 않았습니다. 문제를 해결한 후 다시 시도하세요.")
        return False
    
    # Git 상태 확인
    result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
    changed_files = result.stdout.strip().split('\n') if result.stdout.strip() else []
    
    print("\n" + "="*60)
    print(f"🔄 Phase {phase_number} Git 커밋 승인 요청")
    print("="*60)
    
    print(f"\n📊 검증 요약:")
    print(f"  - 총 검사: {report['summary']['total_checks']}")
    print(f"  - 통과: {report['summary']['passed']}")
    print(f"  - 통과율: {report['summary']['pass_rate']}")
    
    print(f"\n📁 생성된 파일 ({len(report['files_created'])}개):")
    for file in report['files_created'][:10]:  # 처음 10개만 표시
        print(f"  - {file}")
    if len(report['files_created']) > 10:
        print(f"  ... 외 {len(report['files_created']) - 10}개")
    
    print(f"\n🚀 배포된 서비스 ({len(report['services_deployed'])}개):")
    for service in report['services_deployed']:
        print(f"  - {service}")
    
    print(f"\n📝 변경된 파일 ({len(changed_files)}개):")
    for file in changed_files[:10]:
        print(f"  {file}")
    if len(changed_files) > 10:
        print(f"  ... 외 {len(changed_files) - 10}개")
    
    print("\n" + "-"*60)
    print("Director님, 위 내용을 검토하시고 커밋을 승인해주세요.")
    print("\n승인하시려면 'yes'를 입력하세요 (거부: 'no'):")
    
    approval = input("> ").strip().lower()
    
    if approval == 'yes':
        # Git 커밋 실행
        commit_message = f"Phase {phase_number}: {get_phase_description(phase_number)} - Completed"
        
        subprocess.run(['git', 'add', '.'])
        subprocess.run(['git', 'commit', '-m', commit_message])
        
        print(f"\n✅ Phase {phase_number} 커밋 완료!")
        print("다음 Phase를 진행할 준비가 되었습니다.")
        
        # 다음 Phase 안내
        next_phase = phase_number + 1
        print(f"\n다음 명령으로 Phase {next_phase}를 시작하세요:")
        print(f"  python scripts/start_phase.py {next_phase}")
        
        return True
    else:
        print("\n커밋이 취소되었습니다.")
        return False

def get_phase_description(phase_number):
    descriptions = {
        0: "Initial Setup & Service Accounts",
        1: "Omni-Contextual Core",
        2: "Multi-Agent Ideation Swarm",
        3: "Creative & Analytical Unit",
        4: "Autonomous Development Arm",
        5: "Multi-tenant Architecture"
    }
    return descriptions.get(phase_number, f"Phase {phase_number}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python request_commit.py <phase_number>")
        sys.exit(1)
    
    phase_number = int(sys.argv[1])
    success = request_commit_approval(phase_number)
    sys.exit(0 if success else 1)

🚀 최종 실행 명령 - 커서 AI 전용
[AUTORUN] 완전 자동 실행 스크립트
다음 내용으로 AUTORUN.sh 파일을 생성하고 실행하라:
bash#!/bin/bash
# AUTORUN.sh - ARGO 시스템 완전 자동 구축 스크립트

set -e
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd $PROJECT_ROOT

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Git 저장소 초기화
if [ ! -d ".git" ]; then
    log "Git 저장소 초기화 중..."
    git init
    git remote add origin https://github.com/INESS-741209/Argo-813.git
fi

# Phase 0: 초기 설정
log "🚀 Phase 0: 프로젝트 초기화 시작"
chmod +x scripts/init_project.sh
./scripts/init_project.sh

log "🔐 서비스 계정 생성 중..."
chmod +x scripts/create_service_accounts.sh
./scripts/create_service_accounts.sh

# 환경 변수 로드
source .env

# Phase 1: Omni-Contextual Core
log "📦 Phase 1: Omni-Contextual Core 구축 시작"

log "BigQuery 설정 중..."
chmod +x scripts/setup_bigquery.sh
./scripts/setup_bigquery.sh

log "Redis 설정 중..."
chmod +x scripts/setup_redis.sh
./scripts/setup_redis.sh

log "Pub/Sub 설정 중..."
python3 scripts/setup_pubsub.py

log "Cloud Functions 배포 중..."
chmod +x scripts/deploy_functions.sh
./scripts/deploy_functions.sh

# Phase 1 검증
log "🔍 Phase 1 검증 중..."
if python3 scripts/validate_phase.py 1; then
    log "✅ Phase 1 검증 성공!"
    
    # 자동 커밋 (Director 승인 대기)
    warning "Director님의 커밋 승인이 필요합니다."
    echo "yes" | python3 scripts/request_commit.py 1
else
    error "Phase 1 검증 실패. manual_tasks.txt를 확인하세요."
    exit 1
fi

# Phase 2: Multi-Agent Swarm
log "🤖 Phase 2: Multi-Agent Swarm 구축 시작"

# Python 패키지 설치
pip install -r requirements.txt

# 에이전트 실행 (백그라운드)
log "에이전트 시작 중..."
python3 agents/master_orchestrator.py &
MASTER_PID=$!
python3 agents/specialist_agents.py &
SPECIALIST_PID=$!

sleep 10

# Phase 2 검증
log "🔍 Phase 2 검증 중..."
if python3 scripts/validate_phase.py 2; then
    log "✅ Phase 2 검증 성공!"
    echo "yes" | python3 scripts/request_commit.py 2
else
    error "Phase 2 검증 실패."
    kill $MASTER_PID $SPECIALIST_PID
    exit 1
fi

log "=" * 60
log "🎉 ARGO 시스템 Phase 1-2 구축 완료!"
log "=" * 60
log ""
log "다음 단계:"
log "1. manual_tasks.txt 파일을 확인하여 수동 작업 완료"
log "2. Google Drive API 권한 설정"
log "3. Vertex AI API 키 설정"
log "4. Phase 3 시작: ./scripts/start_phase.py 3"
