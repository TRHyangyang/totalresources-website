// Targeted state regression checks; synthetic data never reaches production.
// NODE_PATH=<existing Playwright parent> node tools/test_daily_headlines_browser.cjs <base> <chrome> <screenshots> [--live]
const {chromium}=require('playwright');
const fs=require('fs');
const [base,chrome,output]=process.argv.slice(2); const live=process.argv.includes('--live');
const assert=(v,m)=>{if(!v)throw Error(m);};
(async()=>{
 const browser=await chromium.launch({executablePath:chrome,headless:true});let checks=0;
 fs.mkdirSync(output,{recursive:true});
 try{
  for(const width of [1440,390]){
   const context=await browser.newContext({viewport:{width,height:1000}});const page=await context.newPage();
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   const date=await page.evaluate(()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()));
   const failure={schema_version:1,date,status:'NO_VERIFIED_UPDATE'};
   const headline={date,headline_cn:'测试头条',summary:'测试摘要，不是新闻。',category:'TEST',confidence:'PARTIAL'};
   const success={schema_version:1,date,status:'PUBLISHED',headlines:[headline]};
   const cases=live?[['LIVE',undefined,undefined,'No Verified Update',true]]:[
    ['PENDING',null,null,'Daily Intelligence Update Pending',true],
    ['QA_FAIL',null,failure,'No Verified Update',true],
    ['STALE_ARTICLE',{...success,date:'2000-01-01'},failure,'No Verified Update',true],
    ['OLD_FAILURE',null,{...failure,date:'2000-01-01'},'Daily Intelligence Update Pending',true],
    ['MALFORMED', {...success,headlines:[{}]},null,'Daily Intelligence Update Pending',true],
    ['SUCCESS_AFTER_FAILURE',success,failure,null,false],
    ['NO_CHANGE',{schema_version:1,date,status:'NO_MATERIAL_CHANGE',headlines:[]},failure,'No Material Intelligence Change',false]
   ];
   for(const [name,data,outcome,expected,archive]of cases){
    if(!live){
     await page.route('**/data/daily-headlines/latest.json',r=>data?r.fulfill({json:data}):r.fulfill({status:503,body:'unavailable'}));
     await page.route('**/data/daily-headlines/status.json',r=>outcome?r.fulfill({json:outcome}):r.fulfill({status:404,body:'missing'}));
    }
    for(const route of ['/','/intelligence/daily-headlines/']){
     const response=await page.goto(base+route,{waitUntil:'networkidle'});assert(response.status()===200,route+' HTTP');
     const root=page.locator('[data-daily-headlines]');const state=root.locator('.dh-state');
     if(expected){assert((await state.innerText()).includes(expected),name+' state');assert(await root.locator('.dh-card').count()===0,name+' leaked cards');}
     else assert(await root.locator('.dh-card').count()===1,name+' missing cards');
     const href=await root.locator('.dh-action').getAttribute('href');
     assert(href===(archive?'/intelligence/daily-headlines/#archive':'/intelligence/daily-headlines/'+date+'.html'),name+' link');
     assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),name+' overflow');
     if(route!=='/'){
      assert(await page.locator('main .dh-eyebrow').count()===1,'Duplicate title');
      assert(await page.locator('#archive').count()===1,'Missing archive target');
     }
     if(name==='QA_FAIL'||name==='LIVE')await root.screenshot({path:output+'/'+(route==='/'?'home':'column')+'-'+width+'.png'});
     checks++;
    }
    if(!live){await page.unroute('**/data/daily-headlines/latest.json');await page.unroute('**/data/daily-headlines/status.json');}
   }
   if(!live){
    await page.route('**/data/daily-headlines/latest.json',r=>r.fulfill({status:503,body:'missing'}));
    await page.route('**/data/daily-headlines/status.json',r=>r.fulfill({json:failure}));
    await page.clock.install({time:new Date(date+'T15:59:50Z')});await page.goto(base+'/intelligence/daily-headlines/',{waitUntil:'networkidle'});
    await page.clock.runFor(70000);
    await page.waitForFunction(()=>document.querySelector('.dh-state').textContent.includes('Daily Intelligence Update Pending'));
    checks++;
   }
   assert(errors.length===0,errors.join('\n'));await context.close();
  }
  console.log(JSON.stringify({status:'PASS',checks,live}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
