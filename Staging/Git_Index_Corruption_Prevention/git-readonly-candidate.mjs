import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

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

const FORBIDDEN_ARGUMENTS = [
  /^--exec(?:=|$)/,
  /^--ext-diff$/,
  /^--output(?:=|$)/,
  /^--textconv$/
];

export function createReadOnlyGitEnvironment(baseEnvironment = process.env) {
  return { ...baseEnvironment, GIT_OPTIONAL_LOCKS: '0' };
}

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
