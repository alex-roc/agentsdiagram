import type { Diagnostic, Node as IrNode } from "@agentsdiagram/protocol";
import { Icon } from "./icons";
import { KIND_LABELS } from "./model";

/** Flags the analyzer leaves for the viewer and the checks; not worth showing. */
const INTERNAL_EXTRA = new Set(["explicit_name", "instructions_code"]);

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
  children,
}: {
  node: IrNode;
  diagnostics: Diagnostic[];
  onReveal: () => void;
  onClose: () => void;
  /** Plan and edit actions, when the host can change the code. */
  children?: React.ReactNode;
}) {
  const a = node.attrs;
  const extra = Object.entries(a.extra).filter(([k]) => !INTERNAL_EXTRA.has(k));
  return (
    <section className={`panel detail kind-${node.kind}`} aria-label={`Details of ${node.name}`}>
      <header className="panel-head">
        <span className="ad-tile">
          <Icon name={node.kind} size={16} />
        </span>
        <div className="panel-title">
          <h2>{node.name}</h2>
          <p>
            {KIND_LABELS[node.kind]} in {node.framework === "pydantic_ai" ? "PydanticAI" : "smolagents"}
            {node.status !== "resolved" && <span className={`ad-status s-${node.status}`}>{node.status}</span>}
          </p>
        </div>
        <button className="icon-btn" onClick={onClose} aria-label="Close details" title="Close (Esc)">
          <Icon name="close" />
        </button>
      </header>
      {node.source && (
        <button className="btn primary block" onClick={onReveal}>
          <Icon name="code" />
          <span className="btn-label">Go to code</span>
          <span className="btn-meta">
            {node.source.file}:{node.source.range.start.line}
          </span>
        </button>
      )}
      <dl>
        {a.agent_class && <Row label="Class">{a.agent_class}</Row>}
        {a.model && <Row label="Model"><code>{a.model}</code></Row>}
        {a.instructions && <Row label="Instructions"><pre className="quote">{a.instructions}</pre></Row>}
        {a.dynamic_instructions.length > 0 && (
          <Row label="Dynamic instructions">
            {a.dynamic_instructions.map((d) => <code key={d} className="pill">{d}</code>)}
          </Row>
        )}
        {a.description && <Row label="Description">{a.description}</Row>}
        {a.output_type && <Row label="Output type"><code>{a.output_type}</code></Row>}
        {a.deps_type && <Row label="Deps type"><code>{a.deps_type}</code></Row>}
        {a.signature && <Row label="Signature"><code>{a.signature}</code></Row>}
        {a.takes_ctx !== null && <Row label="Takes context">{a.takes_ctx ? "Yes" : "No"}</Row>}
        {a.url && <Row label="URL"><code>{a.url}</code></Row>}
        {a.command && <Row label="Command"><code>{a.command}</code></Row>}
        {a.docstring && <Row label="Docstring"><pre className="quote">{a.docstring}</pre></Row>}
        {a.badges.length > 0 && (
          <Row label="Badges">
            {a.badges.map((b) => (
              <span key={b} className="ad-badge">{b}</span>
            ))}
          </Row>
        )}
        {extra.length > 0 && (
          <Row label="More">
            <pre>{extra.map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`).join("\n")}</pre>
          </Row>
        )}
      </dl>
      {children}
      {diagnostics.length > 0 && (
        <>
          <h3>{diagnostics.some((d) => d.severity !== "info") ? "Problems in this node" : "Notes"}</h3>
          <ul className="diag-list">
            {diagnostics.map((d, i) => (
              <li key={i} className={`sev-${d.severity}`}>
                <span className="diag-msg">{d.message}</span>
                <code className="diag-code">{d.code}</code>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
