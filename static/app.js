/* ============================================================
   کلینیک مسیر — app.js
   تقویم شمسی + فرم رزرو + اتصال به API
   ============================================================ */

// ─── وضعیت کلی برنامه ───────────────────────────────────────
const state = {
    sessionType: null,      // 'online' | 'inperson'
    selectedDate: null,     // '1404-05-12'  (شمسی)
    selectedDateGreg: null, // '2025-08-03'  (میلادی برای API)
    selectedTime: null,     // '17:00'
    name: '',
    phone: '',
    notes: '',
    calYear: null,
    calMonth: null,
    availableDays: [],      // لیست روزهای آزاد از API (میلادی)
};

// ─── آدرس‌دهی API ────────────────────────────────────────────
// BASE به صورت خودکار از Flask تنظیم می‌شود
// روی /booking → '/booking' ، روی / → ''
const BASE = (window.APP_BASE || '').replace(/\/$/, '');
function apiUrl(path) {
    return BASE + path;
}
const FA = ['۰','۱','۲','۳','۴','۵','۶','۷','۸','۹'];
function toFa(n) {
    return String(n).replace(/\d/g, d => FA[d]);
}

// ─── تبدیل تقویم شمسی ↔ میلادی ─────────────────────────────
// کپی مستقیم از jalaali-js v2 (MIT License) — تست‌شده و اثبات‌شده

const JALAALI_BREAKS = [
    -61,9,38,199,426,686,756,818,1111,1181,
    1210,1635,2060,2097,2192,2262,2324,2394,2456,3178
];
function _div(a,b){ return ~~(a/b); }
function _mod(a,b){ return a - ~~(a/b)*b; }

function _g2d(gy,gm,gd){
    let d=_div((gy+_div(gm-8,6)+100100)*1461,4)+_div(153*_mod(gm+9,12)+2,5)+gd-34840408;
    return d-_div(_div(gy+100100+_div(gm-8,6),100)*3,4)+752;
}
function _d2g(jdn){
    let j=4*jdn+139361631;
    j=j+_div(_div(4*jdn+183187720,146097)*3,4)*4-3908;
    const i=_div(_mod(j,1461),4)*5+308;
    return {gd:_div(_mod(i,153),5)+1, gm:_mod(_div(i,153),12)+1, gy:_div(j,1461)-100100+_div(8-(_mod(_div(i,153),12)+1),6)};
}
function _jalCalCore(jy){
    const gy=jy+621;
    let leapJ=-14,jp=JALAALI_BREAKS[0],jm=0,jump=0;
    for(let i=1;i<JALAALI_BREAKS.length;i++){
        jm=JALAALI_BREAKS[i]; jump=jm-jp;
        if(jy<jm) break;
        leapJ=leapJ+_div(jump,33)*8+_div(_mod(jump,33),4);
        jp=jm;
    }
    const n=jy-jp;
    leapJ=leapJ+_div(n,33)*8+_div(_mod(n,33)+3,4);
    if(_mod(jump,33)===4&&jump-n===4) leapJ+=1;
    const leapG=_div(gy,4)-_div((_div(gy,100)+1)*3,4)-150;
    return {gy, march:20+leapJ-leapG, jump, n};
}
function _leapFromCycle(jump,n){
    let adj=n;
    if(jump-n<6) adj=n-jump+_div(jump+4,33)*33;
    let leap=_mod(_mod(adj+1,33)-1,4);
    if(leap===-1) leap=4;
    return leap;
}
function _isLeapJalaali(jy){
    const {jump,n}=_jalCalCore(jy);
    return _leapFromCycle(jump,n)===0;
}
function _j2d(jy,jm,jd){
    const {gy,march}=_jalCalCore(jy);
    return _g2d(gy,3,march)+(jm-1)*31-_div(jm,7)*(jm-7)+jd-1;
}
function _d2j(jdn){
    const gy=_d2g(jdn).gy;
    let jy=gy-621;
    const r=_jalCalCore(jy);
    const leap=_leapFromCycle(r.jump,r.n);
    const jdn1f=_g2d(gy,3,r.march);
    let k=jdn-jdn1f;
    if(k>=0){
        if(k<=185) return {jy,jm:1+_div(k,31),jd:_mod(k,31)+1};
        k-=186;
    } else {
        jy-=1; k+=179;
        if(leap===1) k+=1;
    }
    return {jy, jm:7+_div(k,30), jd:_mod(k,30)+1};
}

