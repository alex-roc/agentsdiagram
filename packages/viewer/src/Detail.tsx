import type { Diagnostic, Node as IrNode } from "@agentsdiagram/protocol";
import { ICONS } from "./nodes";
import { KIND_LABELS } from "./model";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="d-row">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

export function Detail({
  node,
  diagnostics,
  onReveal,
  onClose,
}: {
  node: IrNode;
  diagnostics: Diagnostic[];
  onReveal: () => void;
  onClose: () => void;
}) {
  const a = node.attrs;
  const extra = Object.entries(a.extra);
  return (
    <aside className="panel detail" aria-label={`Details of ${node.name}`}>
      <header className="panel-head">
        <h2>
          <span aria-hidden="true">{ICONS[node.kind]}</span> {node.name}
        </h2>
        <button className="icon-btn" onClick={onClose} aria-label="Close details">
          ✕
        </button>
      </header>
      <dl>
        <Row label="Kind">{KIND_LABELS[node.kind]}</Row>
        <Row label="Framework">{node.framework}</Row>
        <Row label="Status">{node.status}</Row>
        {a.agent_class && <Row label="Class">{a.agent_class}</Row>}
        {a.model && <Row label="Model">{a.model}</Row>}
        {a.instructions && <Row label="Instructions"><pre>{a.instructions}</pre></Row>}
        {a.dynamic_instructions.length > 0 && <Row label="Dynamic instructions">{a.dynamic_instructions.join(", ")}</Row>}
        {a.description && <Row label="Description">{a.description}</Row>}
        {a.output_type && <Row label="Output type"><code>{a.output_type}</code></Row>}
        {a.deps_type && <Row label="Deps type"><code>{a.deps_type}</code></Row>}
        {a.signature && <Row label="Signature"><code>{a.signature}</code></Row>}
        {a.takes_ctx !== null && <Row label="takes_ctx">{String(a.takes_ctx)}</Row>}
        {a.url && <Row label="URL"><code>{a.url}</code></Row>}
        {a.command && <Row label="Command"><code>{a.command}</code></Row>}
        {a.docstring && <Row label="Docstring"><pre>{a.docstring}</pre></Row>}
        {a.badges.length > 0 && (
          <Row label="Badges">
            {a.badges.map((b) => (
              <span key={b} className="ad-badge">{b}</span>
            ))}
          </Row>
        )}
        {extra.length > 0 && (
          <Row label="Extra">
            <pre>{extra.map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`).join("\n")}</pre>
          </Row>
        )}
        {node.source && (
          <Row label="Source">
            <code>
              {node.source.file}:{node.source.range.start.line}
            </code>
          </Row>
        )}
      </dl>
      {node.source && (
        <button className="btn" onClick={onReveal}>
          Go to code
        </button>
      )}
      {diagnostics.length > 0 && (
        <>
          <h3>Node diagnostics</h3>
          <ul className="diag-list">
            {diagnostics.map((d, i) => (
              <li key={i} className={`sev-${d.severity}`}>
                <code>{d.code}</code> {d.message}
              </li>
            ))}
          </ul>
        </>
      )}
    </aside>
  );
}
