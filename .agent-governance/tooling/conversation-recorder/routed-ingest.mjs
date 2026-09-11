// [역할] General dispatcher가 전달한 scope-routed ChatGPT event를 검증하고 기존 Mini-Server Chat writer에 투영한다.
// [의존성 관계] target/authority Rule·manifest·capability·bootstrap fingerprint와 conversation-recorder core에 의존한다.
// [변경 시 영향도] envelope schema 또는 검증 기준을 바꾸면 General routed-delivery contract와 양쪽 E2E를 함께 갱신해야 한다.

import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { parseDocument } from 'yaml';
import {
  normalizeNewlines,
  projectEvents,
  readState,
  redactSecrets,
  renderEventBlock,
  sha256,
  toKstParts,
  withWriterLock,
  writeState,
} from './core.mjs';

const ENVELOPE_SCHEMA = 'general.routed-conversation-envelope.v1';
const PLATFORM = 'chatgpt-remote';
const VISIBLE_CHANNELS = new Set(['user', 'commentary', 'final_answer']);
const EXACT_TIME_QUALITY = new Set(['provider-exact', 'adapter-exact']);

function canonicalJson(value) {
  if (Array.isArray(value)) return value.map(canonicalJson);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalJson(value[key])]));
  return value;
}

function shaJson(value) {
  return crypto.createHash('sha256').update(JSON.stringify(canonicalJson(value)), 'utf8').digest('hex').toUpperCase();
}

function shaFile(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex').toUpperCase();
}

function readYaml(filePath) {
  const document = parseDocument(fs.readFileSync(filePath, 'utf8'), { uniqueKeys: true, prettyErrors: true });
  if (document.errors.length) throw new Error(`governance-yaml-invalid:${document.errors.map((error) => error.message).join('|')}`);
  return document.toJS();
}

function canonicalPath(filePath) {
  const resolved = path.resolve(filePath);
  return fs.realpathSync.native ? fs.realpathSync.native(resolved) : fs.realpathSync(resolved);
}

function samePath(left, right) {
  return process.platform === 'win32'
    ? path.normalize(left).toLowerCase() === path.normalize(right).toLowerCase()
    : path.normalize(left) === path.normalize(right);
}

function inside(root, candidate) {
  const relative = path.relative(path.resolve(root), path.resolve(candidate));
  return relative === '' || (!relative.startsWith('..') && !path.isAbsolute(relative));
}

export function fingerprintWorkspace(workspaceRoot, platform = PLATFORM) {
  const root = canonicalPath(workspaceRoot);
  const governanceRoot = path.join(root, '.agent-governance');
  const manifestPath = path.join(governanceRoot, 'manifest.yaml');
  const rulePath = path.join(root, 'Rule.md');
  if (![manifestPath, rulePath].every((candidate) => fs.existsSync(candidate) && fs.statSync(candidate).isFile())) throw new Error('governance-required-file-missing');
  const manifest = readYaml(manifestPath);
  const humanPath = path.resolve(governanceRoot, String(manifest.human_reference?.path ?? ''));
  if (!fs.existsSync(humanPath) || !samePath(canonicalPath(humanPath), canonicalPath(rulePath))) throw new Error('governance-human-reference-mismatch');
  const ruleHash = shaFile(rulePath);
  if (String(manifest.human_reference?.sha256 ?? '').toUpperCase() !== ruleHash) throw new Error('governance-rule-hash-mismatch');
  const capabilityRelative = manifest.capabilities?.[platform];
  if (typeof capabilityRelative !== 'string' || !capabilityRelative) throw new Error('governance-platform-capability-missing');
  const capabilityPath = path.resolve(governanceRoot, capabilityRelative);
  if (!inside(governanceRoot, capabilityPath) || !fs.existsSync(capabilityPath) || !fs.statSync(capabilityPath).isFile()) throw new Error('governance-capability-invalid');
  const capability = readYaml(capabilityPath);
  const bootstrapRelative = capability.instruction_entrypoint;
  if (typeof bootstrapRelative !== 'string' || !bootstrapRelative) throw new Error('governance-bootstrap-missing');
  const bootstrapPath = path.resolve(root, bootstrapRelative);
  if (!inside(root, bootstrapPath) || !fs.existsSync(bootstrapPath) || !fs.statSync(bootstrapPath).isFile()) throw new Error('governance-bootstrap-invalid');
  return {
    root,
    governanceVersion: String(manifest.governance_version ?? ''),
    fingerprints: { rule: shaFile(rulePath), manifest: shaFile(manifestPath), capability: shaFile(capabilityPath), bootstrap: shaFile(bootstrapPath) },
    manifest,
    capability,
  };
}

