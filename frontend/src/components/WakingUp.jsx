export default function WakingUp() {
  return (
    <div className="waking-up">
      <div className="waking-up-spinner" aria-hidden="true" />
      <div>
        <div className="waking-up-title">Waking up the demo</div>
        <div className="waking-up-sub">
          This runs on a free-tier server that sleeps when idle. First response can
          take up to ~30 seconds &mdash; it's not stuck.
        </div>
      </div>
    </div>
  );
}
