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
    const reads=[], unexpected=[], errors=[]; let releaseSlow; let failEquipment=false;
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
            if(failEquipment){failEquipment=false;return res({error:'합성 조회 오류'},503);}
            if(url.searchParams.get('keyword')==='__empty__')return res({items:[],page:1,pages:1,total:0});
            return res({items:draft?[]:[item],page:Number(url.searchParams.get('page')||1),pages:draft?1:3,total:draft?0:51});
        }
        if(route==='/api/equipment/101/lifecycle')return res({equipment:{name:item.Name,status:'ACTIVE',option_id:1},states:{ACTIVE:'정상'},writable:true,transitions:[],history:[]});
        if(route==='/api/equipment/101/files')return res({files:[]});
        unexpected.push(['GET',route]);return res({},404);
    };
    const isBaseline=__BASELINE__;
    document.addEventListener('DOMContentLoaded',async()=>{
        const result=document.createElement('pre');result.hidden=true;result.id='browser-test-result';document.body.append(result);
        const checks=[],geometry={},resize=[];
        const wait=async(fn,label)=>{for(let i=0;i<400;i++){if(fn())return;await new Promise(r=>setTimeout(r,15));}throw Error(label);};
        const ok=(condition,label)=>{if(!condition)throw Error(label);checks.push(label);};
        const frame=()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
        const equipmentReads=()=>reads.filter(u=>u.startsWith('/api/equipment?'));
        const controls=()=>[...document.querySelectorAll('.equipment-toolbar button,.equipment-toolbar input,.equipment-toolbar #roadmap-page')].filter(el=>el.getBoundingClientRect().height>0);
        const box=el=>{const b=el.getBoundingClientRect(),s=getComputedStyle(el);return {name:el.id||el.textContent.trim(),x:b.x,y:b.y,width:b.width,height:b.height,right:b.right,bottom:b.bottom,font:s.fontSize};};
        const measure=()=>{const root=document.querySelector('.equipment-workspace'),bar=document.querySelector('.equipment-toolbar')||root;
            const list=isBaseline?[...root.querySelectorAll('.equipment-page-actions button,.roadmap-search-basic input,.roadmap-search-basic button,[aria-label="장비 목록 페이지"] > *')].filter(el=>el.getBoundingClientRect().height>0):controls();
            const rectangles=list.map(box), bands=[];
            // Legacy controls have different heights/padding; overlapping vertical intervals count as one visual row.
            for(const r of [...rectangles].sort((a,b)=>a.y-b.y)){
                const band=bands.at(-1);
                if(band&&r.y<band.bottom-1){band.top=Math.max(band.top,r.y);band.bottom=Math.min(band.bottom,r.bottom);}
                else bands.push({top:r.y,bottom:r.bottom});
            }
            return {width:innerWidth,toolbar:box(bar),workspace:box(root),controls:rectangles,rows:bands.length,overflow:document.documentElement.scrollWidth-innerWidth,firstWorkGap:Math.round(root.getBoundingClientRect().top-document.querySelector('nav.app-nav-polish').getBoundingClientRect().bottom)};
        };
        const fit=label=>{const m=measure();ok(m.overflow<=1,label+': no page overflow');ok(m.controls.every(r=>r.width>0&&r.x>=m.toolbar.x-1&&r.right<=m.toolbar.right+1),label+': controls stay inside toolbar');return m;};
        const fresh=async(action,label)=>{const n=equipmentReads().length;action();await wait(()=>equipmentReads().length>n,label);await frame();};
        try{
            await wait(()=>document.documentElement.dataset.layoutSkin===skin&&$('roadmap-page').textContent.includes('51건'),'initial rows/theme');
            await frame();
            geometry.initial=measure();
            if(!isBaseline){
                const form=$('roadmap-filter'),fields=['keyword','category_id','manufacturer_id','status','purchase_from','purchase_to','due','sort','per_page'];
                ok(fields.every(n=>form.elements[n]?.form===form),'all search inputs retain one form owner');
                ok(!form.querySelector('form')&&form.querySelectorAll('button[type="submit"]').length===1,'no nested form or accidental submit action');
                ok(form.querySelector('button:default')===form.querySelector('button[type="submit"]'),'native implicit submission still targets search');
                ok([...form.querySelectorAll('button')].every(b=>['button','submit','reset'].includes(b.type)),'explicit native button types');
                const m=fit('initial');
                ok(m.controls.every(r=>Math.abs(r.height-44)<1)&&new Set(m.controls.map(r=>r.font)).size===1,'input/actions/page counter share 44px height and font');
                ok(innerWidth<1024||m.rows===1,'roomy desktop uses exactly one toolbar row');
                if(innerWidth>=360&&innerWidth<=430)ok(m.rows<=3,'phone controls use at most three readable rows');
                ok($('roadmap-prev').disabled&&!$('roadmap-next').disabled,'initial page boundaries retained');
                await fresh(()=>$('roadmap-next').click(),'next page');ok($('roadmap-page').textContent.includes('2/3')&&new URL(equipmentReads().at(-1),location.href).searchParams.get('page')==='2','next page sends page 2');
                await fresh(()=>$('roadmap-prev').click(),'previous page');ok($('roadmap-page').textContent.includes('1/3'),'previous page returns to page 1');
                const n=equipmentReads().length;$('roadmap-csv-toggle').click();ok(!$('roadmap-csv-actions').hidden&&equipmentReads().length===n,'CSV disclosure never submits or fetches');
                $('roadmap-import').click();ok($('roadmap-csv-dialog').open,'CSV dialog still opens');$('roadmap-csv-dialog').querySelector('[data-roadmap-close]').click();$('roadmap-csv-toggle').click();
                await fresh(()=>$('roadmap-search-toggle').click(),'advanced search opens');
                ok(!$('roadmap-advanced').hidden&&!$('roadmap-advanced').disabled,'advanced fields enable only while open');
                const bar=document.querySelector('.equipment-toolbar').getBoundingClientRect(),advanced=$('roadmap-advanced').getBoundingClientRect();
                ok(advanced.top>=bar.bottom-1&&Math.abs(advanced.width-bar.width)<1,'advanced panel uses full width below the bar');
                form.elements.status.value='REPAIR';await fresh(()=>form.requestSubmit(),'advanced search submits');ok(new URL(equipmentReads().at(-1),location.href).searchParams.get('status')==='REPAIR','expanded filter values are submitted');
                await fresh(()=>$('roadmap-search-toggle').click(),'simple search returns');ok($('roadmap-advanced').disabled&&!new URL(equipmentReads().at(-1),location.href).searchParams.has('status'),'closed advanced fields do not filter silently');
                form.elements.keyword.value='검증 장비';
                await fresh(()=>form.requestSubmit(),'keyword search');ok(new URL(equipmentReads().at(-1),location.href).searchParams.get('keyword')==='검증 장비','keyword search uses the existing scope');
                if(view!=='public'){
                    await fresh(()=>$('btnToggleDrafts').click(),'draft mode');ok($('btnOpenAddModal').getBoundingClientRect().height===0&&document.querySelector('.app-nav-title').textContent.includes('임시저장'),'draft hides registration and keeps its title');
                    await fresh(()=>$('btnToggleDrafts').click(),'owned mode returns');
                    await openModal();ok(!$('equipmentModal').classList.contains('hidden')&&$('modalTitle').textContent.includes('등록'),'registration opens without searching');closeModal();
                }
                if(innerWidth===1440&&view==='my'){
                    const key=form.elements.keyword.value,status=form.elements.status.value,selected=$('includeMineCheckbox')?.checked;
                    const n=equipmentReads().length;
                    for(const width of [1280,1024,820,640,412,384,320,1440]){
                        parent.document.getElementById('fixture-viewport').style.width=width+'px';
                        await wait(()=>innerWidth===width,'live width '+width);await frame();
                        const r=fit('resize '+width);resize.push(r);
                        ok(width<1024||r.rows===1,'resize '+width+': sufficient width is one row');
                        ok(form.elements.keyword.value===key&&form.elements.status.value===status&&$('includeMineCheckbox')?.checked===selected,'resize '+width+': filters and scope remain');
                    }
                    ok(equipmentReads().length===n,'resizing never submits, reloads or fetches equipment');
                }
                if(view==='draft')await fresh(()=>$('btnToggleDrafts').click(),'final draft view');
                if(view==='advanced')await fresh(()=>$('roadmap-search-toggle').click(),'final expanded view');
                if(view==='csv')$('roadmap-csv-toggle').click();
                if(view==='error'){
                    failEquipment=true;await fresh(()=>form.requestSubmit(),'synthetic failure');await wait(()=>$('roadmap-message').textContent.includes('합성 조회 오류'),'inline error feedback');
                    ok($('roadmap-message').getBoundingClientRect().top>=document.querySelector('.equipment-toolbar').getBoundingClientRect().bottom-1,'failure remains below all toolbar controls');
                    await fresh(()=>form.requestSubmit(),'retry after error');ok($('roadmap-message').textContent==='','successful retry clears the existing error feedback');
                    failEquipment=true;await fresh(()=>form.requestSubmit(),'final failure evidence');await wait(()=>$('roadmap-message').textContent.includes('합성 조회 오류'),'final inline error');
                }
                if(view==='empty'){form.elements.keyword.value='__empty__';await fresh(()=>form.requestSubmit(),'empty result');ok($('roadmap-message').textContent.includes('조건에 맞는 장비가 없습니다.')&&$('roadmap-next').disabled,'empty feedback and disabled paging remain');}
                if(view==='long')$('roadmap-page').textContent='123456789건 · 123456/999999 페이지';
                if(view==='future'){
                    const extra=document.createElement('button');extra.type='button';extra.textContent='확장 검증용 추가 기능';extra.dataset.fixtureOnly='true';document.querySelector('.equipment-page-actions').append(extra);
                    await frame();fit('additional future action');ok(extra.getBoundingClientRect().height===44,'future action inherits the control standard');
                }
                if(view==='edit'){await openModal(101);ok($('modalTitle').textContent.includes('수정')&&$('Name').value===item.Name,'edit keeps original equipment identity');}
                geometry.final=fit('final');
                if(view==='long')ok(geometry.final.controls.find(r=>r.name==='roadmap-page').height>=44,'long counts retain all content and a usable box');
            }else geometry.final=measure();
            ok(unexpected.length===0&&errors.length===0,'no unexpected API writes or JS failures');
            await Promise.all(document.getAnimations().filter(a=>Number.isFinite(a.effect?.getComputedTiming().endTime)).map(a=>a.finished.catch(()=>{})));
            window.scrollTo(0,0);await frame();
            result.textContent=JSON.stringify({status:'pass',view,width:innerWidth,height:innerHeight,theme,skin,baseline:isBaseline,checks,geometry,resize});
        }catch(e){result.textContent=JSON.stringify({status:'fail',view,width:innerWidth,height:innerHeight,theme,skin,baseline:isBaseline,checks,geometry,resize,error:String(e.stack||e),unexpected,errors});}
        parent.postMessage({fixtureResult:result.textContent},location.origin);
    });
})();