function JalaliToGregorian(jy,jm,jd){
    const g=_d2g(_j2d(+jy,+jm,+jd));
    return [g.gy,g.gm,g.gd];
}
function GregorianToJalali(gy,gm,gd){
    const j=_d2j(_g2d(+gy,+gm,+gd));
    return [j.jy,j.jm,j.jd];
}
function jalaliMonthLen(jy,jm){
    if(jm<=6) return 31;
    if(jm<=11) return 30;
    return _isLeapJalaali(jy)?30:29;
}
function jalaliFirstWeekday(jy,jm){
    const [gy,gm,gd]=JalaliToGregorian(jy,jm,1);
    const jsDay=new Date(gy,gm-1,gd).getDay();
    return jsDay===6?0:jsDay+1;
}

// ─── نام ماه‌های شمسی ────────────────────────────────────────
const JALALI_MONTHS = [
    'فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور',
    'مهر','آبان','آذر','دی','بهمن','اسفند'
];

// ─── مقداردهی اولیه ─────────────────────────────────────────
function init() {
    const today = new Date();
    const [jy, jm] = GregorianToJalali(
        today.getFullYear(), today.getMonth() + 1, today.getDate()
    );
    state.calYear = jy;
    state.calMonth = jm;

    // اول تقویم را با روزهای پیش‌فرض (بدون API) نمایش بده
    // تا کاربر منتظر نماند
    state.availableDays = buildFallbackDays();
    renderCalendar();

    // سپس از API روزهای دقیق‌تر را بگیر و آپدیت کن
    fetch(apiUrl('/api/available-days'))
        .then(r => {
            if (!r.ok) throw new Error('API error');
            return r.json();
        })
        .then(days => {
            if (Array.isArray(days) && days.length > 0) {
                state.availableDays = days;
                renderCalendar();
            }
        })
        .catch(() => {
            // API جواب نداد — fallback محاسبه‌شده قبلی باقی می‌ماند
        });

    // رویدادهای انتخاب نوع جلسه
    document.querySelectorAll('input[name="session_type"]').forEach(radio => {
        radio.addEventListener('change', onSessionTypeChange);
    });
}

// ─── محاسبه روزهای آزاد بدون API (fallback) ─────────────────
function buildFallbackDays() {
    const result = [];
    const today = new Date();
    const nowHour = today.getHours();

    for (let i = 1; i <= 60; i++) {
        const t = new Date(today);
        t.setDate(today.getDate() + i);

        // فردا بعد از ساعت ۲۰
        if (i === 1 && nowHour >= 20) continue;

        // جمعه — getDay() در JS: 5=Friday
        if (t.getDay() === 5) continue;

        result.push(t.toISOString().split('T')[0]);
    }
    return result;
}

// ─── مرحله ۱: نوع جلسه ──────────────────────────────────────
function onSessionTypeChange(e) {
    state.sessionType = e.target.value;

    document.querySelectorAll('.session-card').forEach(c => c.classList.remove('selected'));
    e.target.closest('.session-card').classList.add('selected');

    document.getElementById('inperson-notice').style.display =
        state.sessionType === 'inperson' ? 'block' : 'none';

    document.getElementById('btn-step1').disabled = false;

    // اگر ساعت انتخاب شده بود و الان inperson شد و ساعت 21 بود، پاک کن
    if (state.sessionType === 'inperson' && state.selectedTime === '21:00') {
        state.selectedTime = null;
        document.getElementById('btn-step2').disabled = true;
    }
    // بازسازی ساعت‌ها اگر روز انتخاب شده
    if (state.selectedDate) renderSlots();
}

// ─── تغییر ماه تقویم ────────────────────────────────────────
function changeMonth(dir) {
    state.calMonth += dir;
    if (state.calMonth > 12) { state.calMonth = 1; state.calYear++; }
    if (state.calMonth < 1)  { state.calMonth = 12; state.calYear--; }
    renderCalendar();
}

