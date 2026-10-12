# 무료 서버로 RSI 연구를 이어가는 방법

확인 날짜: 2026-10-12. 이 문서는 실행 준비 안내입니다. Oracle 서버 생성이나 24시간 실운영 검증은 아직 수행하지 않았습니다.

## 카드 없이 먼저 실행하기

현재 우선 경로는 기존 공개 GitHub 저장소의 표준 실행기를 이용한 **24시간 한정 연구 모드**입니다. 추가 계정이나 카드 등록 없이, 30분마다 실제 평가를 시도하고 최대 48회 또는 24시간 후 기존 예약으로 돌아갑니다. 소유자는 한국어 실험실의 **24시간 연구 시작 / 종료** 버튼이나 `scripts/study.py`로 제어합니다. 상세 사용법은 [한국어 안내](../README.ko.md)를 참고하세요.

이 모드는 실험 사이에 대기 시간이 있고 GitHub 예약이 지연되거나 누락될 수 있습니다. 아래 Oracle 경로는 별도 상시 서버를 확보하려는 경우의 선택 사항입니다. Oracle 가입 시 카드 확인이 필요한 사용자는 현재 GitHub 연구 모드를 먼저 사용할 수 있습니다.

## 추천 구성

- GitHub: 기존 코드와 실행·검사 기록.
- GitHub Pages: 기존 한국어 화면.
- Cloudflare: 기존 연구 상태, 평가 결과, 다음 작업 보관.
- Oracle Cloud Always Free A1 서버: Qwen3.5-2B 추론과 RSI 실험 실행.

추론용 서버만 추가합니다. 기존 기준 모델과 평가·채택 규칙을 그대로 사용하며, 컴퓨터를 꺼도 서버에서 연구를 이어가는 구성입니다.

## 무료 서버 선택

Oracle 공식 문서의 현재 Always Free A1 범위는 계정 전체 합계 **2 OCPU, 메모리 12GB**입니다. 월 1,500 OCPU 시간과 9,000 GB 시간이 포함됩니다. 한 서버에 2 OCPU·12GB를 배정하면 31일의 계산량은 각각 1,488 OCPU 시간과 8,928 GB 시간입니다. 다른 A1 서버도 있다면 그 사용량을 합산해야 합니다.

선택할 항목:

1. 계정의 홈 리전에서 서버를 만듭니다.
2. 이미지: Always Free 대상인 Ubuntu ARM64.
3. 서버 형태: `VM.Standard.A1.Flex`.
4. CPU: 2 OCPU. 메모리: 12GB.
5. 부팅 디스크: 50GB. 계정의 무료 디스크 전체 한도 200GB 안에서 사용합니다.
6. 생성 화면에서 무료 대상 여부와 실제 가격을 확인합니다.

메모리 1GB인 AMD Micro 서버는 현재 프로젝트의 5GiB 가용 메모리 조건을 충족하지 못합니다. 30일 체험 크레딧과 Always Free는 다릅니다. 상시 운영은 Always Free 범위로 준비해야 합니다.

무료 서버는 해당 리전의 자원이 부족하면 생성하지 못할 수 있습니다. 유휴 상태인 무료 서버는 회수될 수 있습니다. 이 때문에 무료 서버의 무중단 운영을 보장하지는 않습니다. Cloudflare에 기록을 계속 저장해 서버가 없어져도 연구를 다시 이어갈 수 있게 합니다.

## 계정이 없다면

[Oracle 무료 가입](https://signup.cloud.oracle.com/)에서 사용자가 계정을 준비해야 합니다. 공식 안내에 따르면 대부분 휴대전화와 신용카드 확인이 필요하며, 유료 계정으로 업그레이드하지 않으면 카드에 요금이 청구되지 않습니다. 가입 정보·비밀번호·카드 정보를 채팅에 보내지 마세요.

## 서버를 확보한 뒤의 작업

1. SSH로 서버에 연결하고 CPU·메모리·ARM64·디스크를 확인합니다.
2. Ollama 공식 ARM64 배포판과 현재 선택한 `qwen3.5:2b-q4_K_M`을 설치합니다. ARM64 패키지 지원은 확인했지만, 이 프로젝트의 해당 서버 실측은 아직 없습니다.
3. GitHub의 검증된 소스를 내려받습니다.
4. 기존 `RSI_URL`과 `RSI_TOKEN`을 서버의 비공개 환경 파일에 설정합니다. 추론 API는 서버 내부에서만 접근하도록 유지합니다.
5. 같은 모델 digest인지 확인하고, 첫 번째 실제 평가를 실행합니다. 다른 하드웨어의 실행 시간을 이전 실행과 섞지 않습니다.
6. Linux 서비스로 Ollama와 RSI 실행을 관리해 종료·재부팅 후 자동 복구되도록 구성합니다.
7. 첫 실행과 복구가 검증된 뒤 24시간 관찰합니다. 실패·미채택 결과도 기록합니다.

현재 실행 프로그램에는 `python -m rsi run --continuous` 옵션이 있습니다. 이 옵션은 실험 후 15분 대기하고 다시 확인하는 반복 실행입니다. **현재 온라인 서버의 하루 4회 완료 제한은 이 옵션으로 바뀌지 않습니다.**

따라서 24시간 동안 여러 실험을 이어가려면, 별도 서버의 메모리·속도·무료 사용량을 먼저 측정하고 Cloudflare의 실험 한도를 조정해야 합니다. 한도를 무제한으로 제거하는 대신 하루 실험 수, 저장량, 재시도 제한을 정하고 화면에도 실제 한도를 표시해야 합니다.

GPU 추가 학습(LoRA)은 이 CPU 서버의 실행 범위에 포함하지 않습니다. 모델 자체의 추가 학습 성공은 별도 장비와 검증 기록이 필요합니다.

## GitHub의 역할

공개 저장소의 표준 GitHub 실행기는 무료이며, 개발·시험용 작업을 실행할 수 있습니다. 단일 작업은 최대 6시간이고 예약 실행은 지연되거나 누락될 수 있습니다. 기존 예약 실험은 보조 실행 경로로 유지할 수 있지만, 상시 실행 서버 확보와 같은 의미는 아닙니다.

## 확인한 공식 자료

- [Oracle Always Free 자원과 리전·회수 조건](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [Oracle Free Tier 가입과 체험 종료 조건](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm)
- [Ollama Linux ARM64 설치와 서비스 관리](https://docs.ollama.com/linux)
- [GitHub Actions 무료 표준 실행기](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [GitHub Actions 실행 제한](https://docs.github.com/en/actions/reference/limits)
- [GitHub 예약 실행 조건](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [GitHub Actions 이용 조건](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features)