function compareEnvelopeFingerprint(label, envelopeSide, actual) {
  if (typeof envelopeSide !== 'object' || !envelopeSide) throw new Error(`${label}-fingerprint-missing`);
  if (!samePath(String(envelopeSide.workspace_root ?? ''), actual.root)) throw new Error(`${label}-workspace-mismatch`);
  if (String(envelopeSide.owner_id ?? '') && !samePath(String(envelopeSide.owner_id), actual.root)) throw new Error(`${label}-owner-mismatch`);
  if (String(envelopeSide.governance_version ?? '') !== actual.governanceVersion) throw new Error(`${label}-governance-version-mismatch`);
  const pairs = [
    ['rule_sha256', 'rule'],
    ['manifest_sha256', 'manifest'],
    ['capability_sha256', 'capability'],
    ['bootstrap_sha256', 'bootstrap'],
  ];
  for (const [field, key] of pairs) {
    if (String(envelopeSide[field] ?? '').toUpperCase() !== actual.fingerprints[key]) throw new Error(`${label}-${key}-fingerprint-mismatch`);
  }
}

function requireHex64(value, label) {
  if (typeof value !== 'string' || !/^[A-Fa-f0-9]{64}$/.test(value)) throw new Error(`${label}-invalid`);
  return value.toUpperCase();
}

function verifyVisibleEvent(event) {
  if (!event || typeof event !== 'object' || Array.isArray(event)) throw new Error('routed-event-object-required');
  for (const field of ['event_id', 'stream_digest', 'session_digest', 'routing_revision', 'provider', 'occurred_at', 'timestamp_quality', 'actor', 'channel', 'speaker', 'content', 'content_sha256', 'previous_cursor', 'source_cursor', 'source_fingerprint']) {
    if (!(field in event)) throw new Error(`routed-event-field-missing:${field}`);
  }
  const eventId = requireHex64(event.event_id, 'event-id');
  const streamDigest = requireHex64(event.stream_digest, 'stream-digest');
  const sessionDigest = requireHex64(event.session_digest, 'session-digest');
  if (!Number.isInteger(event.routing_revision) || event.routing_revision < 0) throw new Error('routing-revision-invalid');
  if (event.provider !== PLATFORM) throw new Error('provider-not-chatgpt-remote');

  if (!['user', 'assistant'].includes(event.actor) || !VISIBLE_CHANNELS.has(event.channel)) throw new Error('visible-event-invalid');
  if ((event.actor === 'user' && event.channel !== 'user') || (event.actor === 'assistant' && event.channel === 'user')) throw new Error('actor-channel-mismatch');
  if (!EXACT_TIME_QUALITY.has(event.timestamp_quality)) throw new Error('timestamp-quality-not-exact');
  const time = toKstParts(event.occurred_at);
  if (typeof event.speaker !== 'string' || !event.speaker) throw new Error('speaker-required');
  const content = redactSecrets(event.content);
  if (!content) throw new Error('content-empty');
  const contentHash = sha256(content);
  if (contentHash !== requireHex64(event.content_sha256, 'content-sha256')) throw new Error('content-sha256-mismatch');
  if (event.previous_cursor !== null && (typeof event.previous_cursor !== 'string' || !event.previous_cursor)) throw new Error('previous-cursor-invalid');
  if (typeof event.source_cursor !== 'string' || !event.source_cursor || event.source_cursor === event.previous_cursor) throw new Error('source-cursor-invalid');
  if (typeof event.source_fingerprint !== 'string' || !event.source_fingerprint) throw new Error('source-fingerprint-invalid');
  return {
    provider: PLATFORM,
    threadId: streamDigest,
    sourceEventId: eventId,
    sourceOrdinal: event.routing_revision,
    occurredAt: event.occurred_at,
    time,
    actor: event.actor,
    channel: event.channel,
    speaker: event.speaker,
    content,
    contentHash,
    eventId,
    destination: 'main',
    parentThreadId: '',
    agentId: '',
    agentName: '',
    taskName: '',
    routed: { sessionDigest, routingRevision: event.routing_revision, streamDigest, sourceFingerprint: event.source_fingerprint },
  };
}