// ─── رندر تقویم شمسی ────────────────────────────────────────
function renderCalendar() {
    const { calYear: jy, calMonth: jm } = state;

    document.getElementById('cal-month-label').textContent =
        `${JALALI_MONTHS[jm - 1]} ${toFa(jy)}`;

    const todayG = new Date();
    const [todayJY, todayJM, todayJD] = GregorianToJalali(
        todayG.getFullYear(), todayG.getMonth() + 1, todayG.getDate()
    );

    const totalDays = jalaliMonthLen(jy, jm);
    const startWD   = jalaliFirstWeekday(jy, jm); // 0=شنبه

    const grid = document.getElementById('cal-grid');
    grid.innerHTML = '';

    // خانه‌های خالی ابتدا
    for (let i = 0; i < startWD; i++) {
        const empty = document.createElement('div');
        empty.className = 'cal-day empty';
        grid.appendChild(empty);
    }

    for (let d = 1; d <= totalDays; d++) {
        const [gy, gm, gd] = JalaliToGregorian(jy, jm, d);
        const gregStr = `${gy}-${String(gm).padStart(2,'0')}-${String(gd).padStart(2,'0')}`;
        const jalaliStr = `${jy}-${String(jm).padStart(2,'0')}-${String(d).padStart(2,'0')}`;

        // چه روزی از هفته؟ (0=شنبه … 6=جمعه)
        const jsDay = new Date(gy, gm - 1, gd).getDay();
        const weekDay = (jsDay + 1) % 7; // Sat=0

        const isToday   = (jy === todayJY && jm === todayJM && d === todayJD);
        const isPast    = (jy < todayJY) || (jy === todayJY && jm < todayJM) || (jy === todayJY && jm === todayJM && d <= todayJD);
        const isFriday  = weekDay === 6;
        const isAvail   = state.availableDays.includes(gregStr);
        const isSelected = (jalaliStr === state.selectedDate);

        const btn = document.createElement('button');
        btn.className = 'cal-day';
        btn.textContent = toFa(d);

        if (isSelected) btn.classList.add('selected');
        if (isToday)    btn.classList.add('today');
        if (isPast)     btn.classList.add('past');
        if (isFriday)   btn.classList.add('friday');
        if (!isAvail || isPast || isFriday) btn.classList.add('disabled');

        if (isAvail && !isPast && !isFriday) {
            btn.onclick = () => selectDate(jalaliStr, gregStr);
        }

        grid.appendChild(btn);
    }

    // دکمه ماه قبل — اگر ماه جاری است، غیرفعال شود
    document.getElementById('btn-prev-month').disabled =
        (jy === todayJY && jm === todayJM);
}

// ─── انتخاب روز ─────────────────────────────────────────────
function selectDate(jalaliStr, gregStr) {
    state.selectedDate = jalaliStr;
    state.selectedDateGreg = gregStr;
    state.selectedTime = null;

    document.getElementById('btn-step2').disabled = true;
    document.getElementById('slots-wrap').style.display = 'block';

    renderCalendar();     // تازه‌سازی برای نمایش انتخاب
    renderSlots();
}

// ─── بارگذاری و رندر ساعت‌های آزاد ─────────────────────────
function renderSlots() {
    const grid = document.getElementById('slots-grid');
    grid.innerHTML = '<div class="loading-slots">در حال بارگذاری ساعت‌ها...</div>';

    const type = state.sessionType === 'inperson' ? 'inperson' : 'online';

    fetch(apiUrl(`/api/slots?date=${state.selectedDateGreg}&type=${type}`))
        .then(r => r.json())
        .then(slots => {
            grid.innerHTML = '';
            if (!slots.length) {
                grid.innerHTML = '<div class="loading-slots">ساعت خالی برای این روز وجود ندارد.</div>';
                return;
            }
            slots.forEach(time => {
                const btn = document.createElement('button');
                btn.className = 'slot-btn';
                btn.textContent = toFa(time);
                if (time === state.selectedTime) btn.classList.add('selected');
                btn.onclick = () => selectTime(time, btn);
                grid.appendChild(btn);
            });
        })
        .catch(() => {
            grid.innerHTML = '<div class="loading-slots">خطا در بارگذاری. دوباره تلاش کنید.</div>';
        });
}

