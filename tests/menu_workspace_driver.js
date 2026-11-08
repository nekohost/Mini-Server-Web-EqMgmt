/* [Role] Checks compact menu geometry, reference help and existing read/open/close workflows.
 * [Dependencies] Actual templates and scripts in the Linux loopback fixture.
 * [Impact] All transport is synthetic and GET-only; destructive controls are never submitted. */
(() => {
    const view='__FIXTURE_VIEW__', theme=new URLSearchParams(location.search).get('theme'), skin=theme==='dark'?'edge':'standard';
    const $=id=>document.getElementById(id), reads=[], unexpected=[], errors=[];
    const user={UserId:900,LoginId:'fixture',Name:'검증',NickName:'검증 사용자',Role:'admin',Email:''};
    const approval={RequestId:41,UserId:901,RequesterName:'합성 사용자',RequestType:'ADD_CATEGORY',RequestDataJSON:'{"name":"합성 카테고리"}',Status:'PENDING',CreatedAt:'2026-11-09 10:00:00',UpdatedAt:'2026-11-09 10:00:00'};
    const cats=[{CategoryId:1,Name:'미니 PC',DisplayName:'미니 PC',IsApproved:'Y',UsageCount:2}], mans=[{ManufacturerId:1,Name:'합성 제조사',DisplayName:'합성 제조사',IsApproved:'Y',UsageCount:2}];
    const node={id:1,name:'시범 노드',parent_id:null,category_id:1,manufacturer_id:1,status:'APPROVED',depth:0,child_count:0,option_count:0,active_equipment_count:2,draft_equipment_count:0};
    const snapshot={success:true,categories:[{id:1,name:'미니 PC',is_approved:true}],manufacturers:[{id:1,name:'합성 제조사',is_approved:true}],nodes:[node],options:[]};
    const item={EquipmentId:101,UserId:901,OwnerNickName:'합성 사용자',Name:'공개 검증 장비',ModelName:'Mini',FullModelName:'Mini',OfficialModelName:'Mini',Status:'ACTIVE',StatusLabel:'정상',CategoryId:1,ManufacturerId:1,Revision:1};
    const menus=['users_management','permissions','master_management','lineup_management','approvals','audit_logs','access_logs','maintenance_admin','backup_restore'].map((MenuCode,i)=>({MenuCode,MenuName:['사용자 관리','메뉴 권한 관리','마스터 데이터 관리','라인업 노드 관리','전자결재함','보안 감사 로그','웹 접근 로그','서버 점검 관리','DB 백업 및 복원'][i],Url:'/'+MenuCode,Description:'기존 기능을 유지하는 메뉴입니다.'}));
    const response=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});
    addEventListener('error',e=>{if(e.error)errors.push(e.message);});
    addEventListener('unhandledrejection',e=>errors.push(String(e.reason)));
    window.fetch=async(path,options={})=>{
        const url=new URL(path,location.href), route=url.pathname;
        if((options.method||'GET')!=='GET'){unexpected.push([options.method,route]);return response({},405);}
        reads.push(url.pathname+url.search);
        if(route==='/api/check_session')return response({valid:true});
        if(route==='/api/user_settings')return response({success:true,settings:{theme,layout_skin:skin}});
        if(route==='/api/me')return response(user);
        if(route==='/api/menus/children/admin_center')return response(menus);
        if(route==='/api/dashboard/master_options')return response({success:true,categories:cats,manufacturers:mans});
        if(route==='/api/dashboard/stats')return response({success:true,data:{my_equipments:2,total_equipments:3,categories:[{category:'미니 PC',count:3}],manufacturers:[{manufacturer:'합성 제조사',count:3}],combined_stats:null}});
        if(route==='/api/master_data')return response({categories:cats,manufacturers:mans});
        if(route==='/api/lineup_tree_all')return response(snapshot);
        if(route==='/api/equipment')return response({items:[item],page:1,pages:1,total:1});
        if(route==='/api/my_approvals')return response({success:true,data:[approval],page:1,pages:1,total:1});
        if(route==='/api/approvals')return response({success:true,data:[approval]});
        if(route==='/api/users')return response({success:true,data:[{...user,UserId:901,LoginId:'sample01',Status:'ACTIVE',IsDeactivated:'N',CreatedAt:'2026-11-09'}]});
        if(route==='/api/permissions')return response(['admin','user'].flatMap(Role=>menus.map(m=>({...m,Role,IsAllowed:Role==='admin'?1:0,ParentMenuCode:'admin_center'}))));
        if(route.startsWith('/api/master/manage/'))return response({success:true,data:route.endsWith('categories')?cats:mans});
        if(route==='/api/admin/lineup_nodes')return response(snapshot);
        if(route==='/api/audit_logs')return response({status:'success',data:[{AuditId:1,CreatedAt:'2026-11-09',ActorName:'합성 사용자',ActorLoginId:'fixture',Action:'LOGIN',TargetId:901,IpAddress:'192.0.2.1',Details:'검증 조회'}],pagination:{total_count:1,page:1,per_page:25,total_pages:1}});
        if(route==='/api/access_logs/stats')return response({total:1,api_count:1,static_count:0,error_rate:0});
        if(route==='/api/access_logs')return response({logs:[{LogId:1,CreatedAt:'2026-11-09',IpAddress:'192.0.2.1',Method:'GET',Path:'/portal',StatusCode:200,ResponseTimeMs:12,UserAgent:'합성 브라우저',RequestPayload:'{}',ResponsePayload:'{}'}],total:1,page:1,per_page:25});
        if(route==='/api/access_logs/error_ips')return response({error_ips:[{IpAddress:'192.0.2.2',TotalErrorCount:3,ClientErrorCount:2,ServerErrorCount:1,LastErrorAt:'2026-11-09'}]});
        unexpected.push(['GET',route]);return response({},404);
    };
    document.addEventListener('DOMContentLoaded',async()=>{
        const result=document.createElement('pre');result.hidden=true;result.id='browser-test-result';document.body.append(result);
        const checks=[],geometry={};
        const wait=async(fn,label)=>{for(let i=0;i<400;i++){if(fn())return;await new Promise(r=>setTimeout(r,15));}throw Error(label);};
        const ok=(condition,label)=>{if(!condition)throw Error(label);checks.push(label);};
        const frame=()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
        const input=(el,value)=>{el.value=value;el.dispatchEvent(new Event('input',{bubbles:true}));};
        const choose=(el,value)=>{el.value=value;el.dispatchEvent(new Event('change',{bubbles:true}));};
        try{
            await wait(()=>document.documentElement.dataset.layoutSkin===skin,'theme and skin');
            if(view==='admin_center')await wait(()=>$('admin-menus-grid').children.length===menus.length,'admin cards');
            if(view==='dashboard')await wait(()=>$('categoryTableBody').rows.length===1,'actual distribution data');
            if(view==='public'){
                await wait(()=>$('equipmentTableBody').textContent.includes(item.Name),'public equipment rows');
                ok(!!$('includeMineCheckbox')&&!$('btnToggleDrafts'),'public scope controls remain');
                $('roadmap-search-toggle').click();ok(!$('roadmap-advanced').hidden,'advanced search opens');$('roadmap-search-toggle').click();
                $('roadmap-csv-toggle').click();ok(!$('roadmap-csv-actions').hidden,'CSV tools open');$('roadmap-csv-toggle').click();
            }
            if(view==='my_approvals'){
                await wait(()=>$('my-approvals-body').textContent.includes('합성 카테고리'),'own request rows');
                $('my-approvals-body').querySelector('button').click();ok($('my-approval-detail').open&&$('my-approval-detail-summary').textContent.includes('합성 카테고리'),'request detail retains its unique title and data');$('my-approval-detail').close();
                choose($('my-approvals-status'),'PENDING');$('my-approvals-filter').requestSubmit();await wait(()=>reads.some(u=>u.includes('status=PENDING')),'inbox filter');
                await wait(()=>document.querySelector('[data-catalog-kind]'),'catalog toolbar mounted');
                const catalog=document.querySelector('[data-catalog-kind]');catalog.click();await wait(()=>document.querySelector('.catalog-request-dialog')?.open,'catalog application');ok(true,'catalog application opens');document.querySelector('.catalog-request-dialog').close();
            }
            if(view==='mypage'){
                document.querySelector('button[onclick="openProfileModal()"]').click();ok(!$('profileModal').classList.contains('hidden'),'profile editor opens');closeProfileModal();
                for(const id of ['passwordModal','withdrawModal']){document.querySelector(id==='passwordModal'?'#openPasswordModal':'#openWithdrawModal').click();ok($(id).open&&!!$(id).querySelector('h2'),'security dialog has its own heading');closeAccountDialog(id);}
                ok(!!$('ai-enter-action')||!!document.querySelector('[name="ai_enter_action"]')||!!document.querySelector('#account-preferences'),'existing input preferences remain');
            }
            if(view==='users_management'){
                await wait(()=>$('userTableBody').textContent.includes('sample01'),'user rows');
                const box=document.querySelector('.user-checkbox');box.click();ok(!$('btnForceSelected').disabled,'selection enables existing actions');box.click();ok($('btnDeleteSelected').disabled,'deselection prevents accidental delete');
                openResetModal(901,'sample01');ok(!$('resetModal').classList.contains('hidden'),'existing user dialog opens');closeResetModal();
            }
            if(view==='permissions'){
                await wait(()=>document.querySelectorAll('.permission-role').length===2,'role list');
                document.querySelector('.permission-role[data-role="user"]').click();ok(!$('permission-detail').hidden&&$('permission-selected-title').textContent.includes('user'),'role selection opens its own permissions');
                input($('permission-role-search'),'not-found');ok(!document.querySelector('.permission-role'),'role filter applies');input($('permission-role-search'),'');
            }
            if(view==='master_management'){
                await wait(()=>$('masterTableBody').textContent.includes('미니 PC'),'category rows');$('tabManufacturers').click();await wait(()=>$('masterTableBody').textContent.includes('합성 제조사'),'manufacturer tab');
                openAddModal();ok(!$('editModal').classList.contains('hidden')&&$('editModalTitle').textContent.includes('추가'),'master editor preserves task title');closeEditModal();
            }
            if(view==='lineup_management'){
                await wait(()=>!$('addRootButton').disabled,'lineup selection');
                $('addRootButton').click();ok(!$('nodeModal').classList.contains('hidden')&&$('nodeModalTitle').textContent.includes('추가'),'node editor opens with unique task title');$('cancelModalButton').click();
                ok($('nodeModal').classList.contains('hidden'),'node editor closes without saving');
            }
            if(view==='approvals'){
                await wait(()=>$('approvalsTableBody').textContent.includes('합성 카테고리'),'approval rows');
                openProcessModal(41,'REJECTED');ok(!$('processModal').classList.contains('hidden'),'approval process dialog opens');closeProcessModal();
            }
            if(view==='audit_logs'||view==='access_logs'){
                const id=view==='audit_logs'?'auditLogTbody':'logsTableBody';await wait(()=>$(id).textContent.includes('192.0.2.1'),'log rows');
                if($('autoRefreshSelect'))choose($('autoRefreshSelect'),'0');
                const n=reads.length;$('searchForm').requestSubmit();await wait(()=>reads.length>n,'log filter request');ok(true,'existing log search works');
                if(view==='access_logs'){openCleanupModal('older_30d');ok(!$('cleanupModal').classList.contains('hidden'),'destructive confirmation retained without submit');closeCleanupModal();}
            }
            if(view==='access_logs_error_ips'){
                await wait(()=>$('errorIpsTableBody').textContent.includes('192.0.2.2'),'error IP rows');
                input($('searchInput'),'not-found');ok($('filteredCountBadge').textContent==='0','error IP filter handles zero result');input($('searchInput'),'');
            }
            if(view==='maintenance_admin')ok($('maintenance-state').textContent==='NORMAL'&&!!$('enable-form'),'maintenance status and activation form remain');
            if(view==='backup_restore')ok(document.querySelector('main').textContent.includes('먼저 서버 점검 모드를 활성화하십시오')&&!!document.querySelector('main a[href="/maintenance_admin"]'),'restore guard and navigation remain');
            await frame();
            const main=document.querySelector('main'),title=$('app-page-title'),nav=document.querySelector('nav.app-nav-polish');
            ok(document.querySelectorAll('h1').length===1&&!!title.textContent.trim()&&!main.querySelector('h1'),'single navigation page heading');
            ok(main.getAttribute('aria-labelledby')===title.id,'main has the surviving title as its accessible name');
            const broken=[...document.querySelectorAll('[aria-labelledby]')].filter(el=>el.getAttribute('aria-labelledby').split(/\s+/).some(id=>!$(id)));
            ok(!broken.length,'all heading references resolve');
            geometry.mainGap=Math.round(main.getBoundingClientRect().top-nav.getBoundingClientRect().bottom);
            geometry.paddingTop=getComputedStyle(main).paddingTop;
            const first=[...main.children].find(el=>!['LINK','SCRIPT','STYLE'].includes(el.tagName)&&el.getBoundingClientRect().height>0);
            geometry.firstContentGap=Math.round(first.getBoundingClientRect().top-nav.getBoundingClientRect().bottom);
            ok(geometry.firstContentGap>=15&&geometry.firstContentGap<=17,'work starts 16px after navigation');
            const guide=main.querySelector('.app-workspace-help');ok(!!guide&&!guide.open&&guide.textContent.trim().length>6,'reference help is preserved and collapsed');
            guide.querySelector('summary').click();ok(guide.open&&guide.querySelector('p').getBoundingClientRect().height>0,'reference help expands');guide.querySelector('summary').click();
            ok(document.documentElement.scrollWidth<=innerWidth+1,'no horizontal page overflow');
            ok(unexpected.length===0&&errors.length===0,'only expected GET requests and no JS errors');
            window.scrollTo(0,0);await frame();
            // Let finite theme/dialog transitions finish so screenshots show the stable selected theme.
            await Promise.all(document.getAnimations().filter(a=>Number.isFinite(a.effect?.getComputedTiming().endTime)).map(a=>a.finished.catch(()=>{})));
            await frame();
            result.textContent=JSON.stringify({status:'pass',view,width:innerWidth,height:innerHeight,theme,skin,checks,geometry});
        }catch(e){result.textContent=JSON.stringify({status:'fail',view,width:innerWidth,height:innerHeight,theme,skin,checks,geometry,error:String(e.stack||e),unexpected,errors});}
        parent.postMessage({fixtureResult:result.textContent},location.origin);
    });
})();
