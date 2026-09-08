import { useState } from 'react';
import { useChat } from '../context/ChatContext';
import { exportConversationPdf } from '../services/exportPdf';
import { policeSrc, badgeSrc, centerSrc } from '../brandAssets';

function LiveBadge() {
  return (
    <div className="live-clock">
      <span className="label"><span className="dot" />البيانات مباشرة</span>
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
  // Official images resolve via brandAssets (window.LENS_ASSETS URLs, else
  // the bundled copies). Each slot falls back to the typographic version when
  // its image is unconfigured or fails to load.
  const [policeOk, setPoliceOk] = useState(true);
  const [centerOk, setCenterOk] = useState(true);
  const [exporting, setExporting] = useState(false);
  const { activeChat } = useChat();

  // "الرجوع للصفحة الرئيسية": target from ?home=<url> (set when the dashboard
  // links here), otherwise browser back.
  const goHome = () => {
    const home = new URLSearchParams(location.search).get('home');
    if (home) location.href = home;
    else history.back();
  };

  const exportReport = async () => {
    if (exporting) return;
    setExporting(true);
    try {
      await exportConversationPdf(activeChat);
    } catch (e) {
      alert('تعذّر إنشاء التقرير: ' + e.message);
    }
    setExporting(false);
  };

  return (
    <header className="topbar">
      {/* Brand cluster — right side in RTL: police | divider | centre+SAS lockup */}
      <div className="brand">
        {policeOk && policeSrc ? (
          <img className="police-logo" src={policeSrc} alt="شرطة دبي — Dubai Police"
            onError={() => setPoliceOk(false)} />
        ) : (
          <>
            {badgeSrc && <img className="badge-logo" src={badgeSrc} alt="" />}
            <div className="wordmark">
              <span className="ar">شرطة دبي</span>
              <span className="en">Dubai Police</span>
            </div>
          </>
        )}
        <div className="divider" />
        {centerOk && centerSrc ? (
          <img className="center-logo" src={centerSrc}
            alt="مركز التحليل والتنبؤ الأمني — Security Analytics & Forecast Center"
            onError={() => setCenterOk(false)} />
        ) : (
          <CenterLockup />
        )}
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

      <LiveBadge />

      <button className="btn-mint" onClick={exportReport} disabled={exporting}
        style={exporting ? { opacity: 0.6, cursor: 'wait' } : undefined}>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
        </svg>
        {exporting ? 'جارٍ إنشاء التقرير…' : 'تصدير التقرير'}
      </button>
    </header>
  );
}
