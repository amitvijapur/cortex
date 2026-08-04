// Cortex Command — the 4-square pixel logomark (from the observatory idiom).

export function Logomark({ size = 18 }: { size?: number }): React.ReactNode {
  return (
    <svg
      className="logomark"
      width={size}
      height={size}
      viewBox="0 0 18 18"
      aria-hidden="true"
    >
      <rect x="0" y="0" width="7" height="7" fill="#191919" />
      <rect x="11" y="0" width="7" height="7" fill="#191919" />
      <rect x="0" y="11" width="7" height="7" fill="#191919" />
      <rect x="11" y="11" width="7" height="7" fill="#191919" />
    </svg>
  );
}

/** The bordered empty-state mark used in empty panels. */
export function EmptyMark({ size = 26 }: { size?: number }): React.ReactNode {
  return (
    <svg
      className="empty-mark"
      width={size}
      height={size}
      viewBox="0 0 26 26"
      aria-hidden="true"
    >
      <rect x="0.5" y="0.5" width="25" height="25" fill="none" stroke="#191919" strokeWidth="1" />
      <rect x="6" y="6" width="6" height="6" fill="#191919" />
      <rect x="14" y="6" width="6" height="6" fill="#191919" />
      <rect x="6" y="14" width="6" height="6" fill="#191919" />
      <rect x="14" y="14" width="6" height="6" fill="#191919" />
    </svg>
  );
}
