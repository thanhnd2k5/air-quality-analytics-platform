(() => {
  'use strict';
  const DATA = window.STUDY_DATA;
  const LESSONS = window.CORE_LESSONS;
  const KEY = 'int1422-study-room-v1';
  const icons = {
    book:'<path d="M3 4h6a4 4 0 0 1 3 1 4 4 0 0 1 3-1h6v15h-6a4 4 0 0 0-3 1 4 4 0 0 0-3-1H3z"/><path d="M12 5v15"/>',
    home:'<path d="m3 10 9-7 9 7v10H3z"/><path d="M9 20v-7h6v7"/>',
    cards:'<rect x="6" y="6" width="15" height="15" rx="2"/><path d="M17 3H5a2 2 0 0 0-2 2v12M10 11h7m-7 4h5"/>',
    flask:'<path d="M9 3h6M10 3v6L4 19a1 1 0 0 0 1 2h14a1 1 0 0 0 1-2L14 9V3M7 15h10"/>',
    mic:'<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8"/>',
    bookmark:'<path d="M6 3h12v18l-6-4-6 4z"/>',
    arrow:'<path d="M5 12h14m-5-5 5 5-5 5"/>',
    back:'<path d="M19 12H5m5-5-5 5 5 5"/>',
    search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    database:'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
    grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    brain:'<path d="M12 4c-3-4-8 0-6 3-5 0-5 7-2 8-2 5 5 8 8 4 3 4 10 1 8-4 3-1 3-8-2-8 2-3-3-7-6-3zm0 0v15M7 10l5 3 5-3"/>',
    layers:'<path d="m12 3 10 5-10 5L2 8zm-9 9 9 5 9-5M3 16l9 5 9-5"/>',
    cloud:'<path d="M6 18a5 5 0 0 1-1-10 7 7 0 0 1 13-1 5.5 5.5 0 0 1 0 11z"/>',
    star:'<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3l-5.6 2.9 1.1-6.2L3 9.6l6.2-.9z"/>',
    check:'<path d="m5 12 4 4L19 6"/>',
    menu:'<path d="M4 6h16M4 12h16M4 18h16"/>',
    download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
    clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    chart:'<path d="M3 3v18h18M7 16v-5m5 5V6m5 10V9"/>',
    eye:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'
  };
  const icon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.book}</svg>`;
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = (n, digits=0) => Number(n).toLocaleString('vi-VN', {maximumFractionDigits:digits, minimumFractionDigits:digits});
  const norm = text => String(text).normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d').replace(/Đ/g,'D').toLowerCase();
  const question = id => DATA.questions.find(q => q.id === Number(id));
  const section = id => DATA.sections.find(s => s.id === id);
  const validIds = new Set(DATA.questions.map(q => String(q.id)));
  let storageAvailable = true;
  const fresh = () => ({version:1, ratings:{}, bookmarks:[], notes:{}, sessions:[],lessons:[]});
  function sanitize(input) {
    if (!input || input.version !== 1) throw new Error('Định dạng bản lưu không phù hợp.');
    const out = fresh();
    for (const [id, value] of Object.entries(input.ratings || {})) if (validIds.has(id) && ['again','practice','know'].includes(value)) out.ratings[id]=value;
    out.bookmarks = [...new Set((Array.isArray(input.bookmarks) ? input.bookmarks : []).map(Number).filter(id=>validIds.has(String(id))))];
    for (const [id, value] of Object.entries(input.notes || {})) if (validIds.has(id) && typeof value==='string') out.notes[id]=value.slice(0,20000);
    if (Array.isArray(input.sessions)) out.sessions=input.sessions.filter(s=>s && Number.isFinite(s.known) && Number.isFinite(s.total) && typeof s.date==='string').slice(-30);
    if (Array.isArray(input.lessons)) out.lessons=[...new Set(input.lessons.filter(id=>LESSONS.some(l=>l.id===id)))];
    return out;
  }
  let progress = fresh();
  try { const saved=localStorage.getItem(KEY); if(saved) progress=sanitize(JSON.parse(saved)); }
  catch { storageAvailable=false; }
  function persist() {
    try { localStorage.setItem(KEY,JSON.stringify(progress)); }
    catch { if(storageAvailable) toast('Trình duyệt không lưu được tiến độ. Bạn có thể xuất bản lưu.'); storageAvailable=false; }
  }
  let toastTimer;
  function toast(message) {
    const el=document.getElementById('toast'); el.textContent=message; el.classList.add('show');
    clearTimeout(toastTimer); toastTimer=setTimeout(()=>el.classList.remove('show'),3000);
  }
  const ui={query:'',topic:'all',filter:'all',node:'warehouse',tool:'olap',level:'month',station:'all',pivot:false,model:'histgb',metricValues:{},revealed:false,examCount:5,examSection:'all',lesson:1,quizChoice:null};
  let route={page:'home',id:null};
  let exam=null;
  let timer;
  const labels={home:'Góc học tập',theory:'Kiến thức nền',questions:'Ngân hàng câu hỏi',question:'Luyện trả lời',practice:'Phòng thực hành',exam:'Thi thử vấn đáp',notebook:'Sổ tay của bạn'};
  const topicInfo={
    A:{name:'Bài toán & nghiệp vụ',desc:'Giải thích đề tài làm gì, cho ai và giá trị nằm ở đâu.',icon:'cloud',color:'blue'},
    B:{name:'Dữ liệu & tiền xử lý',desc:'Nguồn dữ liệu, NULL và những quy tắc làm sạch.',icon:'layers',color:'orange'},
    C:{name:'Luồng dữ liệu & CDC',desc:'Theo dấu một số đo từ nguồn tới nơi phục vụ.',icon:'database',color:'blue'},
    D:{name:'Kho dữ liệu & OLAP',desc:'Fact, dimension, grain và năm thao tác đa chiều.',icon:'grid',color:''},
    E:{name:'Phân loại & đánh giá',desc:'Nhãn, baseline, F1 và rò rỉ dữ liệu.',icon:'brain',color:'purple'},
    F:{name:'Hồi quy PM2.5',desc:'Dự báo giá trị, MAE và cách đọc đúng sai số.',icon:'chart',color:'orange'},
    G:{name:'Phân cụm trạm',desc:'Hồ sơ trạm, K-Means và diễn giải hai cụm.',icon:'grid',color:'purple'},
    H:{name:'Đợt ô nhiễm & phát lại',desc:'Phân biệt một giờ, một đợt và thời gian báo trước.',icon:'clock',color:'blue'},
    I:{name:'Demo & bảo vệ',desc:'Dẫn chứng, giới hạn và phần đóng góp của mình.',icon:'mic',color:''}
  };
  const flowInfo={
    source:{title:'Nguồn dữ liệu',text:'CSV và SQLite mô phỏng cùng xuất phát từ UCI. Open-Meteo bổ sung khí tượng. Ba kênh tích hợp không phải ba nguồn ô nhiễm độc lập.',q:11},
    lake:{title:'Data lake',text:'Giữ bản thô để truy vết và chạy lại; CSV/API được chuẩn hóa thành Parquet. Nhánh CDC chuẩn hóa rồi upsert staging trực tiếp.',q:18},
    staging:{title:'Staging',text:'Vùng tiếp nhận các bảng quan trắc, thời tiết và danh mục trạm trước khi dbt tích hợp. CDC serving hiện đọc từ vùng này.',q:19},
    warehouse:{title:'Kho dữ liệu',text:'Một dòng fact là một trạm tại một giờ. Bốn chiều: ngày, giờ, trạm và hướng gió. Từ đây mới tạo các bảng tổng hợp và đặc trưng.',q:26},
    olap:{title:'OLAP',text:'Phân tích dữ liệu đã có bằng roll-up, drill-down, slice, dice và pivot. Cube lưu sum và count để tổng hợp trung bình đúng.',q:31},
    ml:{title:'Machine Learning',text:'Phân loại cảnh báo là bài toán chính. Hồi quy PM2.5 và phân cụm trạm là bổ trợ. Đầu vào dự đoán chỉ dùng thông tin đã có tại t.',q:37},
    dashboard:{title:'Dashboard',text:'FastAPI đọc DWH/marts, React hiển thị tổng quan, OLAP và kết quả mô hình. Dashboard là nơi trình bày, không tự chứng minh mô hình đúng.',q:65}
  };
  const countKnown = ids => ids.filter(q=>progress.ratings[q.id]==='know').length;
  function navTo(page,id='') { const hash=`#${page}${id ? '/'+id : ''}`; if(location.hash===hash) render(); else location.hash=hash; }
  function readRoute() {
    const [page,id]=location.hash.replace(/^#/,'').split('/');
    route={page:labels[page]?page:'home',id:id || null};
    ui.revealed=false;
    if(route.page==='questions' && id && section(id)) ui.topic=id;
    render();
    window.scrollTo({top:0,behavior:'instant'});
  }
  function sidebar() {
    const navItems=[['home','home','Góc học tập'],['theory','book','Kiến thức nền'],['questions','cards','Ngân hàng câu hỏi'],['practice','flask','Phòng thực hành'],['exam','mic','Thi thử vấn đáp'],['notebook','bookmark','Sổ tay của bạn']];
    const known=countKnown(DATA.questions);
    return `<aside class="sidebar" aria-label="Điều hướng chính"><button class="brand" data-nav="home"><span class="brand-mark">${icon('book')}</span><span><strong>Góc bảo vệ.</strong><small>HIỂU ĐỂ TRẢ LỜI</small></span></button><nav class="nav">${navItems.map(([p,i,t])=>`<button data-nav="${p}" class="${route.page===p || (route.page==='question' && p==='questions')?'active':''}">${icon(i)}${t}${p==='questions'?`<span class="count">${DATA.questions.length}</span>`:''}</button>`).join('')}</nav><div class="side-label">CHỦ ĐỀ NÊN NẮM</div>${['D','E','C','B'].map(id=>`<button class="side-topic" data-topic="${id}"><span class="dot"></span>${topicInfo[id].name}</button>`).join('')}<div class="side-bottom"><div class="progress-label"><span>Đã tự tin trả lời</span><b>${known}/${DATA.questions.length}</b></div><div class="progress-track"><div class="progress-fill" style="width:${known/DATA.questions.length*100}%"></div></div><p class="side-foot">Ôn theo nhịp của bạn.<br/>Tiến độ lưu trong trình duyệt này.<br/><button data-action="export">Xuất bản lưu</button></p></div></aside>`;
  }
  function render() {
    clearInterval(timer);
    const view=({home:homeView,theory:theoryView,questions:questionsView,question:questionView,practice:practiceView,exam:examView,notebook:notebookView})[route.page];
    document.title=`${labels[route.page]} · Góc bảo vệ`;
    document.getElementById('app').innerHTML=`<div class="layout">${sidebar()}<div class="main-shell"><header class="topbar"><button class="mobile-menu" data-action="menu" aria-label="Mở điều hướng">${icon('menu')}</button><div class="crumb">INT1422 <span class="muted"> / </span> <b>${labels[route.page]}</b></div><div class="top-actions"><label class="search">${icon('search')}<input id="global-search" aria-label="Tìm câu hỏi" placeholder="Tìm câu hỏi, khái niệm…" value="${esc(ui.query)}"><span class="key">/</span></label><span class="avatar" title="Không cần đăng nhập">SV</span></div></header>${!storageAvailable?'<div class="storage-warning">Tiến độ hiện chỉ giữ trong phiên này. Hãy xuất bản lưu trước khi đóng trang.</div>':''}<main id="main" class="content" tabindex="-1">${view()}<footer class="bottom-note"><span>Góc bảo vệ · Kho dữ liệu & Khai phá dữ liệu</span><span>Nội dung từ dự án INT1422 · ${DATA.date} · Ôn tập, không dự đoán đề thi</span></footer></main></div></div>`;
    if(route.page==='exam' && exam && !exam.done) startTimer();
    if(route.page==='practice') { if(ui.tool==='metrics') updateMetrics(); if(ui.tool==='average') updateAverage(); }
  }
  function flowMarkup() {
    const node=(id,label,i)=>`<button class="flow-node ${ui.node===id?'active':''}" data-node="${id}" aria-pressed="${ui.node===id}">${icon(i)}<span>${label}</span></button>`;
    const a='<span class="flow-arrow" aria-hidden="true"></span>';
    const info=flowInfo[ui.node];
    return `<section class="panel flow-panel"><div class="section-head" style="margin-bottom:0"><h2>Một số đo đi qua những đâu?</h2><span class="chip">BẤM ĐỂ KHÁM PHÁ</span></div><p class="flow-sub">Từ dữ liệu gốc đến phân tích và dự đoán.</p><div class="flow-row">${node('source','Nguồn','cloud')}${a}${node('lake','Data lake','layers')}${a}${node('staging','Staging','database')}${a}${node('warehouse','Kho dữ liệu','database')}${a}<div class="flow-branch">${node('olap','OLAP','grid')}${node('ml','ML','brain')}</div>${a}${node('dashboard','Dashboard','chart')}</div><div class="flow-detail"><strong>${info.title}.</strong> ${info.text} <button class="flow-question" data-question="${info.q}">Học câu ${info.q} ↗</button></div></section>`;
  }
  function topicCard(id,idx) {
    const t=topicInfo[id], qs=DATA.questions.filter(q=>q.section===id), known=countKnown(qs);
    return `<button class="topic-card" data-topic="${id}"><div class="topic-top"><span class="topic-icon ${t.color}">${icon(t.icon)}</span><span class="topic-num">0${idx+1}</span></div><h3>${t.name}</h3><p>${t.desc}</p><footer><span>${qs.length} câu hỏi · ${known} đã nắm</span>${icon('arrow')}</footer></button>`;
  }
  function nextQuestion() {return DATA.questions.find(q=>q.section==='D' && q.important && progress.ratings[q.id]!=='know') || DATA.questions.find(q=>q.important && progress.ratings[q.id]!=='know') || DATA.questions[0];}
  function theoryView() {
    const lesson=LESSONS.find(l=>l.id===ui.lesson) || LESSONS[0];
    const choice=ui.quizChoice,correct=choice===lesson.quiz.correct;
    return `<div class="page-title"><div class="eyebrow">NẮM GỐC, RỒI GẮN VÀO ĐỀ TÀI</div><h1>Kiến thức nền, dùng được.</h1><p>13 bài ngắn về những khái niệm dự án thật sự sử dụng. Mỗi bài có định nghĩa, ví dụ, cách áp dụng và một câu tự kiểm tra.</p></div><div class="theory-layout"><nav class="lesson-nav" aria-label="Chọn bài kiến thức nền"><p class="small muted" style="margin:0 10px 12px">${progress.lessons.length}/${LESSONS.length} bài đã trả lời đúng câu kiểm tra</p>${LESSONS.map(l=>`<button data-lesson="${l.id}" class="lesson-link ${l.id===lesson.id?'active':''}" ${l.id===lesson.id?'aria-current="page"':''}><span>${String(l.id).padStart(2,'0')}</span>${esc(l.title)}${progress.lessons.includes(l.id)?'<b aria-label="Đã trả lời đúng">✓</b>':''}</button>`).join('')}</nav><article class="panel lesson-body"><div class="eyebrow">BÀI ${String(lesson.id).padStart(2,'0')} · ${esc(lesson.tag)}</div><h2>${esc(lesson.title)}</h2><p class="lesson-lead">${esc(lesson.idea)}</p><ul class="lesson-points">${lesson.points.map(p=>`<li>${esc(p)}</li>`).join('')}</ul><section class="lesson-example"><h3>Một ví dụ nhỏ</h3><p>${esc(lesson.example)}</p></section><section class="lesson-project"><h3>Trong dự án của bạn</h3><p>${esc(lesson.project)}</p><div class="lesson-question-links">${lesson.questions.map(id=>`<button data-question="${id}">Câu ${id} ↗</button>`).join('')}${lesson.tool?`<button data-open-tool="${lesson.tool}">Thử tương tác ↗</button>`:''}</div></section><div class="note"><strong>Cẩn thận cách nói</strong><br/>${esc(lesson.trap)}</div><section class="lesson-quiz"><div class="eyebrow">KIỂM TRA NHANH</div><h3>${esc(lesson.quiz.prompt)}</h3><div class="quiz-options">${lesson.quiz.options.map((option,i)=>`<button data-quiz="${i}" class="quiz-option ${choice===i?'chosen':''} ${choice!==null && i===lesson.quiz.correct?'correct':''}" aria-pressed="${choice===i}"><span>${'ABC'[i]}</span>${esc(option)}</button>`).join('')}</div>${choice!==null?`<div class="quiz-feedback ${correct?'good':'retry'}" role="status"><strong>${correct?'Đúng rồi.':'Chưa đúng. Hãy xem lại mẫu số hoặc ý nghĩa khái niệm.'}</strong> ${esc(lesson.quiz.explain)}</div>`:'<p class="choice-hint">Chọn một đáp án để mở giải thích. Đây là kiểm tra hiểu bài, không phải câu hỏi thi thật.</p>'}</section><section class="lesson-follow"><span class="eyebrow">NẾU THẦY HỎI TIẾP…</span><h3>“${esc(lesson.follow)}”</h3><p>Thử trả lời trong 30 giây, rồi mở một câu hỏi liên quan ở trên để đối chiếu.</p></section><div class="reader-nav"><button class="btn secondary" data-lesson="${lesson.id-1}" ${lesson.id===1?'disabled':''}>${icon('back')}Bài trước</button><button class="btn primary" data-lesson="${lesson.id+1}" ${lesson.id===LESSONS.length?'disabled':''}>Bài tiếp ${icon('arrow')}</button></div></article></div>`;
  }
  function foundationBanner(resume) {
    return `<section class="foundation-banner"><span class="topic-icon">${icon('book')}</span><div><strong>Kiến thức nền → Ví dụ → Câu hỏi bảo vệ</strong><p>13 bài để hiểu gốc, 70 câu để tập diễn đạt bằng lời của bạn.</p></div><button class="btn soft" data-question="${resume.id}">Luyện trả lời ${icon('arrow')}</button></section>`;
  }
  function homeView() {
    const resume=nextQuestion();
    return `<div class="hero"><div><div class="eyebrow"><span class="dot"></span>PHÒNG HỌC CỦA BẠN · INT1422</div><h1>Hiểu cách làm.<br/>Tự tin trả lời.</h1><p>Đừng học thuộc từng dòng code. Học cách giải thích dữ liệu,<br class="desktop-break"/> lựa chọn thiết kế và bằng chứng của chính dự án mình.</p></div><div class="hero-actions"><button class="btn secondary" data-nav="exam">${icon('mic')}Thi thử vấn đáp</button><button class="btn primary" data-nav="theory">Học kiến thức nền ${icon('arrow')}</button></div></div><div class="dashboard-grid"><div>${foundationBanner(resume)}${flowMarkup()}<div class="section-head topic-head"><h2>Học theo chủ đề</h2><button class="link" data-nav="questions">Tất cả 9 chủ đề ${icon('arrow')}</button></div><div class="topics">${['D','E','C','B'].map(topicCard).join('')}</div></div><aside class="right-column"><section class="panel daily"><span class="watermark" aria-hidden="true">“</span><div class="eyebrow">THẦY CÓ THỂ HỎI</div><h3>Một dòng trong bảng fact biểu diễn cái gì?</h3><p>Thử giải thích bằng một trạm và một mốc giờ cụ thể. Bạn có 60 giây.</p><button class="btn" data-question="26">Tự trả lời trước ${icon('arrow')}</button></section><section class="panel panel-pad"><div class="fact-heading">${icon('bookmark')}Ba điều cần nhớ</div><div class="fact-list"><div class="fact-row"><b>12</b><span>trạm quan trắc</span></div><div class="fact-row"><b>420.768</b><span>dòng giờ–trạm</span></div><div class="fact-row"><b>115 <small>µg/m³</small></b><span>ngưỡng nhãn PM2.5</span></div></div><hr class="section-divider"><button class="topic-link" data-nav="notebook">Mở tờ ghi nhớ ↗</button></section><div class="note"><strong>Mẹo trả lời rõ ý</strong><br/>Mục đích → Cách làm → Kết quả → Giới hạn. Luôn gắn một ví dụ trong dự án.</div></aside></div>`;
  }
  function filteredQuestions() {
    const search=norm(ui.query);
    return DATA.questions.filter(q=>(ui.topic==='all'||q.section===ui.topic) && (!search||norm(q.title+' '+q.answer).includes(search)) && (ui.filter==='all'||(ui.filter==='important'&&q.important)||(ui.filter==='saved'&&progress.bookmarks.includes(q.id))||(ui.filter==='weak'&&progress.ratings[q.id] && progress.ratings[q.id]!=='know')||(ui.filter==='new'&&!progress.ratings[q.id])));
  }
  function bookmarkButton(q) {const saved=progress.bookmarks.includes(q.id);return `<button class="icon-btn ${saved?'saved':''}" data-bookmark="${q.id}" aria-label="${saved?'Bỏ lưu':'Lưu'} câu ${q.id}" aria-pressed="${saved}">${icon('bookmark')}</button>`;}
  function rowsMarkup(qs) {
    if(!qs.length) return '<div class="empty"><h3>Chưa có câu hỏi ở đây</h3><p>Thử đổi bộ lọc, hoặc lưu một câu bạn muốn học lại.</p></div>';
    return `<div class="question-list">${qs.map(q=>`<article class="question-row"><button class="question-open" data-question="${q.id}"><span class="q-number">${String(q.id).padStart(2,'0')}</span><div><h3>${esc(q.title)}</h3><div class="question-meta"><span>${topicInfo[q.section].name}</span>${q.important?'<span>★ Trọng tâm</span>':''}</div></div></button>${progress.ratings[q.id]?`<span class="chip ${progress.ratings[q.id]==='know'?'':'orange'}">${{know:'Đã nắm',practice:'Cần luyện',again:'Học lại'}[progress.ratings[q.id]]}</span>`:''}${bookmarkButton(q)}</article>`).join('')}</div>`;
  }
  function topicOptions(selected='all') {return `<option value="all">Tất cả chủ đề</option>${DATA.sections.map(s=>`<option value="${s.id}" ${selected===s.id?'selected':''}>${s.id}. ${esc(topicInfo[s.id].name)}</option>`).join('')}`;}
  function questionsView() {
    const qs=filteredQuestions();
    return `<div class="page-title"><div class="eyebrow">TỪ HIỂU ĐẾN DIỄN ĐẠT</div><h1>Ngân hàng câu hỏi.</h1><p>70 câu hỏi từ chính dự án. Tự nói hoặc viết câu trả lời, rồi đối chiếu và tự đánh giá.</p></div><div class="filters"><select id="topic-filter" aria-label="Lọc chủ đề">${topicOptions(ui.topic)}</select>${[['all','Tất cả'],['important','★ Trọng tâm'],['new','Chưa học'],['weak','Cần luyện lại'],['saved','Đã lưu']].map(([id,t])=>`<button class="filter-btn ${ui.filter===id?'active':''}" data-filter="${id}">${t}</button>`).join('')}</div><div id="question-results"><p class="inline-result">${qs.length} câu hỏi${ui.query?` phù hợp với “${esc(ui.query)}”`:''}</p>${rowsMarkup(qs)}</div>`;
  }
  function inlineMarkdown(raw) {return esc(raw).replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');}
  function markdown(raw) {
    const lines=raw.split('\n'); let result='',i=0;
    while(i<lines.length) {
      const line=lines[i].trim();
      if(!line){i++;continue;}
      if(line.startsWith('|') && i+1<lines.length && /^\|[\s:|\-]+\|$/.test(lines[i+1].trim())) {
        const cells=l=>l.trim().replace(/^\||\|$/g,'').split('|').map(c=>inlineMarkdown(c.trim()));
        result+='<div class="table-scroll"><table><thead><tr>'+cells(line).map(c=>'<th>'+c+'</th>').join('')+'</tr></thead><tbody>';i+=2;
        while(i<lines.length && lines[i].trim().startsWith('|')){result+='<tr>'+cells(lines[i]).map(c=>'<td>'+c+'</td>').join('')+'</tr>';i++;} result+='</tbody></table></div>';continue;
      }
      if(/^[-*] /.test(line)){result+='<ul>';while(i<lines.length&&/^[-*] /.test(lines[i].trim())){result+='<li>'+inlineMarkdown(lines[i].trim().slice(2))+'</li>';i++;}result+='</ul>';continue;}
      if(/^\d+\. /.test(line)){result+='<ol>';while(i<lines.length&&/^\d+\. /.test(lines[i].trim())){result+='<li>'+inlineMarkdown(lines[i].trim().replace(/^\d+\. /,''))+'</li>';i++;}result+='</ol>';continue;}
      if(line.startsWith('> ')){result+='<blockquote>'+inlineMarkdown(line.slice(2))+'</blockquote>';i++;continue;}
      const para=[];while(i<lines.length && lines[i].trim() && !lines[i].trim().startsWith('|')){para.push(lines[i].trim());i++;}result+='<p>'+inlineMarkdown(para.join(' '))+'</p>';if(!para.length)i++;
    }return result;
  }
  function ratingButtons(qid,examMode=false) {
    return `<div class="rating-row">${[['again','Chưa nắm'],['practice','Cần luyện thêm'],['know','Đã giải thích được']].map(([v,t])=>`<button class="rating ${progress.ratings[qid]===v?'selected':''}" data-rate="${v}" data-id="${qid}" ${examMode?'data-exam="true"':''}>${v==='know'?'✓ ':''}${t}</button>`).join('')}</div>`;
  }
  function questionView() {
    const q=question(route.id);
    if(!q) return '<div class="empty"><h3>Không tìm thấy câu hỏi</h3><button class="btn primary" data-nav="questions">Về ngân hàng câu hỏi</button></div>';
    const siblings=filteredQuestions(),list=siblings.some(x=>x.id===q.id)?siblings:DATA.questions,index=list.findIndex(x=>x.id===q.id);
    return `<div class="reader"><button class="back" data-nav="questions">${icon('back')}Ngân hàng câu hỏi</button><div class="reader-header"><span class="chip">${esc(topicInfo[q.section].name)}</span><div style="display:flex;align-items:center;gap:8px">${q.important?'<span class="chip orange">★ Trọng tâm</span>':''}${bookmarkButton(q)}</div></div><div class="eyebrow">CÂU ${String(q.id).padStart(2,'0')} / ${DATA.questions.length}</div><h1>${esc(q.title)}</h1><section class="panel answer-box"><label class="field-label" for="answer-note">Bạn sẽ trả lời thế nào?</label><textarea class="answer-input" id="answer-note" data-note="${q.id}" maxlength="20000" placeholder="Viết ý của bạn, hoặc nói thành tiếng trong 30–60 giây…">${esc(progress.notes[q.id] || '')}</textarea><div class="answer-help"><span>Mục đích → Cách làm → Kết quả → Giới hạn</span><span id="note-status">${progress.notes[q.id]?'Đã lưu ghi chú':'Lưu tự động'}</span></div><div class="answer-toolbar"><button class="btn primary" data-action="reveal">${icon('eye')}${ui.revealed?'Ẩn đáp án mẫu':'Xem đáp án mẫu'}</button><span class="small muted">Tự trả lời trước khi mở nhé.</span></div></section>${ui.revealed?`<section class="panel answer-box answer-reveal"><div class="eyebrow">ĐỐI CHIẾU & TỰ ĐÁNH GIÁ</div><div class="answer-content">${markdown(q.answer)}</div><hr class="section-divider"><label class="field-label">Bạn đã giải thích được bằng lời của mình chưa?</label>${ratingButtons(q.id)}<p class="source-note">Nguồn: ${DATA.source} · Câu ${q.id}. Đáp án mẫu để tham khảo, không phải lời cam kết về câu hỏi của giảng viên.</p></section>`:''}<div class="reader-nav"><button class="btn secondary" data-question="${list[index-1]?.id || ''}" ${index===0?'disabled':''}>${icon('back')}Câu trước</button><button class="btn secondary" data-question="${list[index+1]?.id || ''}" ${index===list.length-1?'disabled':''}>Câu tiếp ${icon('arrow')}</button></div></div>`;
  }

  // LABS
  const demoRows=[];
  ['2016-01-02','2016-01-03','2016-02-02','2016-02-03','2016-04-02','2016-04-03'].forEach((date,d)=>['Dongsi','Dingling'].forEach((station,s)=>[0,4,8,12,16,20].forEach((hour,h)=>{demoRows.push({date,station,hour,pm25:(d===1&&s===1&&h>1)?null:Math.round(35+d*9+s*23+(h%3)*17)});}))); 
  const dateGroup=(date,level)=>level==='year'?date.slice(0,4):level==='quarter'?`${date.slice(0,4)}-Q${Math.ceil(Number(date.slice(5,7))/3)}`:level==='month'?date.slice(0,7):date;
  function aggregateRows(level,station) {
    const groups=new Map();
    for(const row of demoRows){if(station!=='all'&&row.station!==station)continue;const date=dateGroup(row.date,level),key=row.station+'|'+date;if(!groups.has(key))groups.set(key,{station:row.station,date,sum:0,count:0,hours:0});const g=groups.get(key);g.hours++;if(row.pm25!==null){g.sum+=row.pm25;g.count++;}}
    return [...groups.values()].map(g=>({...g,mean:g.count?g.sum/g.count:null})).sort((a,b)=>a.station.localeCompare(b.station)||a.date.localeCompare(b.date));
  }
  function practiceView() {
    return `<div class="page-title"><div class="eyebrow">CHẠM VÀO KHÁI NIỆM</div><h1>Hiểu bằng cách thử.</h1><p>Thay một lựa chọn, quan sát kết quả, rồi thử giải thích vì sao. Đây là nơi biến định nghĩa thành ví dụ.</p></div><div class="tools-tabs" role="group" aria-label="Chọn bài thực hành">${[['olap','Khám phá OLAP'],['metrics','Precision & Recall'],['average','Trung bình đúng'],['schema','Lược đồ sao']].map(([id,t])=>`<button data-tool="${id}" class="${ui.tool===id?'active':''}" aria-pressed="${ui.tool===id}">${t}</button>`).join('')}</div>${({olap:olapView,metrics:metricsView,average:averageView,schema:schemaView})[ui.tool]()}`;
  }
  function olapView() {
    const rows=aggregateRows(ui.level,ui.station),dates=[...new Set(rows.map(r=>r.date))].sort(),stations=[...new Set(rows.map(r=>r.station))];
    let table;
    if(ui.pivot) table=`<table><thead><tr><th>Thời gian</th>${stations.map(s=>`<th>${s}</th>`).join('')}</tr></thead><tbody>${dates.map(d=>`<tr><td>${d}</td>${stations.map(s=>{const r=rows.find(x=>x.date===d&&x.station===s);return `<td class="number">${r?.mean!=null?fmt(r.mean,1):'—'}</td>`;}).join('')}</tr>`).join('')}</tbody></table>`;
    else table=`<table><thead><tr><th>Trạm</th><th>Thời gian</th><th>PM2.5 TB</th><th>Có số đo / Tổng giờ</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${r.station}</td><td>${r.date}</td><td class="number">${r.mean===null?'—':fmt(r.mean,1)}</td><td class="number">${r.count} / ${r.hours}</td></tr>`).join('')}</tbody></table>`;
    const trunc={day:'day',month:'month',quarter:'quarter',year:'year'}[ui.level];
    const sql=ui.pivot?`-- Pivot chỉ đổi bố trí chiều hiển thị.\n-- Giá trị mỗi ô vẫn là SUM(pm25) / COUNT(pm25).\n-- Hàng: thời gian; cột: trạm.\n-- Dữ liệu truy vấn giữ nguyên bộ lọc đang chọn.`:`SELECT station, date_trunc('${trunc}', event_time) AS period,\n       SUM(pm25) / NULLIF(COUNT(pm25), 0) AS avg_pm25,\n       COUNT(pm25) AS valid_hours, COUNT(*) AS total_hours\nFROM demo_observations${ui.station!=='all'?`\nWHERE station = '${ui.station}'`:''}\nGROUP BY station, period;`;
    return `<div class="lab-grid"><section class="panel panel-pad"><div class="lab-note">Dữ liệu minh họa tự tạo: ${demoRows.length} dòng giờ–trạm, có NULL. Không phải số đo thực từ UCI. Đơn vị PM2.5: µg/m³.</div><div class="lab-controls"><label>Mức tổng hợp<select id="olap-level">${[['day','Ngày'],['month','Tháng'],['quarter','Quý'],['year','Năm']].map(([v,t])=>`<option value="${v}" ${ui.level===v?'selected':''}>${t}</option>`).join('')}</select></label><label>Slice theo trạm<select id="olap-station"><option value="all">Tất cả trạm</option>${['Dongsi','Dingling'].map(s=>`<option ${ui.station===s?'selected':''}>${s}</option>`).join('')}</select></label><button class="btn ${ui.pivot?'primary':'secondary'}" data-action="pivot" aria-pressed="${ui.pivot}">${icon('grid')}Pivot</button></div><div class="table-scroll">${table}</div><p class="small muted" style="margin-top:14px">${rows.length} nhóm tổng hợp. NULL không được tính thành 0.</p><pre class="code-block">${esc(sql)}</pre></section><aside class="panel panel-pad"><h3>Bạn vừa thực hiện gì?</h3><div class="explain-list"><p><strong>Roll-up</strong>Đổi từ tháng lên quý hoặc năm để gộp lên một cấp.</p><p><strong>Drill-down</strong>Đổi từ năm xuống quý, tháng hoặc ngày để xem chi tiết.</p><p><strong>Slice</strong>Chọn một trạm để cố định một giá trị của chiều trạm.</p><p><strong>Pivot</strong>Đổi chiều nằm trên hàng/cột. Không làm thay đổi từng ô tổng hợp.</p><p><strong>Count là mẫu số</strong>Dingling thiếu một số số đo. Xem cả số giờ có giá trị và tổng số giờ.</p></div><hr class="section-divider"><button class="topic-link" data-question="31">Luyện câu hỏi OLAP ↗</button></aside></div>`;
  }
  function metricsView() {
    if(!Object.keys(ui.metricValues).length) ui.metricValues={...DATA.metrics.histgb};
    return `<div class="lab-grid"><section class="panel panel-pad"><div class="section-head"><h2>Ma trận nhầm lẫn</h2><span class="chip">MỨC GIỜ–TRẠM</span></div><p class="small muted" style="margin-bottom:18px">Bắt đầu từ số đếm test đã khóa của dự án. Sửa số đếm để học cách các chỉ số thay đổi.</p><div class="filters"><button class="filter-btn ${ui.model==='histgb'?'active':''}" data-model="histgb">HistGB đã khóa</button><button class="filter-btn ${ui.model==='persistence'?'active':''}" data-model="persistence">Baseline persistence</button></div><div class="matrix">${[['tp','TP — Cảnh báo đúng'],['fp','FP — Báo nhầm'],['fn','FN — Bỏ sót'],['tn','TN — Không cảnh báo, đúng']].map(([key,label])=>`<label>${label}<input type="number" min="0" max="10000000" step="1" data-metric="${key}" value="${ui.metricValues[key]}" aria-label="${label}"><small>${key==='tp'||key==='fn'?'Thực tế vượt ngưỡng':'Thực tế không vượt ngưỡng'}</small></label>`).join('')}</div><div id="metrics-output"></div><p class="source-note" id="metric-source">Nguồn gốc: artifacts/classification/model_lock.json · test 2016 H2. Số đếm chỉnh tay chỉ dùng để minh họa.</p></section><aside class="panel panel-pad"><h3>Đọc chỉ số bằng lời</h3><div class="explain-list"><p><strong>Precision = TP / (TP + FP)</strong>Trong những giờ đã báo động, bao nhiêu giờ thực sự vượt ngưỡng?</p><p><strong>Recall = TP / (TP + FN)</strong>Trong những giờ thực sự vượt ngưỡng, bao nhiêu giờ được phát hiện?</p><p><strong>F1 = 2TP / (2TP + FP + FN)</strong>Cân bằng precision và recall; không phải accuracy.</p><p><strong>Accuracy có thể đánh lừa</strong>Đặt TP = FP = 0, TN = 37.135 và FN = 11.646: accuracy vẫn cao, recall bằng 0.</p></div><button class="topic-link" data-question="45">Vì sao không chỉ dùng accuracy? ↗</button></aside></div>`;
  }
  const ratio=(a,b)=>b?a/b:null;
  function updateMetrics() {
    const el=document.getElementById('metrics-output');if(!el)return;
    const {tp,fp,fn,tn}=ui.metricValues,values=[['Precision',ratio(tp,tp+fp)],['Recall',ratio(tp,tp+fn)],['F1',ratio(2*tp,2*tp+fp+fn)],['Accuracy',ratio(tp+tn,tp+tn+fp+fn)]];
    el.innerHTML=`<div class="metrics">${values.map(([label,v])=>`<div class="metric"><b>${v===null?'—':fmt(v,3)}</b><span>${label}</span></div>`).join('')}</div><div class="small muted">Tổng: ${fmt(tp+fp+fn+tn)} giờ–trạm. “—” nghĩa là mẫu số bằng 0, chỉ số không xác định.</div>`;
  }
  function averageView() {
    return `<div class="lab-grid"><section class="panel panel-pad"><div class="section-head"><h2>Đừng lấy trung bình của trung bình.</h2><span class="chip orange">BẪY THƯỜNG GẶP</span></div><p class="small muted" style="margin-bottom:23px">Hai nhóm có số đo hợp lệ khác nhau. Thử thay mẫu số và xem kết quả.</p><div class="weight-grid">${[['a-count','Số đo hợp lệ nhóm A',24],['a-mean','PM2.5 trung bình nhóm A',100],['b-count','Số đo hợp lệ nhóm B',6],['b-mean','PM2.5 trung bình nhóm B',200]].map(([id,label,value])=>`<label>${label}<input id="${id}" data-average="true" type="number" min="0" step="1" value="${value}"></label>`).join('')}</div><div id="average-output" class="weighted-result"></div></section><aside class="panel panel-pad"><h3>Kho lưu gì để tính đúng?</h3><div class="explain-list"><p><strong>SUM + COUNT</strong>Giữ tổng và số đo hợp lệ để gộp lại các nhóm.</p><p><strong>AVG không cộng được</strong>Không thể lấy AVG của các AVG nếu số đo mỗi nhóm khác nhau.</p><p><strong>NULL khác 0</strong>Một giờ không có số đo không được coi là một giờ có nồng độ bằng 0.</p></div><button class="topic-link" data-question="30">Luyện câu hỏi về độ đo ↗</button></aside></div>`;
  }
  function updateAverage() {
    const values=['a-count','a-mean','b-count','b-mean'].map(id=>Math.max(0,Number(document.getElementById(id)?.value)||0));
    const [n1,m1,n2,m2]=values,valid=(n1?n1:0)+(n2?n2:0),sum=n1*m1+n2*m2,mean=ratio(sum,valid);
    document.getElementById('average-output').innerHTML=`<div class="eyebrow">TRUNG BÌNH CÓ TRỌNG SỐ</div><b>${mean===null?'—':fmt(mean,2)} <small>µg/m³</small></b><p>(${fmt(n1)} × ${fmt(m1)} + ${fmt(n2)} × ${fmt(m2)}) / ${fmt(valid)} ${!valid?'— chưa có số đo hợp lệ':''}</p><p>Lấy trung bình hai giá trị hiển thị sẽ ra ${fmt((m1+m2)/2,2)}. Cách đó chỉ dùng được khi các nhóm có cùng số đo hợp lệ và khác 0.</p>`;
  }
  function schemaView() {
    return `<div class="lab-grid"><section class="panel panel-pad"><div class="section-head"><h2>Một trạm, tại một giờ.</h2><span class="chip">GRAIN CỦA FACT</span></div><p class="small muted">Ví dụ minh họa: Dongsi lúc 10:00 ngày 01/12/2016. Số đo nằm trong fact; các dimension cung cấp góc nhìn để phân tích.</p><div class="schema"><div class="schema-item"><b>dim_date</b>Ngày → Tháng → Quý → Năm<br/>Mùa cũng là thuộc tính của ngày.</div><div class="schema-item"><b>dim_time</b>Giờ → Buổi trong ngày</div><div class="schema-item fact"><b>fact_air_quality_hourly</b>Khóa chiều ngày · giờ · trạm · hướng gió<br/>Độ đo: PM2.5, PM10, khí tượng…<br/>Một dòng = một trạm × một giờ</div><div class="schema-item"><b>dim_station</b>Trạm → Quận</div><div class="schema-item"><b>dim_wind_direction</b>Hướng gió → Phần tư → Bắc/Nam</div></div><hr class="section-divider"><div class="note"><strong>4 bảng chiều ≠ 4 thuộc tính trong cube</strong><br/>Cube hiện chọn 5 thuộc tính: năm, mùa, quận, buổi, phần tư hướng gió. Năm và mùa cùng thuộc chiều ngày. Vì vậy có 2⁵ = 32 grouping sets.</div></section><aside class="panel panel-pad"><h3>Giải thích thay vì đọc tên bảng</h3><div class="explain-list"><p><strong>Fact</strong>Điều gì đã được quan sát và đo bao nhiêu?</p><p><strong>Dimension</strong>Quan sát xảy ra khi nào, ở đâu, trong bối cảnh nào?</p><p><strong>Grain</strong>Một dòng thật sự đại diện cho điều gì?</p></div>${[25,26,28,33].map(id=>`<button class="topic-link" data-question="${id}">Câu ${id}: ${esc(question(id).title)} ↗</button>`).join('')}</aside></div>`;
  }

  // ORAL PRACTICE
  function examView() {
    if(!exam) return `<div class="page-title"><div class="eyebrow">ĐÓNG TÀI LIỆU, THỬ NÓI XEM</div><h1>Một buổi bảo vệ nhỏ.</h1><p>Tập nói có cấu trúc, rồi tự đối chiếu với đáp án. Không có AI chấm điểm hay nhận diện giọng nói.</p></div><section class="panel exam-start"><span class="chip">VẤN ĐÁP TỰ LUYỆN</span><h2>Mỗi câu, một phút để rõ ý.</h2><p>Chọn chủ đề, nhận câu hỏi ngẫu nhiên và bắt đầu trả lời thành tiếng. Hết giờ chỉ là lời nhắc; bạn vẫn có thể hoàn thành câu trả lời.</p><div class="exam-options"><label>Phạm vi<select id="exam-topic">${topicOptions(ui.examSection)}</select></label><label>Số câu<select id="exam-count">${[3,5,10].map(n=>`<option value="${n}" ${ui.examCount===n?'selected':''}>${n} câu</option>`).join('')}</select></label></div><button class="btn primary" data-action="exam-start">${icon('mic')}Bắt đầu buổi luyện</button><div class="exam-rubric">Tự chấm theo bốn ý: mục đích → cách làm → kết quả → giới hạn. Điểm tự đánh giá không dự đoán điểm của giảng viên.</div>${progress.sessions.length?`<p class="choice-hint">Buổi gần nhất: ${progress.sessions.at(-1).known}/${progress.sessions.at(-1).total} câu tự đánh giá đã nắm.</p>`:''}</section>`;
    if(exam.done) return `<div class="reader"><div class="eyebrow">HOÀN THÀNH BUỔI LUYỆN</div><h1>Bạn đã nói rõ hơn rồi.</h1><section class="panel exam-start"><div class="result-score">${exam.scores.filter(s=>s==='know').length}<small> / ${exam.ids.length} câu tự đánh giá đã nắm</small></div><p>Đây là kết quả tự đánh giá. Những câu chưa nắm đã được đánh dấu để bạn quay lại luyện.</p><div class="question-list" style="margin-bottom:25px">${exam.ids.map((id,i)=>`<button class="question-row question-open" data-question="${id}"><span class="q-number">${i+1}</span><div><h3>${esc(question(id).title)}</h3><span class="chip ${exam.scores[i]==='know'?'':'orange'}">${{know:'Đã nắm',practice:'Cần luyện thêm',again:'Học lại'}[exam.scores[i]]}</span></div></button>`).join('')}</div><button class="btn primary" data-action="exam-new">Luyện buổi khác ${icon('arrow')}</button><button class="btn ghost" data-action="weak">Xem các câu cần luyện</button></section></div>`;
    const q=question(exam.ids[exam.index]);
    return `<div class="reader"><div class="practice-heading"><button class="back" style="margin:0" data-action="exam-end">${icon('back')}Kết thúc buổi luyện</button><div class="timer" id="exam-timer" aria-label="Thời gian còn lại">01:00</div></div><div class="exam-progress"><span class="small muted">Câu ${exam.index+1} / ${exam.ids.length}</span><div class="progress-track"><div class="progress-fill" style="width:${exam.index/exam.ids.length*100}%"></div></div></div><span class="chip">${esc(topicInfo[q.section].name)}</span><h1>${esc(q.title)}</h1><section class="panel answer-box"><label class="field-label" for="exam-answer">Nói thành tiếng, hoặc ghi lại các ý chính</label><textarea id="exam-answer" class="answer-input" data-exam-note="true" placeholder="Đi thẳng vào ý chính, sau đó đưa ví dụ…">${esc(exam.note || '')}</textarea><div class="answer-toolbar"><button class="btn primary" data-action="exam-reveal">${icon('eye')}${exam.revealed?'Ẩn đáp án':'Mở đáp án & tự đánh giá'}</button></div></section>${exam.revealed?`<section class="panel answer-box answer-reveal"><div class="answer-content">${markdown(q.answer)}</div><hr class="section-divider"><strong class="small">Tự đánh giá để chuyển sang câu tiếp</strong>${ratingButtons(q.id,true)}<p class="small muted" style="margin-top:12px">Chọn một mức sẽ lưu tiến độ và ${exam.index+1===exam.ids.length?'kết thúc buổi luyện':'chuyển sang câu tiếp'}.</p></section>`:''}</div>`;
  }
  function startTimer() {
    const tick=()=>{const el=document.getElementById('exam-timer');if(!el)return;const seconds=Math.max(0,Math.ceil((exam.deadline-Date.now())/1000));el.textContent=`${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;el.classList.toggle('expired',seconds===0);if(!seconds && !exam.notified){exam.notified=true;toast('Hết một phút. Bạn vẫn có thể hoàn thiện ý rồi đối chiếu.');}};
    tick(); timer=setInterval(tick,1000);
  }
  function beginExam() {
    const pool=DATA.questions.filter(q=>ui.examSection==='all'||q.section===ui.examSection).map(q=>q.id);
    for(let i=pool.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[pool[i],pool[j]]=[pool[j],pool[i]];}
    exam={ids:pool.slice(0,Math.min(pool.length,ui.examCount)),index:0,scores:[],deadline:Date.now()+60000,revealed:false,note:'',done:false,notified:false};render();
  }
  function notebookView() {
    const saved=DATA.questions.filter(q=>progress.bookmarks.includes(q.id));
    return `<div class="page-title"><div class="eyebrow">MANG THEO NHỮNG Ý CỐT LÕI</div><h1>Sổ tay trước giờ bảo vệ.</h1><p>Con số phải đi cùng ý nghĩa. Ghi chú và câu đã lưu chỉ nằm trong trình duyệt này; bạn có thể xuất để mang sang máy khác.</p></div><section class="panel intro-card"><h2>Giới thiệu đề tài trong một phút</h2><p>${esc(DATA.intro)}</p></section><div class="section-head"><h2>Câu bạn đã lưu</h2><span class="chip">${saved.length} CÂU</span></div>${rowsMarkup(saved)}<div class="section-head topic-head"><h2>Những con số nên nhớ</h2><span class="small muted">Kết quả đã ghi nhận trong dự án</span></div><div class="facts-grid">${DATA.facts.map(([title,value])=>`<article class="fact-card"><h3>${esc(title)}</h3><p>${esc(value)}</p></article>`).join('')}</div><div class="footer-actions"><button class="btn primary" data-action="export">${icon('download')}Xuất tiến độ & ghi chú</button><button class="btn secondary" data-action="import">Nhập bản lưu</button><button class="btn ghost" data-action="reset">Xóa tiến độ trên máy này</button></div><input id="import-file" type="file" accept="application/json,.json" hidden><p class="source-note">Nguồn nội dung: ${DATA.source}. Đây là tài liệu hỗ trợ ôn tập theo dự án, không thay thế giáo trình học phần.</p>`;
  }

  // INTERACTIONS
  document.addEventListener('click',event=>{
    const button=event.target.closest('button');if(!button || button.disabled)return;
    if(button.dataset.nav){if(button.dataset.nav==='questions'){ui.query='';ui.topic='all';ui.filter='all';}navTo(button.dataset.nav);return;}
    if(button.dataset.topic){ui.topic=button.dataset.topic;ui.filter='all';ui.query='';navTo('questions',ui.topic);return;}
    if(button.dataset.question){navTo('question',button.dataset.question);return;}
    if(button.dataset.node){ui.node=button.dataset.node;const pos=window.scrollY;render();window.scrollTo(0,pos);return;}
    if(button.dataset.bookmark){const id=Number(button.dataset.bookmark);progress.bookmarks=progress.bookmarks.includes(id)?progress.bookmarks.filter(n=>n!==id):[...progress.bookmarks,id];persist();render();return;}
    if(button.dataset.filter){ui.filter=button.dataset.filter;render();return;}
    if(button.dataset.tool){ui.tool=button.dataset.tool;render();return;}
    if(button.dataset.openTool){ui.tool=button.dataset.openTool;navTo('practice');return;}
    if(button.dataset.lesson){const id=Number(button.dataset.lesson);if(LESSONS.some(l=>l.id===id)){ui.lesson=id;ui.quizChoice=null;render();window.scrollTo(0,0);}return;}
    if(button.dataset.quiz!==undefined){ui.quizChoice=Number(button.dataset.quiz);const lesson=LESSONS.find(l=>l.id===ui.lesson);if(ui.quizChoice===lesson.quiz.correct&&!progress.lessons.includes(lesson.id)){progress.lessons.push(lesson.id);persist();}const pos=window.scrollY;render();window.scrollTo(0,pos);return;}
    if(button.dataset.model){ui.model=button.dataset.model;ui.metricValues={...DATA.metrics[ui.model]};render();return;}
    if(button.dataset.rate){
      const id=Number(button.dataset.id);progress.ratings[id]=button.dataset.rate;
      if(button.dataset.exam && exam && !exam.done){exam.scores.push(button.dataset.rate);if(exam.note)progress.notes[id]=exam.note;if(exam.index+1===exam.ids.length){exam.done=true;progress.sessions.push({known:exam.scores.filter(s=>s==='know').length,total:exam.ids.length,date:new Date().toISOString()});progress.sessions=progress.sessions.slice(-30);}else{exam.index++;exam.revealed=false;exam.note='';exam.deadline=Date.now()+60000;exam.notified=false;}}
      persist();render();if(button.dataset.exam)window.scrollTo(0,0);else toast('Đã lưu mức độ nắm bài.');return;
    }
    switch(button.dataset.action){
      case 'menu':document.querySelector('.sidebar').classList.toggle('open');break;
      case 'reveal':ui.revealed=!ui.revealed;render();break;
      case 'pivot':ui.pivot=!ui.pivot;render();break;
      case 'exam-start':beginExam();break;
      case 'exam-reveal':exam.revealed=!exam.revealed;render();break;
      case 'exam-new':exam=null;render();break;
      case 'exam-end':if(confirm('Kết thúc buổi luyện này? Các câu đã tự đánh giá vẫn được lưu.')){exam=null;render();}break;
      case 'weak':ui.topic='all';ui.filter='weak';ui.query='';navTo('questions');break;
      case 'export':{
        const blob=new Blob([JSON.stringify(progress,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='goc-bao-ve-tien-do.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Đã xuất bản lưu tiến độ.');break;
      }
      case 'import':document.getElementById('import-file').click();break;
      case 'reset':if(confirm('Xóa toàn bộ mức tự đánh giá, câu đã lưu và ghi chú trên trình duyệt này? Nên xuất bản lưu trước.')){progress=fresh();persist();exam=null;render();toast('Đã xóa tiến độ trên trình duyệt này.');}break;
    }
  });
  document.addEventListener('input',event=>{
    const el=event.target;
    if(el.id==='global-search'){
      ui.query=el.value;
      if(route.page!=='questions') {route={page:'questions',id:null};ui.topic='all';ui.filter='all';history.replaceState(null,'','#questions');const caret=el.selectionStart;render();const search=document.getElementById('global-search');search.focus();search.setSelectionRange(caret,caret);}
      else {const qs=filteredQuestions();document.getElementById('question-results').innerHTML=`<p class="inline-result">${qs.length} câu hỏi${ui.query?` phù hợp với “${esc(ui.query)}”`:''}</p>${rowsMarkup(qs)}`;}
    }
    if(el.dataset.note){progress.notes[el.dataset.note]=el.value;persist();const status=document.getElementById('note-status');if(status)status.textContent=storageAvailable?'Đã lưu ghi chú':'Chưa lưu được — hãy xuất bản lưu';}
    if(el.dataset.examNote && exam)exam.note=el.value;
    if(el.dataset.metric){const n=Math.max(0,Math.min(10000000,Math.round(Number(el.value)||0)));ui.metricValues[el.dataset.metric]=n;ui.model='custom';document.querySelectorAll('[data-model]').forEach(b=>b.classList.remove('active'));updateMetrics();}
    if(el.dataset.average)updateAverage();
  });
  document.addEventListener('change',async event=>{
    const el=event.target;
    if(el.id==='topic-filter'){ui.topic=el.value;render();}
    if(el.id==='olap-level'){ui.level=el.value;render();}
    if(el.id==='olap-station'){ui.station=el.value;render();}
    if(el.id==='exam-topic')ui.examSection=el.value;
    if(el.id==='exam-count')ui.examCount=Number(el.value);
    if(el.dataset.metric){el.value=ui.metricValues[el.dataset.metric];}
    if(el.id==='import-file'&&el.files[0]){
      try{if(el.files[0].size>2000000)throw new Error('Bản lưu quá lớn.');const loaded=sanitize(JSON.parse(await el.files[0].text()));if(confirm('Thay tiến độ hiện tại bằng bản lưu này?')){progress=loaded;persist();render();toast('Đã nhập tiến độ và ghi chú.');}}
      catch(error){toast('Không đọc được bản lưu: '+error.message);}el.value='';
    }
  });
  document.addEventListener('keydown',event=>{if(event.key==='/'&&!/INPUT|TEXTAREA|SELECT/.test(event.target.tagName)&&!event.ctrlKey&&!event.metaKey){event.preventDefault();document.getElementById('global-search').focus();}if(event.key==='Escape')document.querySelector('.sidebar')?.classList.remove('open');});
  window.addEventListener('hashchange',readRoute);
  readRoute();
})();
