import './SiteBar.css';

/** The bar across the top of the pages a stranger reaches from the start page:
 *  the name, the way back to it, and the way on from here. The same on each,
 *  so it is found in the same place every time. */
export default function SiteBar({
  back,
  on,
}: {
  back: string;
  on?: { href: string; label: string };
}) {
  return (
    <nav className="site-bar" aria-label="Kataribe">
      <a href="/" className="brand">
        <img src="/logo.png" alt="" />
        Kataribe <span lang="ja">語り部</span>
      </a>
      <span className="site-links">
        <a href="/" className="home">
          <span aria-hidden>←</span> {back}
        </a>
        {on && (
          <a href={on.href} className="on">
            {on.label} <span aria-hidden>→</span>
          </a>
        )}
      </span>
    </nav>
  );
}
