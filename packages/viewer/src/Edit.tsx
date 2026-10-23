// Plan and edit from the diagram. Every form sends one EditRequest; the host writes the code
// (VS Code applies a WorkspaceEdit, `agentsdiagram serve` writes the files) and the diagram is
// redrawn from the new code. The viewer keeps no state of its own.
import type { EditRequest, EditResult, Node as IrNode, Project } from "@agentsdiagram/protocol";
import { useId, useState, type FormEvent, type ReactNode } from "react";
import { Icon } from "./icons";
import { canDisconnect, connectionsOf, defaultAgentFile, instructionsEditable, KIND_LABELS, modelId } from "./model";

export type RunEdit = (request: EditRequest) => Promise<EditResult>;

const IDENT = "[A-Za-z_][A-Za-z0-9_]*";
const FW_LABEL: Record<IrNode["framework"], string> = { smolagents: "smolagents", pydantic_ai: "PydanticAI" };

function Field({ label, hint, children }: { label: string; hint?: string; children: (id: string) => ReactNode }) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children(id)}
      {hint && <p className="hint">{hint}</p>}
    </div>
  );
}

function useSubmit(run: RunEdit, onDone: () => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const send = async (e: FormEvent, request: EditRequest | null) => {
    e.preventDefault();
    if (!request || busy) return;
    setBusy(true);
    setError(null);
    const result = await run(request);
    setBusy(false);
    if (result.ok) onDone();
    else setError(result.message);
  };
  return { busy, error, send };
}

function ErrorLine({ error }: { error: string | null }) {
  return error ? (
    <p className="form-error" role="alert">
      {error}
    </p>
  ) : null;
}

// ---------------------------------------------------------------- new agent

