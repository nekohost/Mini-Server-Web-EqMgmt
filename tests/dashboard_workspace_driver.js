/* [Role] Exercises real equipment controls and dashboard charts on isolated, read-only fixture data.
 * [Dependencies] Linux browser fixture, actual templates and their scripts. [Impact] Records layout, filtered results and stale-response protection; never submits a business form. */
(() => {
    const view = '__FIXTURE_VIEW__', theme = new URLSearchParams(location.search).get('theme'), skin = theme === 'dark' ? 'edge' : 'standard';
    const $ = id => document.getElementById(id);
    const user = {UserId:1, NickName:'화면 검증',Role:'user'}, cats=[{CategoryId:1,Name:'미니 PC',DisplayName:'미니 PC'}];
    const mans=['제조사 A','제조사 B','제조사 C','제조사 D'].map((name,i)=>({ManufacturerId:i+1,Name:name,DisplayName:name}));
    const item={EquipmentId:101,UserId:1,OwnerNickName:'화면 검증',Name:'사무실 미니 PC',ModelName:'Mini',FullModelName:'Mini',OfficialModelName:'Mini',Status:'ACTIVE',StatusLabel:'정상',PurchaseDate:'2026-01-05',Revision:1,CategoryId:1,ManufacturerId:1,LineupNodeId:1,OptionId:1};
    const tree={categories:[{id:1,name:'미니 PC'}],manufacturers:[{id:1,name:'제조사 A'}],nodes:[{id:1,parent_id:null,category_id:1,manufacturer_id:1,name:'Mini',status:'APPROVED'}],options:[{id:1,lineup_node_id:1,option_name:'기본',status:'APPROVED'}]};
    const info={my_equipments:2,total_equipments:3,categories:[{category:'미니 PC',count:2},{category:'<img src=x onerror=alert(1)>',count:1}],manufacturers:[{manufacturer:'제조사 A',count:3}]};
    const matched={status_distribution:[{status:'정상',count:2},{status:'수리',count:1}],equipment_list:[item,{...item,Name:'연구실 장비'},{...item,Name:'수리 중 장비',Status:'수리'}]};
    const res=(v,status=200)=>new Response(JSON.stringify(v),{status,headers:{'Content-Type':'application/json'}});
    const reads=[], unexpected=[], errors=[]; let releaseSlow;
    addEventListener('error',e=>{if(e.error)errors.push(e.message);});
    window.fetch=async(path,opts={})=>{
        const url=new URL(path,location.href), route=url.pathname;
        if((opts.method || 'GET')!=='GET'){unexpected.push([opts.method,route]);return res({},405);}
        reads.push(url.pathname+url.search);
        if(route==='/api/check_session')return res({valid:true});
        if(route==='/api/user_settings')return res({success:true,settings:{theme,layout_skin:skin}});
        if(route==='/api/me')return res(user);
        if(route==='/api/dashboard/master_options')return res({success:true,categories:cats,manufacturers:mans});
        if(route==='/api/dashboard/stats'){
            const m=url.searchParams.get('manufacturer_id');
            if(m==='4')await new Promise(resolve=>{releaseSlow=resolve;});
            if(m==='3')return res({},503);
            return res({success:true,data:{...info,combined_stats:!m?null:m==='2'?{status_distribution:[],equipment_list:[]}:matched}});
        }
        if(route==='/api/master_data')return res({categories:cats,manufacturers:mans});
        if(route==='/api/lineup_tree_all')return res(tree);
        if(route==='/api/equipment'){
            const draft=url.searchParams.has('is_draft');
            return res({items:draft?[]:[item],page:1,pages:1,total:draft?0:1});
        }
        if(route==='/api/equipment/101/lifecycle')return res({equipment:{name:item.Name,status:'ACTIVE',option_id:1},states:{ACTIVE:'정상'},writable:true,transitions:[],history:[]});
        if(route==='/api/equipment/101/files')return res({files:[]});
        unexpected.push(['GET',route]);return res({},404);
    };
    document.addEventListener('DOMContentLoaded',async()=>{
        const result=document.createElement('pre');result.hidden=true;result.id='browser-test-result';document.body.append(result);
        const checks=[], geometry={};
        const wait=async(fn,label)=>{for(let i=0;i<400;i++){if(fn())return;await new Promise(r=>setTimeout(r,15));}throw Error(label);};
        const ok=(v,name)=>{if(!v)throw Error(name);checks.push(name);};
        const frame=()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
        const send=payload=>{result.textContent=JSON.stringify(payload);parent.postMessage({fixtureResult:result.textContent},location.origin);};
        const title=()=>document.querySelector('.app-nav-title').textContent.trim().replace(/\s+/g,' ');
        const gap=el=>Math.round(el.getBoundingClientRect().top-document.querySelector('nav.app-nav-polish').getBoundingClientRect().bottom);
        try{
            await wait(()=>document.documentElement.dataset.layoutSkin===skin,'layout skin');
            if(view==='dashboard'){
                const form=$('combinedSearchForm'),cat=$('filterCategory'),man=$('filterManufacturer');
                await wait(()=>man.options.length===5 && $('categoryTableBody').rows.length===2,'upper distributions');
                const select=id=>{man.value=id;man.dispatchEvent(new Event('change',{bubbles:true}));};
                const search=()=>form.requestSubmit();
                const done=()=>wait(()=>form.getAttribute('aria-busy')!=='true','search response');
                const draws=id=>{const c=$(id),a=c.getContext('2d').getImageData(0,0,c.width,c.height).data;return a.some((b,i)=>i%4===3&&b>0);};
                ok(!form.checkValidity() && $('combinedResultArea').hidden,'both filters are required');
                ok(!$('categoryTableBody').querySelector('img')&&$('categoryTableBody').textContent.includes('<img'),'labels are text');
                cat.value='1';select('1');search();await done();await frame();
                ok($('combinedStatusBody').rows.length===2 && $('combinedStatusBody').textContent.includes('정상2대') && $('combinedStatusBody').textContent.includes('수리1대'),'filtered status 2+1');
                ok(['categoryChart','manufacturerChart','combinedChart'].every(draws),'three actual painted doughnuts');
                ok(!$('combinedDetails').open && $('combinedCount').textContent==='3','list starts folded and total matches');
                $('combinedDetails').querySelector('summary').click();ok($('combinedDetails').open && $('combinedTableBody').rows.length===3 && $('combinedTableBody').textContent.includes('제조사 A / Mini'),'equipment drill-down retained');
                const n=reads.length;document.documentElement.classList.toggle('dark');await frame();document.documentElement.classList.toggle('dark');await frame();
                ok(reads.length===n && !$('combinedResultArea').hidden,'theme preserves selection without GET');
                select('2');ok($('combinedResultArea').hidden && !$('combinedDetails').open,'changing a filter clears old results');
                search();await done();ok($('combinedResultArea').hidden && $('combinedNotice').textContent.includes('일치하는 장비가 없습니다'),'empty result');
                select('3');search();await done();ok($('combinedResultArea').hidden && $('combinedNotice').textContent.includes('다시 검색'),'failure is retryable');
                select('4');search();await wait(()=>releaseSlow,'delayed request started');select('2');search();await done();releaseSlow();await frame();
                ok($('combinedResultArea').hidden && $('combinedNotice').textContent.includes('제조사 B'),'late response cannot replace latest selection');
                select('1');search();await done();await frame();
                const c=$('combinedChart').getBoundingClientRect(), t=$('combinedStatusBody').closest('table').getBoundingClientRect();
                ok(innerWidth>=768?c.right<=t.left+1:c.bottom<=t.top+1,'responsive chart and count-table geometry');
                $('combinedSearchForm').closest('div.rounded-xl').scrollIntoView();window.scrollBy(0,-document.querySelector('nav.app-nav-polish').offsetHeight);
                geometry.chartWidth=Math.round(c.width);
            }else{
                await wait(()=>$('roadmap-page')?.textContent.includes('1건'),'equipment loaded');
                geometry.firstControlGap=gap(document.querySelector('.equipment-workspace'));
                if(view==='public'){
                    ok(!document.querySelector('main h1') && title()==='공개 장비' && !!$('includeMineCheckbox') && !$('btnToggleDrafts'),'public title is only in navigation and filters remain scoped');
                }else{
                    ok(!document.querySelector('main h1') && title()==='나의 장비','single page title');
                    ok(geometry.firstControlGap>=0 && geometry.firstControlGap<=20,'owned controls start alongside nav');
                    $('btnToggleDrafts').click();await wait(()=>$('equipmentTableBody').textContent.includes('임시저장된 장비가 없습니다.'),'draft rows');
                    ok(title()==='나의 임시저장 목록' && document.title.startsWith(title()) && $('btnOpenAddModal').classList.contains('hidden') && reads.some(x=>x.includes('is_draft=1')),'actual draft toggle updates scope, title and controls');
                    if(view!=='draft'){
                        $('btnToggleDrafts').click();await wait(()=>$('equipmentTableBody').textContent.includes(item.Name),'owned rows return');
                        ok(title()==='나의 장비' && !$('btnOpenAddModal').classList.contains('hidden'),'actual draft return');
                        $('roadmap-search-toggle').click();ok(!$('roadmap-advanced').hidden,'advanced search opens');$('roadmap-search-toggle').click();
                        $('roadmap-csv-toggle').click();$('roadmap-import').click();ok($('roadmap-csv-dialog').open,'CSV dialog opens');$('roadmap-csv-dialog').querySelector('[data-roadmap-close]').click();
                        $('roadmap-csv-toggle').click();
                        await window.Roadmap.openDetails(101);ok($('roadmap-detail').open && $('roadmap-detail-title').textContent.includes(item.Name),'item detail keeps its name');$('roadmap-detail').querySelector('[data-roadmap-close]').click();
                        await openModal();ok(!$('equipmentModal').classList.contains('hidden') && $('modalTitle').textContent.includes('등록'),'registration opens');
                        const toolbar=document.querySelector('[data-catalog-kind]');toolbar.click();
                        await wait(()=>document.querySelector('.catalog-request-dialog')?.open,'catalog request opens');
                        ok(!!document.querySelector('.catalog-request-dialog h2')?.textContent,'nested catalog application has a heading');document.querySelector('.catalog-request-dialog').close();closeModal();
                        await openModal(101);ok($('Name').value===item.Name && !$('equipmentModal').classList.contains('hidden') && $('modalTitle').textContent.includes('수정'),'edit keeps equipment identity');
                        const panel=$('equipmentModalPanel').getBoundingClientRect(),foot=$('equipmentModalFooter').getBoundingClientRect();
                        ok(panel.top>=0 && foot.bottom<=innerHeight+1,'editor footer fits the viewport');
                        if(view!=='edit')closeModal();
                    }
                }
            }
            await frame();ok(document.documentElement.scrollWidth<=innerWidth+1,'no horizontal page overflow');
            ok(unexpected.length===0 && errors.length===0,'only expected reads and no JS exceptions');
            send({status:'pass',view,width:innerWidth,height:innerHeight,theme,skin,checks,geometry});
        }catch(e){send({status:'fail',view,width:innerWidth,height:innerHeight,theme,skin,checks,geometry,error:String(e.stack||e),unexpected,errors});}
    });
})();
