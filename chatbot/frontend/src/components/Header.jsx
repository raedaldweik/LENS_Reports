export default function Header() {
  return (
    <header className="app-header">
      {/* Badge — left. Drop the official emblem at frontend/public/police.png to replace it. */}
      <div className="flex items-center gap-3">
        <img className="police-logo" src="/police.png" alt=""
          onError={e => { e.target.style.display = 'none'; }} />
        <img className="badge-logo" src="/badge.svg" alt="Smart Assistant" />
      </div>

      {/* Title + green line */}
      <div className="title-block">
        <div className="title-row">
          <h1 className="app-title">
            Smart Assistant<span className="title-ar">المساعد الذكي</span>
          </h1>
          <div className="red-line" />
        </div>
      </div>

      {/* Dubai Police wordmark — right */}
      <div className="brand-block">
        <span className="brand-ar">شرطة دبي</span>
        <span className="brand-en">Dubai Police</span>
        <span className="brand-center">Security Analytics &amp; Forecast Center · مركز التحليل والتنبؤ الأمني</span>
      </div>
    </header>
  );
}