export function PlanAgentPanel({
  project,
  parent,
  run,
  onClose,
}: {
  project: Project;
  parent: IrNode | null;
  run: RunEdit;
  onClose: () => void;
}) {
  const frameworks: IrNode["framework"][] = parent
    ? [parent.framework]
    : project.frameworks.length
      ? [...project.frameworks].sort((a) => (a === "smolagents" ? -1 : 1))
      : ["smolagents", "pydantic_ai"];
  const [framework, setFramework] = useState<IrNode["framework"]>(frameworks[0]!);
  const [parentId, setParentId] = useState<string>(parent?.id ?? "");
  const [name, setName] = useState("");
  const [agentClass, setAgentClass] = useState<"CodeAgent" | "ToolCallingAgent">(parent ? "ToolCallingAgent" : "CodeAgent");
  const [model, setModel] = useState("");
  const [description, setDescription] = useState("");
  const [instructions, setInstructions] = useState("");
  const [file, setFile] = useState(defaultAgentFile(project, frameworks[0]!, parent?.id ?? null));
  const { busy, error, send } = useSubmit(run, onClose);
  const agents = project.nodes.filter((n) => n.kind === "agent" && n.framework === framework);
  const files = [...new Set(project.nodes.filter((n) => n.framework === framework && n.source).map((n) => n.source!.file))];
  const smol = framework === "smolagents";
  const listId = useId();

  const changeFramework = (fw: IrNode["framework"]) => {
    setFramework(fw);
    setParentId("");
    setFile(defaultAgentFile(project, fw, null));
  };
  const changeParent = (id: string) => {
    setParentId(id);
    setFile(defaultAgentFile(project, framework, id || null));
    if (smol) setAgentClass(id ? "ToolCallingAgent" : "CodeAgent");
  };

  return (
    <section className="panel" aria-label="Plan an agent">
      <header className="panel-head">
        <span className="ad-tile plan-tile">
          <Icon name="plus" size={16} />
        </span>
        <div className="panel-title">
          <h2>Plan an agent</h2>
          <p>It is written to your code as a planned agent, ready to fill in.</p>
        </div>
        <button className="icon-btn" onClick={onClose} aria-label="Close" title="Close (Esc)">
          <Icon name="close" />
        </button>
      </header>
      <form
        className="form"
        onSubmit={(e) =>
          void send(e, {
            op: "add_agent",
            framework,
            name: name.trim(),
            file: file.trim(),
            parent: parentId || null,
            model: model.trim() || null,
            description: description.trim() || null,
            instructions: instructions.trim() || null,
            agent_class: smol ? agentClass : null,
          })
        }
      >
        {frameworks.length > 1 && (
          <Field label="Framework">
            {(id) => (
              <select id={id} value={framework} onChange={(e) => changeFramework(e.target.value as IrNode["framework"])}>
                {frameworks.map((fw) => (
                  <option key={fw} value={fw}>
                    {FW_LABEL[fw]}
                  </option>
                ))}
              </select>
            )}
          </Field>
        )}
        <Field label="Name" hint="A Python variable name, e.g. researcher.">
          {(id) => (
            <input id={id} required pattern={IDENT} value={name} onChange={(e) => setName(e.target.value)} autoFocus spellCheck={false} />
          )}
        </Field>
        {smol && (
          <Field label="Kind">
            {(id) => (
              <select id={id} value={agentClass} onChange={(e) => setAgentClass(e.target.value as "CodeAgent" | "ToolCallingAgent")}>
                <option value="CodeAgent">CodeAgent (writes Python)</option>
                <option value="ToolCallingAgent">ToolCallingAgent (calls tools as JSON)</option>
              </select>
            )}
          </Field>
        )}
        {agents.length > 0 && (
          <Field
            label={smol ? "Managed by" : "Delegated from"}
            hint={smol ? "Added to its managed_agents." : "It gets a tool that runs the new agent."}
          >
            {(id) => (
              <select id={id} value={parentId} onChange={(e) => changeParent(e.target.value)}>
                <option value="">Nobody (a top-level agent)</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            )}
          </Field>
        )}
        <Field label="Description" hint={smol && parentId ? "Its manager reads this to decide when to call it." : undefined}>
          {(id) => <input id={id} value={description} onChange={(e) => setDescription(e.target.value)} />}
        </Field>
        <Field label="Instructions">
          {(id) => <textarea id={id} rows={3} value={instructions} onChange={(e) => setInstructions(e.target.value)} />}
        </Field>
        <Field label="Model" hint={smol ? "A model id; empty reuses the file's model." : "Empty reuses the model of your other agents."}>
          {(id) => (
            <input
              id={id}
              value={model}
              placeholder={smol ? "Qwen/Qwen3-Coder-30B-A3B-Instruct" : "openai:gpt-5-mini"}
              onChange={(e) => setModel(e.target.value)}
              spellCheck={false}
            />
          )}
        </Field>
        <Field label="File" hint="Relative to the project; created if it does not exist.">
          {(id) => (
            <>
              <input id={id} required list={listId} value={file} onChange={(e) => setFile(e.target.value)} spellCheck={false} />
              <datalist id={listId}>
                {files.map((f) => (
                  <option key={f} value={f} />
                ))}
              </datalist>
            </>
          )}
        </Field>
        <ErrorLine error={error} />
        <div className="form-actions">
          <button type="submit" className="btn primary" disabled={busy}>
            {busy ? "Writing…" : "Write planned agent"}
          </button>
          <button type="button" className="btn ghost" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}

// ---------------------------------------------------------------- actions on a node

type Action = "tool" | "mcp" | "connect" | "model" | "instructions" | null;

export function NodeActions({
  node,
  project,
  run,
  onPlanChild,
  onSelect,
}: {
  node: IrNode;
  project: Project;
  run: RunEdit;
  onPlanChild: (parent: IrNode) => void;
  onSelect: (id: string) => void;
}) {
  const [action, setAction] = useState<Action>(null);
  const close = () => setAction(null);
  const agent = node.kind === "agent";
  const removable = !["graph", "graph_step", "workflow"].includes(node.kind);
  return (
    <>
      {agent && (
        <>
          <h3>Plan and edit</h3>
          {action === null && (
            <div className="actions">
              <button className="btn ghost" onClick={() => setAction("tool")}>
                <Icon name="tool" size={14} /> Add tool
              </button>
              <button className="btn ghost" onClick={() => setAction("mcp")}>
                <Icon name="mcp_server" size={14} /> Add MCP server
              </button>
              <button className="btn ghost" onClick={() => onPlanChild(node)}>
                <Icon name="plus" size={14} /> {node.framework === "smolagents" ? "Plan managed agent" : "Plan specialist"}
              </button>
              <button className="btn ghost" onClick={() => setAction("connect")}>
                <Icon name="link" size={14} /> Hand work to…
              </button>
              <button className="btn ghost" onClick={() => setAction("model")}>
                <Icon name="edit" size={14} /> Change model
              </button>
              <button className="btn ghost" onClick={() => setAction("instructions")}>
                <Icon name="edit" size={14} /> Instructions
              </button>
              {node.framework === "pydantic_ai" && node.attrs.agent_class === "Agent" && <ExportSpecButton node={node} run={run} />}
            </div>
          )}
          {action === "tool" && <AddToolForm node={node} run={run} onClose={close} />}
          {action === "mcp" && <AddMcpForm node={node} run={run} onClose={close} />}
          {action === "connect" && <ConnectForm node={node} project={project} run={run} onClose={close} />}
          {action === "model" && <ModelForm node={node} run={run} onClose={close} />}
          {action === "instructions" && <InstructionsForm node={node} run={run} onClose={close} />}
        </>
      )}
      <Connections node={node} project={project} run={run} onSelect={onSelect} />
      {removable && action === null && <RemoveButton node={node} run={run} />}
    </>
  );
}

function AddToolForm({ node, run, onClose }: { node: IrNode; run: RunEdit; onClose: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [params, setParams] = useState("");
  const [returns, setReturns] = useState("");
  const { busy, error, send } = useSubmit(run, onClose);
  return (
    <form
      className="form"
      onSubmit={(e) =>
        void send(e, {
          op: "add_tool",
          agent: node.id,
          name: name.trim(),
          description: description.trim() || null,
          params: params.trim() || null,
          returns: returns.trim() || null,
        })
      }
    >
      <p className="form-lead">A planned tool: a typed stub that raises NotImplementedError until you write it.</p>
      <Field label="Function name">
        {(id) => <input id={id} required pattern={IDENT} value={name} onChange={(e) => setName(e.target.value)} autoFocus spellCheck={false} />}
      </Field>
      <Field label="What it does" hint="Becomes the docstring the model reads.">
        {(id) => <input id={id} value={description} onChange={(e) => setDescription(e.target.value)} />}
      </Field>
      <Field label="Parameters">
        {(id) => <input id={id} value={params} placeholder="query: str" onChange={(e) => setParams(e.target.value)} spellCheck={false} />}
      </Field>
      <Field label="Returns">
        {(id) => <input id={id} value={returns} placeholder="str" onChange={(e) => setReturns(e.target.value)} spellCheck={false} />}
      </Field>
      <ErrorLine error={error} />
      <FormButtons busy={busy} submit="Write stub" onCancel={onClose} />
    </form>
  );
}

function AddMcpForm({ node, run, onClose }: { node: IrNode; run: RunEdit; onClose: () => void }) {
  const [mode, setMode] = useState<"url" | "command">("url");
  const [value, setValue] = useState("");
  const [name, setName] = useState("");
  const { busy, error, send } = useSubmit(run, onClose);
  return (
    <form
      className="form"
      onSubmit={(e) =>
        void send(e, {
          op: "add_mcp",
          agent: node.id,
          url: mode === "url" ? value.trim() : null,
          command: mode === "command" ? value.trim() : null,
          name: name.trim() || null,
        })
      }
    >
      <div className="segmented" role="radiogroup" aria-label="How to reach the server">
        {(["url", "command"] as const).map((m) => (
          <button key={m} type="button" role="radio" aria-checked={mode === m} className={mode === m ? "on" : ""} onClick={() => setMode(m)}>
            {m === "url" ? "URL (HTTP)" : "Command (stdio)"}
          </button>
        ))}
      </div>
      <Field label={mode === "url" ? "Server URL" : "Command line"}>
        {(id) => (
          <input
            id={id}
            required
            value={value}
            placeholder={mode === "url" ? "https://example.com/mcp" : "uvx mcp-server-fetch"}
            onChange={(e) => setValue(e.target.value)}
            autoFocus
            spellCheck={false}
          />
        )}
      </Field>
      <Field label="Variable name" hint="Optional; derived from the URL or command.">
        {(id) => <input id={id} pattern={IDENT} value={name} onChange={(e) => setName(e.target.value)} spellCheck={false} />}
      </Field>
      <ErrorLine error={error} />
      <FormButtons busy={busy} submit="Connect server" onCancel={onClose} />
    </form>
  );
}

function ConnectForm({ node, project, run, onClose }: { node: IrNode; project: Project; run: RunEdit; onClose: () => void }) {
  const others = project.nodes.filter((n) => n.kind === "agent" && n.framework === node.framework && n.id !== node.id);
  const [target, setTarget] = useState(others[0]?.id ?? "");
  const { busy, error, send } = useSubmit(run, onClose);
  if (!others.length) {
    return (
      <div className="form">
        <p className="form-lead">There is no other {FW_LABEL[node.framework]} agent yet. Plan one first.</p>
        <FormButtons busy={false} onCancel={onClose} />
      </div>
    );
  }
  return (
    <form className="form" onSubmit={(e) => void send(e, { op: "connect", source: node.id, target })}>
      <p className="form-lead">
        {node.framework === "smolagents"
          ? `Adds the agent to ${node.name}'s managed_agents.`
          : `Writes a tool on ${node.name} that runs the other agent and returns its answer.`}
      </p>
      <Field label="Agent">
        {(id) => (
          <select id={id} value={target} onChange={(e) => setTarget(e.target.value)} autoFocus>
            {others.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        )}
      </Field>
      <ErrorLine error={error} />
      <FormButtons busy={busy} submit="Connect" onCancel={onClose} />
    </form>
  );
}

function ModelForm({ node, run, onClose }: { node: IrNode; run: RunEdit; onClose: () => void }) {
  const [model, setModel] = useState(modelId(node));
  const { busy, error, send } = useSubmit(run, onClose);
  return (
    <form className="form" onSubmit={(e) => void send(e, { op: "set_model", agent: node.id, model: model.trim() })}>
      <Field label="Model" hint={node.framework === "smolagents" ? "The model_id of this agent's model." : "Provider and model, e.g. anthropic:claude-sonnet-5-5."}>
        {(id) => <input id={id} required value={model} onChange={(e) => setModel(e.target.value)} autoFocus spellCheck={false} />}
      </Field>
      <ErrorLine error={error} />
      <FormButtons busy={busy} submit="Save model" onCancel={onClose} />
    </form>
  );
}

function InstructionsForm({ node, run, onClose }: { node: IrNode; run: RunEdit; onClose: () => void }) {
  const editable = instructionsEditable(node);
  const [text, setText] = useState(editable ? (node.attrs.instructions ?? "") : "");
  const { busy, error, send } = useSubmit(run, onClose);
  if (!editable) {
    return (
      <div className="form">
        <p className="form-lead">These instructions are long or built in code; edit them there so nothing is lost.</p>
        <FormButtons busy={false} onCancel={onClose} />
      </div>
    );
  }
  return (
    <form className="form" onSubmit={(e) => void send(e, { op: "set_instructions", agent: node.id, instructions: text })}>
      <Field label="Instructions" hint="Empty removes them.">
        {(id) => <textarea id={id} rows={5} value={text} onChange={(e) => setText(e.target.value)} autoFocus />}
      </Field>
      <ErrorLine error={error} />
      <FormButtons busy={busy} submit="Save instructions" onCancel={onClose} />
    </form>
  );
}

function FormButtons({ busy, submit, onCancel }: { busy: boolean; submit?: string; onCancel: () => void }) {
  return (
    <div className="form-actions">
      {submit && (
        <button type="submit" className="btn primary" disabled={busy}>
          {busy ? "Writing…" : submit}
        </button>
      )}
      <button type="button" className="btn ghost" onClick={onCancel}>
        {submit ? "Cancel" : "Close"}
      </button>
    </div>
  );
}

function ExportSpecButton({ node, run }: { node: IrNode; run: RunEdit }) {
  const [error, setError] = useState<string | null>(null);
  return (
    <>
      <button
        className="btn ghost"
        title="Move model, name, instructions and literal capabilities to a YAML Agent Spec loaded with Agent.from_file"
        onClick={() => void run({ op: "export_spec", agent: node.id, replace: true }).then((r) => setError(r.ok ? null : r.message))}
      >
        <Icon name="code" size={14} /> Move to Agent Spec
      </button>
      <ErrorLine error={error} />
    </>
  );
}

function RemoveButton({ node, run }: { node: IrNode; run: RunEdit }) {
  const [armed, setArmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const what = KIND_LABELS[node.kind].toLowerCase();
  return (
    <div className="remove">
      {armed ? (
        <div className="confirm" role="group" aria-label={`Remove ${node.name}`}>
          <span>Remove {node.name} from the code?</span>
          <button
            className="btn danger"
            onClick={() =>
              void run({ op: "remove", node: node.id }).then((r) => {
                setArmed(false);
                setError(r.ok ? null : r.message);
              })
            }
          >
            Remove
          </button>
          <button className="btn ghost" onClick={() => setArmed(false)}>
            Keep
          </button>
        </div>
      ) : (
        <button className="btn ghost danger-text" onClick={() => setArmed(true)}>
          <Icon name="trash" size={14} /> Remove {what}
        </button>
      )}
      <ErrorLine error={error} />
    </div>
  );
}

const EDGE_VERB: Record<string, [string, string]> = {
  uses: ["uses", "used by"],
  provides: ["provides", "provided by"],
  wraps: ["wraps", "wrapped by"],
  delegates_to: ["hands work to", "gets work from"],
  manages: ["manages", "managed by"],
  runs: ["runs", "run by"],
  transitions: ["goes to", "comes from"],
};

function Connections({ node, project, run, onSelect }: { node: IrNode; project: Project; run: RunEdit; onSelect: (id: string) => void }) {
  const list = connectionsOf(project, node.id);
  const [error, setError] = useState<string | null>(null);
  if (!list.length) return null;
  return (
    <>
      <h3>Connections</h3>
      <ul className="conn-list">
        {list.map(({ edge, other, outgoing }) => (
          <li key={edge.id + (outgoing ? ">" : "<")}>
            <span className="conn-verb">{EDGE_VERB[edge.kind]?.[outgoing ? 0 : 1] ?? edge.kind}</span>
            <button className={`conn-node kind-${other.kind}`} onClick={() => onSelect(other.id)} title={`Show ${other.name}`}>
              <Icon name={other.kind} size={12} />
              <span>{other.name}</span>
            </button>
            {canDisconnect(project, edge) && (
              <button
                className="icon-btn small"
                aria-label={`Disconnect ${node.name} and ${other.name}`}
                title="Disconnect (edits the code)"
                onClick={() => void run({ op: "disconnect", edge: edge.id }).then((r) => setError(r.ok ? null : r.message))}
              >
                <Icon name="unlink" size={13} />
              </button>
            )}
          </li>
        ))}
      </ul>
      <ErrorLine error={error} />
    </>
  );
}

