// [역할] Claude 자동 기록의 단계적 활성화 상태를 명시적으로 반환한다.
// [의존성 관계] Codex·Antigravity 1차 버전 안정화 후 실제 Claude 원본 adapter로 교체된다.
// [변경 시 영향도] 접근 가능한 원본과 정확한 시각이 fixture로 검증되기 전에는 status를 ok로 바꾸면 안 된다.

// Claude는 이번 1차 버전에서 추정 기록을 만들지 않고 unsupported로 고정한다.
export async function collectClaudeEvents() {
  // 사용자 계획의 단계적 활성화 원칙에 따라 명확한 상태와 빈 이벤트를 반환한다.
  return { platform: 'claude', status: 'unsupported', events: [], snapshots: {}, errors: ['Claude 어댑터는 Codex·Antigravity 안정화 이후 별도 capability 검증 대상으로 예약되었습니다.'] };
}
