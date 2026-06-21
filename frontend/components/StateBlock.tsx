type StateBlockProps = {
  title: string;
  body: string;
  tone?: "loading" | "empty" | "error" | "success";
};

export function StateBlock({ title, body, tone = "empty" }: StateBlockProps) {
  return (
    <div className={`state-block state-block--${tone}`} role={tone === "error" ? "alert" : undefined}>
      <strong>{title}</strong>
      <p>{body}</p>
    </div>
  );
}
