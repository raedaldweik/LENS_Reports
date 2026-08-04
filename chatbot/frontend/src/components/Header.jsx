export default function Header() {
  return (
    <header className="app-header">
      {/* Government of Dubai logo — left */}
      <img className="gov-logo" src="/gov.png" alt="Government of Dubai"
        onError={e => { e.target.style.display = 'none'; }} />

      {/* Title + red line */}
      <div className="title-block">
        <div className="title-row">
          <h1 className="app-title">Smart Monitoring Assistant</h1>
          <div className="red-line" />
        </div>
      </div>

      {/* RTA logo — right */}
      <img className="rta-logo" src="/logo.png" alt="RTA"
        onError={e => { e.target.style.display = 'none'; }} />
    </header>
  );
}
