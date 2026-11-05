"""[MINI-COMMENT: ASSISTANT.COMPACT.MEASURE.FIXTURE]
[EN rev.3]
[Role] Measures the same synthetic initial chat before and after the compact layout merge.
[Dependencies] Existing synthetic transport setup and Linux chat browser fixture; no production model or database.
[Impact] Returns actual CSS-pixel geometry separately from functional regression counts; the legacy desktop comparison uses1425px after detecting the old harness's iframe shrink, while1440px is also measured exactly.
"""
from pathlib import Path

from assistant_ui_browser_fixture import run_ui_browser


def run_browser(project, assets):
    """[Role] Reuses transport setup while replacing the lifecycle test driver with read-only DOM measurements."""
    source = assets.get("tests/test_equipment_ai_ui.js")
    if source is None:
        path = Path(project) / "tests/test_equipment_ai_ui.js"
        if not path.is_file():
            path = Path(project) / "Staging/20261105-ai-ux-trash/tests/test_equipment_ai_ui.js"
        source = path.read_text(encoding="utf-8-sig")
    anchor = "document.addEventListener('DOMContentLoaded', async () => {"
    if source.count(anchor) != 1:
        raise ValueError("compact measurement requires one reviewed fixture initialization anchor")
    setup = source.split(anchor, 1)[0]
    driver = r"""
    document.addEventListener('DOMContentLoaded', async () => {
        const report = document.createElement('pre'); report.id = 'browser-test-result'; report.hidden = true; document.body.append(report);
        const $ = id => document.getElementById(id);
        const wait = async test => { for (let i=0; i<1200; i++) { if (test()) return; await sleep(10); } throw Error('measurement readiness timeout'); };
        const rect = element => {
            if (!element) return null;
            const r = element.getBoundingClientRect(), c = getComputedStyle(element);
            return {x:r.x,y:r.y,width:r.width,height:r.height,display:c.display,font_size:c.fontSize,line_height:c.lineHeight,padding:c.padding};
        };
        try {
            await wait(() => $('ai-title').textContent.includes('표와 휴지통') && !$('ai-model').disabled && document.querySelector('.ai-answer table'));
            await document.fonts.ready;
            for (const animation of document.body.getAnimations()) {
                if (Number.isFinite(animation.effect?.getComputedTiming().endTime)) { try { animation.finish(); } catch (_) {} }
            }
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
            const layout = {
                actual_viewport_width:innerWidth,
                fixture_state:'initial-Qwen-medium-stored-table',
                selected_model:$('ai-model').selectedOptions[0]?.textContent,
                level:$('ai-level').value,
                root:rect($('equipment-ai')), workspace:rect(document.querySelector('.ai-workspace')),
                header:rect(document.querySelector('.ai-header')),
                model_controls:rect(document.querySelector('.ai-model-control')),
                model:rect($('ai-model')), refresh:rect($('ai-model-refresh')), reasoning:rect($('ai-level')),
                scroll:rect($('ai-scroll')), composer:rect($('ai-form')),
                composer_actions:rect(document.querySelector('.ai-composer-actions')),
                page_scroll_width:document.documentElement.scrollWidth,
                status_hidden:$('ai-model-status').hidden,
            };
            report.textContent=JSON.stringify({status:'pass',kind:'layout-measurement',checks:[],width:innerWidth,theme,layout});
        } catch(error) {
            report.textContent=JSON.stringify({status:'fail',kind:'layout-measurement',checks:[],width:innerWidth,theme,error:error.message});
        }
        if (window.parent!==window) window.parent.postMessage({fixtureResult:report.textContent},location.origin);
        window.dispatchEvent(new Event('pagehide'));
    });
})();
"""
    return run_ui_browser(project, assets, setup + driver, sizes=(430, 1425, 1440), themes=("light",))
