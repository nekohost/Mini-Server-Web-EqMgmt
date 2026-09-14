// Shared geometry contract for the current unified UI (fixture and real-domain tests).
export function responsiveShellSnapshot() {
    const rect=el=>{const r=el.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom};};
    const one=s=>document.querySelector(s), visible=el=>el.getBoundingClientRect().width>0;
    const title=one('.app-nav-title'), heading=one('.app-content-header'), nickname=one('.app-nav-nickname');
    const style=el=>{const s=getComputedStyle(el);return {fontSize:parseFloat(s.fontSize),lineHeight:parseFloat(s.lineHeight),fontWeight:s.fontWeight,color:s.color,border:s.borderTopWidth,radius:s.borderTopLeftRadius,background:s.backgroundColor,whiteSpace:s.whiteSpace,overflow:s.overflow,textOverflow:s.textOverflow};};
    const workspace=one('.equipment-workspace');
    return {width:innerWidth,nav:rect(one('.app-nav-inner')),row:rect(one('.app-nav-row')),
        title:rect(title),titleText:title.textContent.trim().replace(/\s+/g,' '),weightedLength:Number(title.dataset.weightedLength),
        titleLines:[...document.querySelectorAll('.app-nav-title-line')].map(el=>({text:el.textContent,...rect(el)})),
        left:rect(one('.app-nav-links')),right:rect(one('.app-nav-controls')),links:[...document.querySelectorAll('.app-nav-links .app-nav-link')].map(rect),
        history:rect(one('.app-nav-history')),tools:rect(one('.app-nav-tools')),user:rect(one('.app-nav-user')),logout:rect(one('.app-nav-logout')),
        nickname:{...rect(nickname),...style(nickname),text:nickname.textContent},
        role:{...rect(one('.app-nav-role')),...style(one('.app-nav-role')),text:one('.app-nav-role').textContent},
        rightChildren:[...document.querySelectorAll('.app-nav-tools > *, .app-nav-account > *')].filter(visible).map(rect),
        rightCards:[...document.querySelectorAll('.app-nav-controls .app-nav-control')].map(el=>({...rect(el),...style(el)})),
        headingCount:document.querySelectorAll('.app-content-header').length,
        heading:heading&&{box:rect(heading),title:rect(heading.querySelector('.app-content-title')),description:rect(heading.querySelector('.app-content-description')),
            titleStyle:style(heading.querySelector('.app-content-title')),descriptionStyle:style(heading.querySelector('.app-content-description'))},
        actionRegions:[...document.querySelectorAll('.app-page-controls')].map(rect),
        equipment:workspace&&{box:rect(workspace),search:rect(one('.equipment-search-region')),actions:rect(one('.equipment-action-region')),
            status:rect(one('.equipment-list-status')),table:rect(one('#equipmentTableBody').closest('table'))}};
}
export function assertResponsiveShell(assert,m,label='shell') {
    const center=r=>r.y+r.height/2;
    assert.ok(m.nav.width<=1280,label+': nav width');
    assert.ok(Math.abs(m.title.x+m.title.width/2-m.width/2)<1,label+': exact center');
    assert.ok(m.left.right<=m.title.x+1&&m.title.right<=m.right.x+1,label+': title between side groups');
    assert.ok(Math.abs(center(m.left)-center(m.title))<1&&Math.abs(center(m.right)-center(m.title))<1,label+': same vertical band');
    assert.ok(m.rightChildren.every(r=>r.x>=m.right.x-1&&r.right<=m.right.right+1),label+': right containment');
    const [home,back,parent]=m.links;
    if(m.width<600){
        assert.ok(back.y>=home.bottom-1&&Math.abs(home.x-back.x)<1,label+': stacked home/back');
        if(parent)assert.ok(parent.y>=back.bottom-1&&Math.abs(parent.x-back.x)<1,label+': stacked parent');
        assert.ok(m.user.y>=m.logout.bottom-1&&m.tools.y>=m.user.bottom-1,label+': exactly logout/account/tools rows');
        assert.ok(m.user.height<=32.1&&m.tools.height<=32.1&&m.logout.height<=32.1,label+': three single-line right rows '+JSON.stringify([m.logout.height,m.user.height,m.tools.height]));
        assert.ok(m.titleLines.length>=1,label+': responsive title lines');
    }else{
        assert.ok(back.x>home.right,label+': history beside home');
        assert.ok(Math.abs(center(home)-center(m.history))<1,label+': centered home');
        if(parent)assert.ok(parent.y>=back.bottom-1,label+': desktop parent');
        assert.ok(m.user.y>=m.tools.bottom-1,label+': desktop right rows');
    }
    assert.equal(m.nickname.whiteSpace,'nowrap',label+': nickname one line');
    assert.equal(m.nickname.textOverflow,'ellipsis',label+': constrained nickname fallback');
    assert.ok(m.nickname.height<=m.nickname.lineHeight+1,label+': nickname cannot wrap');
    assert.ok(m.role.width>0&&m.role.height>0,label+': original role remains visible');
    assert.equal(m.rightCards.length,4,label+': four consistently styled controls');
    assert.ok(m.rightCards.every(c=>c.border==='1px'&&c.radius==='12px'),label+': common card border/radius');
    assert.equal(m.headingCount,1,label+': one menu heading');
    const h=m.heading;
    assert.equal(h.titleStyle.fontSize,m.width<768?24:30,label+': unified menu title size');
    assert.equal(h.titleStyle.fontWeight,'700',label+': unified title weight');
    assert.equal(h.descriptionStyle.fontSize,14,label+': unified description');
    assert.ok(h.description.y>=h.title.bottom-1,label+': description below title');
    assert.ok(m.actionRegions.every(r=>r.y>=h.box.bottom-1),label+': functions below menu heading');
    const e=m.equipment;
    if(e){
        if(m.width<1024)assert.ok(e.search.bottom<=e.actions.y+1,label+': mobile search before actions');
        else assert.ok(e.actions.right<=e.search.x+1&&Math.abs(e.actions.y-e.search.y)<1,label+': desktop actions left/search right');
        assert.ok(e.status.y>=Math.max(e.actions.bottom,e.search.bottom)-1,label+': feedback below controls');
        assert.ok(e.table.y>=e.box.bottom-1,label+': table follows search/actions');
    }
}
