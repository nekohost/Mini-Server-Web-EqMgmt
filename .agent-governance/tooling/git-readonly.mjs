import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// 에이전트와 거버넌스가 상태를 조회할 때 사용할 수 있는 Git subcommand만 허용한다.
export const READ_ONLY_SUBCOMMANDS = new Set([
  'cat-file',
  'check-attr',
  'check-ignore',
  'describe',
  'diff',
  'diff-files',
  'diff-index',
  'for-each-ref',
  'fsck',
  'log',
  'ls-files',
  'name-rev',
  'rev-parse',
  'show',
  'status'
]);

// 조회 명령이라도 파일 출력이나 외부 프로그램 실행으로 범위가 넓어지는 옵션은 차단한다.
const FORBIDDEN_ARGUMENTS = [
  /^--exec(?:=|$)/,
  /^--ext-diff$/,
  /^--output(?:=|$)/,
  /^--textconv$/
];

// 기존 환경은 보존하되 optional index refresh와 optional lock은 항상 비활성화한다.
export function createReadOnlyGitEnvironment(baseEnvironment = process.env) {
  return { ...baseEnvironment, GIT_OPTIONAL_LOCKS: '0' };
}

// `--` 구분자를 제거하고 허용된 조회 명령과 인자만 반환한다.
export function validateReadOnlyArguments(inputArguments) {
  const args = [...inputArguments];
  if (args[0] === '--') args.shift();
  const subcommand = args[0];
  if (!READ_ONLY_SUBCOMMANDS.has(subcommand)) {
    throw new Error(`허용되지 않은 Git read-only subcommand: ${subcommand ?? '(없음)'}`);
  }
  const forbidden = args.find((argument) => FORBIDDEN_ARGUMENTS.some((pattern) => pattern.test(argument)));
  if (forbidden) throw new Error(`read-only wrapper에서 허용되지 않은 인자: ${forbidden}`);
  return args;
}

// 검증된 인자를 실제 Git에 전달하고 호출별로 optional lock 억제를 강제한다.
export function runReadOnlyGit(inputArguments, options = {}) {
  const args = validateReadOnlyArguments(inputArguments);
  const result = spawnSync(options.gitExecutable ?? 'git', args, {
    cwd: options.cwd ?? process.cwd(),
    env: createReadOnlyGitEnvironment(options.env ?? process.env),
    encoding: options.encoding,
    stdio: options.stdio ?? 'inherit',
    windowsHide: true
  });
  if (result.error) throw result.error;
  return result;
}

// CLI에서는 자식 Git의 종료 코드를 그대로 전달하고 wrapper 입력 오류는 2로 구분한다.
export function main(argv = process.argv.slice(2)) {
  try {
    const result = runReadOnlyGit(argv);
    process.exitCode = result.status ?? 1;
  } catch (error) {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 2;
  }
}

const isDirectExecution = process.argv[1]
  && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isDirectExecution) main();
