// PID 존재 여부와 별개로 프로세스 시작 시각이 recorder 레코드와 일치하는지 검증하는 격리 후보다.
export function processStartMatchesRecord(record, observedStartedAt, toleranceMs = 2000) {
  const observedMs = Date.parse(observedStartedAt ?? '');
  if (!Number.isFinite(observedMs)) return null;
  const recordedProcessStartMs = Date.parse(record?.processStartedAt ?? '');
  if (Number.isFinite(recordedProcessStartMs)) return Math.abs(observedMs - recordedProcessStartMs) <= toleranceMs;
  const legacyReferenceMs = Date.parse(record?.createdAt ?? record?.startedAt ?? '');
  if (!Number.isFinite(legacyReferenceMs)) return null;
  return observedMs <= legacyReferenceMs + toleranceMs;
}
