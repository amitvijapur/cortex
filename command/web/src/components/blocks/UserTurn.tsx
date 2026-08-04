// Cortex Command — a user turn in the transcript.

export function UserTurn({ text }: { text: string }): React.ReactNode {
  return (
    <div className="turn turn-user">
      <div className="turn-gutter mono">you</div>
      <div className="turn-body user-body">{text}</div>
    </div>
  );
}