export function verifyRoutedEnvelope(envelope, workspaceRoot) {
  if (!envelope || typeof envelope !== 'object' || Array.isArray(envelope)) throw new Error('routed-envelope-object-required');
  if (envelope.schema_version !== 1 || envelope.schema !== ENVELOPE_SCHEMA) throw new Error('routed-envelope-schema-mismatch');
  const envelopeId = requireHex64(envelope.envelope_id, 'envelope-id');
  const unsigned = structuredClone(envelope);
  delete unsigned.envelope_id;
  if (shaJson(unsigned) !== envelopeId) throw new Error('routed-envelope-hash-mismatch');
  const target = fingerprintWorkspace(workspaceRoot, PLATFORM);
  if (envelope.target?.kind !== 'governed-workspace') throw new Error('target-kind-invalid');
  compareEnvelopeFingerprint('target', envelope.target, target);
  const routedCapability = target.capability?.conversation_export?.routed_ingest;
  const exportCapability = target.capability?.conversation_export;
  if (exportCapability?.status !== 'routed-ingest-supported' || exportCapability?.automatic_project_recording !== false || exportCapability?.agent_mediated_routed_ingest !== true) throw new Error('target-routed-ingest-not-enabled');
  if (routedCapability?.authority !== 'general-dispatcher' || routedCapability?.transport !== 'stdin-json' || routedCapability?.envelope_schema !== ENVELOPE_SCHEMA || routedCapability?.command !== 'ingest-routed') throw new Error('target-routed-ingest-contract-mismatch');
  const authorityRoot = routedCapability?.authority_workspace;
  if (typeof authorityRoot !== 'string' || !path.isAbsolute(authorityRoot)) throw new Error('authority-workspace-not-declared');
  if (envelope.authority?.kind !== 'general-dispatcher' || !samePath(String(envelope.authority?.workspace_root ?? ''), authorityRoot)) throw new Error('authority-workspace-mismatch');
  const authority = fingerprintWorkspace(authorityRoot, PLATFORM);
  compareEnvelopeFingerprint('authority', envelope.authority, authority);
  const authorityRecording = authority.capability?.conversation_recording;
  if (authorityRecording?.routed_delivery !== 'tooling/routed-conversation-delivery.mjs' || authorityRecording?.governed_target_delivery !== 'capability-declared-only' || authorityRecording?.foreign_chat_path_guessing !== 'forbidden') throw new Error('authority-routed-delivery-capability-mismatch');
  const event = verifyVisibleEvent(envelope.event);
  return { target, authority, event };
}

function routedMetadataMatches(receipt, event) {
  if (!receipt?.routed) return true;
  return receipt.routed.sessionDigest === event.routed.sessionDigest
    && receipt.routed.routingRevision === event.routed.routingRevision
    && receipt.routed.streamDigest === event.routed.streamDigest
    && receipt.routed.sourceFingerprint === event.routed.sourceFingerprint;
}

async function verifyExistingMarker(chatRoot, event) {
  const targetPath = path.join(chatRoot, event.time.year, event.time.month, `${event.time.day}.md`);
  let markdown = '';
  try {
    markdown = await fs.promises.readFile(targetPath, 'utf8');
  } catch (error) {
    if (error.code === 'ENOENT') return { exists: false };
    throw error;
  }
  const marker = `<!-- conversation-event: ${event.eventId} -->`;
  const normalized = normalizeNewlines(markdown);
  if (!normalized.includes(marker)) return { exists: false };
  const expectedBlock = renderEventBlock(event).replace(/\n+$/, '');
  if (!normalized.includes(expectedBlock)) throw new Error('existing-provenance-content-conflict');
  return { exists: true, targetPath };
}

export async function ingestRoutedEnvelope(envelope, options = {}) {
  const workspaceRoot = canonicalPath(options.workspaceRoot ?? process.cwd());
  const chatRoot = path.resolve(options.chatRoot ?? path.join(workspaceRoot, 'Chat'));
  if (!inside(workspaceRoot, chatRoot) && options.allowTestRoots !== true) throw new Error('routed-chat-root-outside-workspace');
  const verified = verifyRoutedEnvelope(envelope, workspaceRoot);
  const event = verified.event;
  const stateRoot = path.join(chatRoot, '.state');
  const statePath = path.join(stateRoot, 'conversation-recorder.json');
  const writerLockPath = path.join(stateRoot, 'recorder.lock');
  return withWriterLock(writerLockPath, async () => {
    const state = await readState(statePath);
    const previousReceipt = state.receipts[event.eventId] ?? null;
    if (previousReceipt && previousReceipt.contentHash !== event.contentHash) throw new Error('routed-event-content-conflict');
    if (previousReceipt && !routedMetadataMatches(previousReceipt, event)) throw new Error('routed-event-metadata-conflict');
    const markerBefore = previousReceipt ? { exists: false } : await verifyExistingMarker(chatRoot, event);
    const projection = await projectEvents({ workspaceRoot, chatRoot, state, events: [event], dryRun: false, trustReceipts: true });
    const receipt = state.receipts[event.eventId];
    if (!receipt || receipt.contentHash !== event.contentHash) throw new Error('routed-receipt-not-committed');
    receipt.routed = structuredClone(event.routed);

    const recovered = !previousReceipt && markerBefore.exists && projection.existing === 1;
    const recorded = projection.written === 1;
    const existing = Boolean(previousReceipt) && projection.existing === 1;
    if (!recorded && !recovered && !existing) throw new Error('routed-projection-unexpected-result');
    if (recorded || recovered || !previousReceipt?.routed) await writeState(statePath, state);
    return {
      decision: recorded ? 'recorded' : recovered ? 'recovered' : 'existing',
      event_id: event.eventId,
      routing_revision: event.routed.routingRevision,
      target_owner: workspaceRoot,
    };
  }, { waitMs: 5000 });
}
