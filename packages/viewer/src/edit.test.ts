import type { Node as IrNode, Project } from "@agentsdiagram/protocol";
import { describe, expect, it } from "vitest";
import sample from "../../protocol/fixtures/sample.json";
import { canDisconnect, connectionsOf, defaultAgentFile, expectFor, instructionsEditable, modelId } from "./model";

const project = sample as unknown as Project;
const agent = project.nodes.find((n) => n.kind === "agent" && n.source)!;
const fileOf = (n: IrNode) => n.source!.file;

describe("expectFor", () => {
  it("sends the hash of the agent's file", () => {
    const expect_ = expectFor(project, { op: "add_tool", agent: agent.id, name: "x" });
    const sha = project.files.find((f) => f.path === fileOf(agent))?.sha256;
    expect(expect_).toEqual(sha ? [{ file: fileOf(agent), sha256: sha }] : []);
  });

  it("covers both ends of a connection and the referencing files of a removal", () => {
    const other = project.nodes.find((n) => n.kind === "agent" && n.id !== agent.id && n.source)!;
    const files = expectFor(project, { op: "connect", source: agent.id, target: other.id }).map((v) => v.file);
    for (const f of new Set([fileOf(agent), fileOf(other)])) {
      if (project.files.some((x) => x.path === f)) expect(files).toContain(f);
    }
    const edge = project.edges.find((e) => e.ref && e.target !== e.source)!;
    const removal = expectFor(project, { op: "remove", node: edge.target }).map((v) => v.file);
    if (project.files.some((x) => x.path === edge.ref!.file)) expect(removal).toContain(edge.ref!.file);
  });

  it("ignores files the diagram has not seen (a new file)", () => {
    expect(expectFor(project, { op: "add_agent", framework: "smolagents", name: "a", file: "new.py" })).toEqual([]);
  });
});

describe("connections", () => {
  it("lists edges both ways without graph containment", () => {
    const list = connectionsOf(project, agent.id);
    expect(list.length).toBeGreaterThan(0);
    for (const c of list) {
      expect(c.edge.kind).not.toBe("contains");
      expect(c.outgoing ? c.edge.source : c.edge.target).toBe(agent.id);
    }
  });

  it("only offers to disconnect relations written as list items or decorators", () => {
    for (const e of project.edges) {
      const ok = canDisconnect(project, e);
      if (["contains", "transitions", "runs"].includes(e.kind) || !e.ref) expect(ok).toBe(false);
      const source = project.nodes.find((n) => n.id === e.source);
      if (e.kind === "delegates_to" && source?.kind === "tool") expect(ok).toBe(false);
    }
  });
});

describe("new agents and agent fields", () => {
  it("puts a new agent next to its parent, else with the framework's agents", () => {
    expect(defaultAgentFile(project, agent.framework, agent.id)).toBe(fileOf(agent));
    const first = project.nodes.find((n) => n.kind === "agent" && n.framework === agent.framework && n.source)!;
    expect(defaultAgentFile(project, agent.framework, null)).toBe(fileOf(first));
    expect(defaultAgentFile({ ...project, nodes: [] }, "smolagents", null)).toBe("agents.py");
  });

  it("reads the model id out of a smolagents model class", () => {
    const n = (model: string | null) => ({ ...agent, attrs: { ...agent.attrs, model } }) as IrNode;
    expect(modelId(n("InferenceClientModel('Qwen/Qwen3')"))).toBe("Qwen/Qwen3");
    expect(modelId(n("openai:gpt-5"))).toBe("openai:gpt-5");
    expect(modelId(n("LiteLLMModel(…)"))).toBe("");
    expect(modelId(n(null))).toBe("");
  });

  it("does not offer to edit truncated or computed instructions", () => {
    const n = (instructions: string, extra: Record<string, unknown> = {}) =>
      ({ ...agent, attrs: { ...agent.attrs, instructions, extra } }) as IrNode;
    expect(instructionsEditable(n("Be brief."))).toBe(true);
    expect(instructionsEditable(n("Very long…"))).toBe(false);
    expect(instructionsEditable(n("PROMPT", { instructions_code: true }))).toBe(false);
  });
});
