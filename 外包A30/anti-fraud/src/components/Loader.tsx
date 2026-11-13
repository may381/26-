import './Loader.css';

/** Three staggered spinning tops. No IDs, so multiple loaders can coexist. */
export default function Loader({ label = '正在加载…' }: { label?: string }) {
  return <div className="loading-status" role="status" aria-live="polite">
    <span className="loader-frame" aria-hidden="true">
      <span className="loader">
        {[1, 2, 3].map(n => <svg key={n} className={`pegtop pegtop-${n}`} viewBox="0 0 100 110" fill="none">
          <g>
            <path d="M8 42 50 20 92 42 50 99Z" />
            <path d="M8 42 50 64 92 42M50 64V99" stroke="#cab6ee" strokeWidth="2" strokeLinejoin="round" />
            <path d="M8 42 50 20 92 42 50 99 8 42Z" stroke="#ad8ad7" strokeWidth="2" strokeLinejoin="round" />
            <path d="M50 7V28" stroke="#eadcff" strokeWidth="5" strokeLinecap="round" />
            <path d="M27 43 50 31 73 43 50 55Z" fill="#a17ad0" />
          </g>
        </svg>)}
      </span>
    </span>
    <span>{label}</span>
  </div>;
}
