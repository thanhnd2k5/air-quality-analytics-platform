/* Exercise offline app flows in a minimal in-memory DOM, without a browser or dependencies.
   This checks behavior and data, not visual layout or browser compatibility. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync(path.join(__dirname,'dist/index.html'),'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
assert.equal(scripts.length,2);
assert(!/<script[^>]+src=|<link[^>]+href=|@import|https?:\/\//.test(html),'The offline page must have no network dependencies');
assert(!/<!--(?:STYLES|DATA|APP)-->/.test(html),'Build placeholders must be filled');

function boot(storage = new Map(), unavailable = false) {
  const handlers={},elements=new Map(),intervals=new Map();let sequence=0;
  const classList=()=>({values:new Set(),add(v){this.values.add(v);},remove(v){this.values.delete(v);},toggle(v,on){if(on===undefined)on=!this.values.has(v);on?this.values.add(v):this.values.delete(v);}});
  function element(id) {
    if(elements.has(id))return elements.get(id);
    const node={id,value:'',textContent:'',dataset:{},classList:classList(),selectionStart:0,focus(){},setSelectionRange(){},click(){}};
    let value='';Object.defineProperty(node,'innerHTML',{get:()=>value,set(v){value=v;
      for(const m of v.matchAll(/<(input|textarea|select|div|span)[^>]*\bid="([^"]+)"[^>]*>/g)){
        const child=element(m[2]),valueMatch=m[0].match(/\bvalue="([^"]*)"/);if(valueMatch)child.value=valueMatch[1];
      }
    }});elements.set(id,node);return node;
  }
  const doc={getElementById:element,addEventListener(type,fn){handlers[type]=fn;},querySelector(){return element('sidebar');},querySelectorAll(){return [];},createElement(){return {click(){}};}};
  const win={addEventListener(type,fn){handlers[type]=fn;},scrollTo(){},scrollY:0};
  let hash='';const location={get hash(){return hash;},set hash(v){hash=v;handlers.hashchange?.();}};
  const localStorage={getItem(k){if(unavailable)throw Error('denied');return storage.get(k)||null;},setItem(k,v){if(unavailable)throw Error('denied');storage.set(k,v);}};
  const context={window:win,document:doc,location,history:{replaceState(a,b,url){hash=url;}},localStorage,confirm:()=>true,console,Blob,URL,
    setTimeout:()=>++sequence,clearTimeout(){},setInterval(fn){const id=++sequence;intervals.set(id,fn);return id;},clearInterval(id){intervals.delete(id);}};
  vm.createContext(context);for(const code of scripts)vm.runInContext(code,context);
  const act=(type,dataset={},extra={})=>{const target={dataset,disabled:false,tagName:'BUTTON',closest(){return this;},...extra};handlers[type]({target});};
  return {storage,context,element,get text(){return element('app').innerHTML;},click:dataset=>act('click',dataset),input:(extra,dataset={})=>act('input',dataset,extra),change:(extra,dataset={})=>act('change',dataset,extra),state:()=>JSON.parse([...storage.values()][0]||'{}')};
}
const app=boot();
assert(app.text.includes('Hiểu cách làm.'));
assert.equal(app.context.window.STUDY_DATA.questions.length,70);
assert.equal(app.context.window.CORE_LESSONS.length,13);
assert(app.context.window.CORE_LESSONS.every(l=>l.questions.every(id=>app.context.window.STUDY_DATA.questions.some(q=>q.id===id))));

// Foundation lesson: wrong choice explains; a correct choice is saved.
app.click({nav:'theory'});
assert(app.text.includes('Kiến thức nền, dùng được.'));
app.click({quiz:'0'});
assert(app.text.includes('Chưa đúng.'));
app.click({quiz:'1'});
assert(app.text.includes('Đúng rồi.'));
assert.deepEqual(app.state().lessons,[1]);
app.click({lesson:'4'});assert(app.text.includes('Độ đo &amp; tổng hợp đúng'));

// Accent-insensitive search, source-topic filtering, free response, reveal, self-rating and bookmark.
app.click({topic:'D'});assert(app.text.includes('12 câu hỏi'));
app.input({id:'global-search',value:'nguong'});
app.click({nav:'questions'});
app.input({id:'global-search',value:'nguong'});
assert(app.element('question-results').innerHTML.includes('PM2.5'));
app.click({question:'26'});
assert(app.text.includes('Một dòng trong bảng fact'));
assert(!app.text.includes('ĐỐI CHIẾU & TỰ ĐÁNH GIÁ'));
app.input({value:'Một trạm tại một giờ. <script>không chạy</script>'},{note:'26'});
app.click({action:'reveal'});
assert(app.text.includes('ĐỐI CHIẾU & TỰ ĐÁNH GIÁ'));
assert(app.text.includes('&lt;script&gt;không chạy&lt;/script&gt;'));
app.click({rate:'know',id:'26'});app.click({bookmark:'26'});
assert.equal(app.state().ratings['26'],'know');assert(app.state().bookmarks.includes(26));

// Persistence survives a fresh app instance.
const restored=boot(app.storage);restored.click({question:'26'});
assert(restored.text.includes('Một trạm tại một giờ.'));
assert(restored.text.includes('Bỏ lưu câu 26'));

// OLAP actually aggregates and pivots illustrative observations, preserving missing counts.
app.click({nav:'practice'});
assert(app.text.includes('72 dòng giờ–trạm'));
assert(app.text.includes('8 / 12'));
app.change({id:'olap-level',value:'year'});assert(app.text.includes('2 nhóm tổng hợp'));
app.change({id:'olap-station',value:'Dingling'});assert(app.text.includes('1 nhóm tổng hợp'));
app.click({action:'pivot'});assert(app.text.includes('Pivot chỉ đổi bố trí chiều hiển thị.'));

// Metric counts are sourced from the model lock; changing counts recomputes metrics.
app.click({tool:'metrics'});assert(app.element('metrics-output').innerHTML.includes('0,927'));
app.click({model:'persistence'});assert(app.element('metrics-output').innerHTML.includes('0,914'));
for(const [key,value] of Object.entries({tp:0,fp:0,fn:11646,tn:37135}))app.input({value:String(value)},{metric:key});
assert(app.element('metrics-output').innerHTML.includes('0,761'));
assert(app.element('metrics-output').innerHTML.includes('0,000'));
assert(app.element('metrics-output').innerHTML.includes('—'));
app.click({tool:'average'});assert(app.element('average-output').innerHTML.includes('120,00'));

// Timed oral practice requires self-assessment; a whole session records its result.
app.click({nav:'exam'});app.change({id:'exam-count',value:'3'});app.click({action:'exam-start'});
for(let i=0;i<3;i++){
  assert(app.text.includes(`Câu ${i+1} / 3`));
  app.click({action:'exam-reveal'});
  const id=app.text.match(/data-rate="again" data-id="(\d+)" data-exam/)[1];
  app.click({rate:i===1?'practice':'know',id,exam:'true'});
}
assert(app.text.includes('HOÀN THÀNH BUỔI LUYỆN'));
assert.equal(app.state().sessions.at(-1).known,2);
assert.equal(app.state().sessions.at(-1).total,3);
app.click({nav:'notebook'});assert(app.text.includes('Những con số nên nhớ'));assert(app.text.includes('1 CÂU'));

// Browser storage denial is surfaced without breaking the learning page.
const denied=boot(new Map(),true);assert(denied.text.includes('Tiến độ hiện chỉ giữ trong phiên này.'));
console.log('PASS: offline packaging, 13 lessons, 70 questions, search, notes, progress, OLAP, metrics, weighted mean and oral-practice session.');
console.log('Scope: in-memory behavior checks only; browser rendering and accessibility remain unverified.');
