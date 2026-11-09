'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { renderAnswer, mailStatus } = require('../static/js/equipment_ai.js');

test('renders literal mail text during streaming and history hydration', () => {
    const source = { mail_translation: 'en-ko' };
    const element = { style: {} };
    const text = '제목: 복구 기록\n\n[작업](/assistant?panel=csv-import)\n<img src=x>\n`cmd --read`';
    renderAnswer(element, text.slice(0, 8), source, { streaming: true });
    assert.equal(element.textContent, text.slice(0, 8));
    renderAnswer(element, text, source);
    assert.equal(element.textContent, text);
    assert.equal(element.style.whiteSpace, 'pre-wrap');
});

test('keeps interrupted mail visibly separate from a completed mail and ordinary chat', () => {
    const source = { mail_translation: 'ko-en' };
    assert.equal(mailStatus({ state: 'failed', source: {} }), '');
    for (const state of ['failed', 'cancelled', 'recovery_required', 'draining']) {
        assert.match(mailStatus({ state, source, error: '중단 사유' }), /번역 미완료 · 중단 사유/u);
    }
    assert.match(mailStatus({ state: 'running', source }), /생성 중/u);
    assert.equal(mailStatus({ state: 'done', source }), ' · 메일 번역');
});

// A mail renderer can set plain text and layout only; markup or DOM creation fails this fixture.
function mailElement() {
    return Object.seal({ textContent: '', style: Object.seal({ whiteSpace: '' }) });
}

test('removes only the bold subject label or its whole-line wrapper from a completed mail', () => {
    const body = '\r\n\r\n  Dear team,\r\n**Subject:** a quoted header\n\tDo **not** run `restore BR-41`.\r' +
        '[Open](/assistant?panel=csv-import) <img src=x>\n\nRegards,  \nA* Team\t\n';
    const cases = [
        ['**Subject:** Export 2*3, **draft**', 'Subject: Export 2*3, **draft**'],
        ['**Subject: Review *.log and GW-17**', 'Subject: Review *.log and GW-17'],
        [' \t\r\n  **제목:**\t상태 점검  ', ' \t\r\n  제목:\t상태 점검  '],
        ['**제목: 파일 `gw17-before.json` 및 명령 `restart GW-17`**\t ', '제목: 파일 `gw17-before.json` 및 명령 `restart GW-17`\t '],
        ['**sUbJeCt** :\tScope: R-71', 'sUbJeCt :\tScope: R-71'],
        ['**제목**：  *.csv', '제목：  *.csv'],
        ['**Subject: Check logs/**/*.json and ``echo `**` ``**', 'Subject: Check logs/**/*.json and ``echo `**` ``'],
        ['**Subject: Use `C:\\temp\\` and \\*\\* literally**', 'Subject: Use `C:\\temp\\` and \\*\\* literally'],
    ];
    for (const [header, expected] of cases) {
        const element = mailElement();
        renderAnswer(element, header + body, { mail_translation: 'en-ko' });
        assert.equal(element.textContent, expected + body, header);
        assert.equal(element.style.whiteSpace, 'pre-wrap');
    }
});

test('leaves literal, ambiguous, quoted, non-leading and incomplete headings untouched', () => {
    const inputs = [
        'Subject: **retain these stars**', '제목: *가* **나**', '**Subject: unterminated',
        '**Subject:**', '**제목: **', '**Subject: title **', '**Subject: ends in ***',
        '**Subject: first** and **second**', '**Subject: form \\**', '**Subject: `unclosed code**',
        '***Subject: three stars***', '*Subject:* one star', '**Subjective:** unrelated',
        '`**Subject:**` in a command', '> **Subject:** quoted', '```text\n**Subject:** sample\n```',
        '    **Subject:** indented code', '\n\t**제목: 들여쓴 코드**',
        'Hello,\r\n**Subject:** in the body', '**제목: across\r\nlines**', '서명\r**제목:** 과거 메일',
    ];
    for (const input of inputs) {
        const element = mailElement();
        renderAnswer(element, input, { mail_translation: 'ko-en' });
        assert.equal(element.textContent, input);
    }
});

test('preserves every stream prefix and partial record, including a closed-looking header', () => {
    const source = { mail_translation: 'ko-en' }, element = mailElement();
    const raw = '**Subject: Run `scan *.csv`**\r\n\r\n안녕하세요.\nSigned, A*';
    for (let end = 0; end <= raw.length; end++) {
        const prefix = raw.slice(0, end);
        renderAnswer(element, prefix, source, { streaming: true });
        assert.equal(element.textContent, prefix);
    }
    renderAnswer(element, raw, source, { streaming: false, complete: false });
    assert.equal(element.textContent, raw);
    renderAnswer(element, raw, source, { streaming: false, complete: true });
    assert.equal(element.textContent, 'Subject: Run `scan *.csv`\r\n\r\n안녕하세요.\nSigned, A*');
});

test('ordinary chat still creates its Markdown emphasis and code nodes', () => {
    const nodes = [];
    const doc = {
        createDocumentFragment: () => ({ append() {} }),
        createTextNode: text => ({ textContent: text }),
        createElement(tag) {
            const node = { tag, ownerDocument: doc, append() {} };
            nodes.push(node);
            return node;
        },
    };
    const element = { ownerDocument: doc, querySelectorAll: () => [], replaceChildren() {} };
    renderAnswer(element, '**Subject:** review `scan`', { provider_name: 'fixture' });
    assert.equal(nodes.find(node => node.tag === 'strong').textContent, 'Subject:');
    assert.equal(nodes.find(node => node.tag === 'code').textContent, 'scan');
});