// ─── انتخاب ساعت ────────────────────────────────────────────
function selectTime(time, btn) {
    state.selectedTime = time;
    document.querySelectorAll('.slot-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    document.getElementById('btn-step2').disabled = false;
}

// ─── validate مرحله ۳ ────────────────────────────────────────
function validateStep3() {
    const name  = document.getElementById('input-name').value.trim();
    const phone = document.getElementById('input-phone').value.trim();
    const valid = name.length >= 2 && /^09\d{9}$/.test(phone);
    document.getElementById('btn-step3').disabled = !valid;
    state.name  = name;
    state.phone = phone;
    state.notes = document.getElementById('input-notes').value.trim();
}

// ─── رندر خلاصه رزرو ────────────────────────────────────────
function renderSummary(containerId) {
    const sessionLabel = state.sessionType === 'online' ? 'آنلاین' : 'حضوری';
    const container = document.getElementById(containerId);

    if (containerId === 'booking-summary-top') {
        container.innerHTML = `
            <div><span class="label">نوع جلسه:</span><span class="val">${sessionLabel}</span></div>
            <div><span class="label">تاریخ:</span><span class="val">${toFa(state.selectedDate)}</span></div>
            <div><span class="label">ساعت:</span><span class="val">${toFa(state.selectedTime)}</span></div>
        `;
    } else {
        container.innerHTML = `
            <div class="row"><span class="label">نام</span><span class="val">${state.name}</span></div>
            <div class="row"><span class="label">موبایل</span><span class="val">${toFa(state.phone)}</span></div>
            <div class="row"><span class="label">نوع جلسه</span><span class="val">${sessionLabel}</span></div>
            <div class="row"><span class="label">تاریخ</span><span class="val">${toFa(state.selectedDate)}</span></div>
            <div class="row"><span class="label">ساعت</span><span class="val">${toFa(state.selectedTime)}</span></div>
        `;
    }
}

// ─── جابجایی بین مراحل ──────────────────────────────────────
function goToStep(step) {
    // مخفی کردن همه مراحل
    [1, 2, 3, 4].forEach(s => {
        document.getElementById(`step-${s}`).classList.add('hidden');
        const dot = document.getElementById(`step-dot-${s}`);
        dot.classList.remove('active', 'done');
    });

    // فعال کردن مرحله جاری
    document.getElementById(`step-${step}`).classList.remove('hidden');

    // بروزرسانی نوار مراحل
    for (let s = 1; s <= 4; s++) {
        const dot = document.getElementById(`step-dot-${s}`);
        if (s < step) dot.classList.add('done');
        else if (s === step) dot.classList.add('active');
    }

    // کارهای خاص هر مرحله
    if (step === 3) {
        state.name  = document.getElementById('input-name').value.trim();
        state.phone = document.getElementById('input-phone').value.trim();
        state.notes = document.getElementById('input-notes').value.trim();
        renderSummary('booking-summary-top');
    }

    if (step === 4) {
        state.name  = document.getElementById('input-name').value.trim();
        state.phone = document.getElementById('input-phone').value.trim();
        state.notes = document.getElementById('input-notes').value.trim();
        renderSummary('final-summary');

        // قیمت بر اساس نوع جلسه
        const price = state.sessionType === 'online' ? '۸۵۰٬۰۰۰ تومان' : '۸۰۰٬۰۰۰ تومان';
        document.getElementById('price-label').textContent = price;
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ─── ارسال رزرو و رفتن به درگاه پرداخت ─────────────────────
function submitBooking() {
    const btn = document.getElementById('btn-pay');
    btn.disabled = true;
    btn.textContent = 'در حال اتصال به درگاه...';

    const payload = {
        name:         state.name,
        phone:        state.phone,
        date:         state.selectedDateGreg,
        time:         state.selectedTime,
        session_type: state.sessionType,
        notes:        state.notes,
    };

    fetch(apiUrl('/api/payment/start'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    })
    .then(r => r.json())
    .then(data => {
        if (data.success && data.payment_url) {
            // ریدایرکت به درگاه زرین‌پال
            window.location.href = data.payment_url;
        } else {
            btn.disabled = false;
            btn.textContent = 'پرداخت و ثبت نوبت';
            showError(data.message || 'خطایی رخ داد. دوباره تلاش کنید.');
        }
    })
    .catch(() => {
        btn.disabled = false;
        btn.textContent = 'پرداخت و ثبت نوبت';
        showError('خطا در اتصال به سرور. اینترنت خود را بررسی کنید.');
    });
}

// ─── بررسی پارامترهای URL بعد از بازگشت از درگاه ────────────
function checkUrlParams() {
    const params = new URLSearchParams(window.location.search);

    if (params.get('success') === '1') {
        const refId = params.get('ref') || '';
        showSuccessPage(refId);
        window.history.replaceState({}, '', window.location.pathname);
        return;
    }

    const error = params.get('error');
    if (error) {
        const messages = {
            payment_failed:  'پرداخت توسط کاربر لغو شد یا با خطا مواجه شد.',
            slot_taken:      'این ساعت در حین پرداخت شما توسط نفر دیگری رزرو شد. لطفاً ساعت دیگری انتخاب کنید.',
            invalid_session: 'نشست شما منقضی شده است. لطفاً دوباره رزرو کنید.',
        };
        const msg = messages[error] || 'خطایی رخ داد. لطفاً دوباره تلاش کنید.';
        showFailurePage(msg);
        window.history.replaceState({}, '', window.location.pathname);
    }
}

// ─── صفحه ناموفق ─────────────────────────────────────────────
function showFailurePage(msg) {
    [1,2,3,4].forEach(s => document.getElementById(`step-${s}`).classList.add('hidden'));
    document.getElementById('step-success').classList.add('hidden');
    document.getElementById('step-failed').classList.remove('hidden');
    document.getElementById('fail-reason').textContent = msg;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ─── تلاش دوباره — برگشت به مرحله ۱ ────────────────────────
function retryPayment() {
    document.getElementById('step-failed').classList.add('hidden');
    // ریست state
    state.sessionType = null;
    state.selectedDate = null;
    state.selectedDateGreg = null;
    state.selectedTime = null;
    state.name = '';
    state.phone = '';
    state.notes = '';
    document.querySelectorAll('.session-card').forEach(c => c.classList.remove('selected'));
    document.querySelectorAll('input[name="session_type"]').forEach(r => r.checked = false);
    document.getElementById('btn-step1').disabled = true;
    goToStep(1);
}

// ─── نمایش خطا داخل مرحله ۴ ────────────────────────────────
function showError(msg) {
    const old = document.getElementById('error-box');
    if (old) old.remove();

    const box = document.createElement('div');
    box.id = 'error-box';
    box.style.cssText = `
        background:#fff0f0; border:1px solid #f0aaaa; border-radius:8px;
        padding:12px 16px; color:#c0392b; font-size:13px;
        margin-top:12px; text-align:center;
    `;
    box.textContent = '⚠️ ' + msg;
    document.getElementById('step-4').appendChild(box);
    setTimeout(() => box.remove(), 6000);
}

// ─── بنر خطا بالای صفحه (بعد از بازگشت از درگاه) ───────────
function showErrorBanner(msg) {
    const banner = document.createElement('div');
    banner.style.cssText = `
        background:#fff0f0; border:1px solid #f0aaaa;
        border-radius:10px; padding:16px 20px; color:#c0392b;
        font-size:14px; text-align:center; margin-bottom:16px;
    `;
    banner.textContent = '⚠️ ' + msg;
    document.querySelector('.booking-container').prepend(banner);
    setTimeout(() => banner.remove(), 8000);
}

// ─── نمایش صفحه موفقیت ──────────────────────────────────────
function showSuccessPage(refId) {
    [1,2,3,4].forEach(s => document.getElementById(`step-${s}`).classList.add('hidden'));
    document.getElementById('step-failed').classList.add('hidden');
    document.getElementById('step-success').classList.remove('hidden');

    const refLine = refId
        ? `<div><span class="label">کد پیگیری:</span><span class="val">${toFa(refId)}</span></div>`
        : '';

    document.getElementById('success-summary').innerHTML = `
        ${refLine}
        <div><span class="label">وضعیت پرداخت:</span><span class="val" style="color:var(--teal)">✓ موفق</span></div>
    `;

    for (let s = 1; s <= 4; s++) {
        const dot = document.getElementById(`step-dot-${s}`);
        dot.classList.remove('active');
        dot.classList.add('done');
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ─── شروع ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    checkUrlParams();
    init();
});
