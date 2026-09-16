// [역할] 동기화 검사기와 KO guard가 동일한 주석 경계·marker 문법을 사용하게 한다.
// [의존성 관계] Node 표준 라이브러리만 사용한다. 범용 언어 AST 대체물이 아니다.
// [변경 시 영향도] 판별이 확실한 독립 주석/docstring만 추적하고 실행 문자열은 마스킹하지 않는다.
const idLine = /^\[MINI-COMMENT: ([A-Z0-9][A-Z0-9_.-]*)\]$/;
const enLine = /^\[EN rev\.(\d+)\]$/;
const koLine = /^\[KO rev\.(\d+)\]$/;

function quotedEnd(text, start, quote) {
  for (let i = start + quote.length; i < text.length; i++) {
    if (text[i] === '\\') { i++; continue; }
    if (text.startsWith(quote, i)) return i + quote.length;
  }
  if (quote.length === 3 && text.slice(start).includes('[MINI-COMMENT')) throw new Error('FORMAT-ERROR: unterminated tracked Python docstring');
  return text.length;
}
// JS template 전체는 실행 문자열로 제외한다. 보간식 안의 중첩 문자열/주석도 건너뛴다.
function templateEnd(text, start) {
  for (let i = start + 1; i < text.length; i++) {
    if (text[i] === '\\') { i++; continue; }
    if (text[i] === '`') return i + 1;
    if (text.startsWith('${', i)) {
      let depth = 1; i += 2;
      for (; i < text.length && depth; i++) {
        if (text[i] === '`') i = templateEnd(text, i) - 1;
        else if ('\'"'.includes(text[i])) i = quotedEnd(text, i, text[i]) - 1;
        else if (text.startsWith('//', i)) i = text.indexOf('\n', i) < 0 ? text.length : text.indexOf('\n', i);
        else if (text.startsWith('/*', i)) i = text.indexOf('*/', i + 2) < 0 ? text.length : text.indexOf('*/', i + 2) + 1;
        else if (text[i] === '{') depth++;
        else if (text[i] === '}') depth--;
        else if (text[i] === '\\') i++;
      }
      i--;
    }
  }
  return text.length;
}
function standaloneDocstring(text, start, end) {
  const lineStart = text.lastIndexOf('\n', start - 1) + 1;
  if (!/^[ \t]*$/.test(text.slice(lineStart, start))) return false;
  if (!/^[ \t]*(?:#.*)?$/.test(text.slice(end, text.indexOf('\n', end) < 0 ? text.length : text.indexOf('\n', end)))) return false;
  const preceding = text.slice(0, lineStart).split('\n').filter(line => line.trim() && !/^\s*#/.test(line));
  if (!preceding.length) return true;
  const previous = preceding.at(-1);
  // 복잡한 여러 행 선언은 추측하지 않고 # 주석 또는 구현 검토로 넘긴다.
  return /^\s*(?:(?:async\s+)?def\s+\w+\s*\(.*\).*|class\s+\w+[^:]*)\s*:\s*(?:#.*)?$/.test(previous)
    && text.slice(lineStart, start).length > previous.match(/^\s*/)[0].length;
}

export function rawBlocks(text, extension) {
  const blocks = [];
  const add = (start, end) => blocks.push({ raw: text.slice(start, end), start, end });
  const py = extension === '.py';
  const js = ['.js', '.mjs'].includes(extension);
  if (!py && !js && extension !== '.html') return blocks;
  for (let i = 0; i < text.length;) {
    const startOfLine = text.lastIndexOf('\n', i - 1) + 1;
    const standalone = /^[ \t]*$/.test(text.slice(startOfLine, i));
    if (extension === '.html') {
      // Jinja 표현식/제어문 안의 문자열은 HTML 주석이 아니다.
      if (/^\{[{%#]/.test(text.slice(i, i + 2))) {
        const closeToken = { '{{': '}}', '{%': '%}', '{#': '#}' }[text.slice(i, i + 2)];
        let end = i + 2;
        for (; end < text.length && !text.startsWith(closeToken, end); end++) if ('\'"'.includes(text[end])) end = quotedEnd(text, end, text[end]) - 1;
        i = Math.min(text.length, end + 2); continue;
      }
      if (text.startsWith('<!--', i)) {
        const close = text.indexOf('-->', i + 4);
        if (close < 0) throw new Error('FORMAT-ERROR: unterminated HTML comment');
        add(i, close + 3); i = close + 3; continue;
      }
      // 속성과 script/style/textarea 안의 주석 모양 문자열은 대상에서 제외한다.
      if (text[i] === '<') {
        const rawTag = text.slice(i).match(/^<(script|style|textarea|title)\b/i)?.[1];
        let end = i + 1;
        for (; end < text.length && text[end] !== '>'; end++) if ('\'"'.includes(text[end])) end = quotedEnd(text, end, text[end]) - 1;
        i = end + 1;
        if (rawTag) { const close = new RegExp(`</${rawTag}\\s*>`, 'ig'); close.lastIndex = i; i = close.exec(text) ? close.lastIndex : text.length; }
        continue;
      }
      i++; continue;
    }
    const linePrefix = py ? '#' : '//';
    if (text.startsWith(linePrefix, i)) {
      let end = text.indexOf('\n', i); end = end < 0 ? text.length : end + 1;
      if (standalone) {
        while (end < text.length && new RegExp(`^[ \\t]*${py ? '#' : '//'}.*(?:\\n|$)`).test(text.slice(end))) {
          const next = text.indexOf('\n', end); end = next < 0 ? text.length : next + 1;
        }
        add(startOfLine, end);
      }
      i = end; continue;
    }
    if (js && text.startsWith('/*', i)) {
      const close = text.indexOf('*/', i + 2);
      if (close < 0) throw new Error('FORMAT-ERROR: unterminated JS comment');
      if (standalone) add(i, close + 2);
      i = close + 2; continue;
    }
    if (js && text[i] === '`') { i = templateEnd(text, i); continue; }
    if ('\'"'.includes(text[i])) {
      const triple = py && text.startsWith(text[i].repeat(3), i);
      const quote = text[i].repeat(triple ? 3 : 1);
      const end = quotedEnd(text, i, quote);
      if (triple && standaloneDocstring(text, i, end)) add(i, end);
      i = end; continue;
    }
    i++;
  }
  return blocks;
}
export function cleanBody(raw, extension) {
  let body = raw.replace(/\r\n/g, '\n');
  if (extension === '.py' && /^(?:"""|''')/.test(body.trimStart())) return body.trim().slice(3, -3).split('\n').map(line => line.trim()).join('\n').trim();
  if (extension === '.py') return body.split('\n').map(line => line.replace(/^\s*# ?/, '')).join('\n').trim();
  if (extension === '.html') return body.trim().slice(4, -3).trim();
  if (body.trimStart().startsWith('/*')) body = body.trim().replace(/^\/\*+/, '').slice(0, -2).split('\n').map(line => line.replace(/^\s*\* ?/, '').trimEnd()).join('\n');
  else body = body.split('\n').map(line => line.replace(/^\s*\/\/ ?/, '')).join('\n');
  return body.trim();
}
export function trackedParts(raw, extension) {
  const body = cleanBody(raw, extension);
  if (!body.includes('[MINI-COMMENT')) return null;
  const lines = body.split('\n').map(line => line.trim());
  const markers = lines.map((line, index) => ({ line, index })).filter(({ line }) => /^\[(?:MINI-COMMENT|EN rev|KO rev)/.test(line));
  if (markers.length < 2 || markers.length > 3 || !idLine.test(markers[0].line) || !enLine.test(markers[1].line)
      || (markers[2] && !koLine.test(markers[2].line)) || markers[0].index !== 0) throw new Error('FORMAT-ERROR: expected one ID, EN, optional KO in order');
  const enRev = Number(markers[1].line.match(enLine)[1]);
  const koRev = markers[2] ? Number(markers[2].line.match(koLine)[1]) : null;
  if (!Number.isSafeInteger(enRev) || enRev < 1 || (koRev !== null && (!Number.isSafeInteger(koRev) || koRev < 0))) throw new Error('FORMAT-ERROR: invalid revision');
  return { id: markers[0].line.match(idLine)[1], enRev, koRev,
    enText: lines.slice(markers[1].index + 1, markers[2]?.index).join('\n').trim(),
    koText: markers[2] ? lines.slice(markers[2].index + 1).join('\n').trim() : '' };
}
export function maskKo(text, extension) {
  const normalized = text.replace(/\r\n/g, '\n');
  let result = '', cursor = 0;
  for (const block of rawBlocks(normalized, extension)) {
    const part = trackedParts(block.raw, extension);
    if (!part) continue;
    // Jinja는 HTML 주석 안에서도 실행되므로 번역 범위에 넣지 않는다.
    if (extension === '.html' && /\{[{%#]/.test(block.raw)) throw new Error('template expression in tracked HTML comment');
    let endToken = '';
    if (extension === '.html') endToken = '-->';
    else if (block.raw.startsWith('/*')) endToken = '*/';
    else if (/^(?:"""|''')/.test(block.raw)) endToken = block.raw.slice(0, 3);
    const koOffset = block.raw.search(/^.*\[KO rev\.\d+\].*$/m);
    const end = endToken ? block.raw.lastIndexOf(endToken) : block.raw.length;
    // EN 앞부분은 보존한다. 최초 KO 추가도 동일한 비교 표현으로 정규화한다.
    const prefix = block.raw.slice(0, koOffset < 0 ? end : koOffset).trimEnd();
    result += normalized.slice(cursor, block.start) + prefix + '\n[KO-MASKED]\n' + endToken;
    cursor = block.end;
  }
  return result + normalized.slice(cursor);
}
