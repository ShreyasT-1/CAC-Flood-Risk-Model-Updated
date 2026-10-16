/** A small marker highlight for occasional emphasis in display copy. */
export const Highlight = ({ color = "#FFF9C4", children }: { color?: string; children: React.ReactNode }) => (
  <span className="hl" style={{ ["--hl" as string]: color }}>{children}</span>
);
