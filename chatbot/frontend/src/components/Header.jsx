import { useEffect, useState } from 'react';

function LiveClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  const time = now.toLocaleTimeString('en-GB', { timeZone: 'Asia/Dubai', hour12: false });
  return (
    <div className="live-clock">
      <span className="label"><span className="dot" />البيانات مباشرة</span>
      <span className="time">{time}</span>
    </div>
  );
}

/* The bilingual centre lockup — English column left, Arabic right,
   matching the official arrangement. */
function CenterLockup() {
  return (
    <div className="center-lockup" aria-label="مركز التحليل والتنبؤ الأمني — Security Analytics & Forecast Center">
      <span className="ar sm">مـركـز</span>       <span className="en sm">Security</span>
      <span className="ar lg">التحليــل و</span>  <span className="en lg">Analytics &amp;</span>
      <span className="ar lg">التنبــؤ</span>     <span className="en lg">Forecast</span>
      <span className="ar sm">الأمني</span>       <span className="en sm">Center</span>
    </div>
  );
}

export default function Header() {
  // Official assets in frontend/public/: police.png (Dubai Police lockup) and
  // sas.png (SAS logo). Until they exist, police falls back to the neutral
  // badge + wordmark and the SAS slot stays hidden.
  const [policeOk, setPoliceOk] = useState(true);
  const [sasOk, setSasOk] = useState(true);

  // "الرجوع للصفحة الرئيسية": target from ?home=<url> (set when the dashboard
  // links here), otherwise browser back.
  const goHome = () => {
    const home = new URLSearchParams(location.search).get('home');
    if (home) location.href = home;
    else history.back();
  };

  const exportReport = () => window.print();

  return (
    <header className="topbar">
      {/* Brand cluster — right side in RTL: police | divider | sas | centre lockup */}
      <div className="brand">
        {policeOk ? (
          <img className="police-logo" src="/police.png" alt="شرطة دبي — Dubai Police"
            onError={() => setPoliceOk(false)} />
        ) : (
          <>
            <img className="badge-logo" src="/badge.svg" alt="" />
            <div className="wordmark">
              <span className="ar">شرطة دبي</span>
              <span className="en">Dubai Police</span>
            </div>
          </>
        )}
        <div className="divider" />
        {sasOk && (
          <img className="sas-logo" src="/sas.png" alt="SAS"
            onError={() => setSasOk(false)} />
        )}
        <CenterLockup />
      </div>

      <div className="flex-1" />

      <button className="btn-ghost" onClick={goHome}>
        الرجوع للصفحة الرئيسية
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ transform: 'scaleX(-1)' }}>
          <polyline points="9 18 15 12 9 6" />
        </svg>
      </button>

      <div className="divider" />

      <LiveClock />

      <button className="btn-mint" onClick={exportReport}>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
        </svg>
        تصدير التقرير
      </button>
    </header>
  );
}
