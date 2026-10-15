import './SiteBar.css';

/** The bar across the top of the pages a stranger reaches from the start page:
 *  the name, the way back to it, and the way on from here. The same on each,
 *  so it is found in the same place every time. On a phone each way takes its
 *  short label, where it has one, so both fit on one line. */
export default function SiteBar({
  back,
  on,
}: {
  back: { label: string; short?: string };
  on?: { href: string; label: string; short?: string };
}) {
  return (
    <nav className="site-bar" aria-label="Kataribe">
      <a href="/" className="brand">
        <img src="/logo.png" alt="" />
        Kataribe <span lang="ja">語り部</span>
      </a>
      <span className="site-links">
        <a href="/" className="home">
          <span aria-hidden>←</span> <Label {...back} />
        </a>
        {on && (
          <a href={on.href} className="on">
            <Label {...on} /> <span aria-hidden>→</span>
          </a>
        )}
      </span>
    </nav>
  );
}

/** The label, and its short form for a phone: one shows, the other is gone
 *  from the page altogether, screen readers included. */
function Label({ label, short }: { label: string; short?: string }) {
  if (!short) return <>{label}</>;
  return (
    <>
      <span className="long">{label}</span>
      <span className="short">{short}</span>
    </>
  );
}
