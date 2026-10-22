import type { Project } from "@agentsdiagram/protocol";
import { describe, expect, it } from "vitest";
import sample from "../../protocol/fixtures/sample.json";
import { layoutGraph } from "./layout";
import { buildFlow, edgeLabel, kindsPresent, searchNodes, subtitleOf } from "./model";
import { revealUrl, toGraphResult } from "./transport";

const project = sample as unknown as Project;

describe("buildFlow", () => {
  const g = buildFlow(project);

  it("keeps every node and drops contains edges", () => {
    expect(g.nodes).toHaveLength(project.nodes.length);
    expect(g.edges.some((e) => e.data.ir.kind === "contains")).toBe(false);
    expect(g.edges).toHaveLength(project.edges.filter((e) => e.kind !== "contains").length);
  });

  it("nests graph_steps in their graph, parents first", () => {
    const steps = g.nodes.filter((n) => n.type === "graph_step");
    expect(steps.length).toBeGreaterThan(0);
    for (const s of steps) {
      const parent = g.nodes.find((n) => n.id === s.parentId);
      expect(parent?.type).toBe("graph");
      expect(g.nodes.indexOf(parent!)).toBeLessThan(g.nodes.indexOf(s));
    }
  });

  it("filters by kind and drops dangling edges", () => {
    const f = buildFlow(project, { hiddenKinds: new Set(["mcp_server", "graph"] as const) });
    expect(f.nodes.some((n) => n.type === "mcp_server" || n.type === "graph")).toBe(false);
    const ids = new Set(f.nodes.map((n) => n.id));
    expect(f.edges.every((e) => ids.has(e.source) && ids.has(e.target))).toBe(true);
    // without their graph, steps become top-level nodes
    expect(f.nodes.filter((n) => n.type === "graph_step").every((n) => !n.parentId)).toBe(true);
  });

  it("highlights delegation and management edges", () => {
    const hot = g.edges.filter((e) => ["delegates_to", "manages"].includes(e.data.ir.kind));
    expect(hot.length).toBeGreaterThan(0);
    expect(hot.every((e) => e.animated)).toBe(true);
  });
});

describe("labels and subtitles", () => {
  it("combines order, label and wrappers", () => {
    const base = project.edges[0]!;
    expect(edgeLabel({ ...base, label: "x", order: 2, wrappers: ["prefixed('a')"] })).toBe("#2 x prefixed('a')");
    expect(edgeLabel({ ...base, label: null, order: null, wrappers: [] })).toBeUndefined();
  });

  it("uses model for agents and url/command for MCP", () => {
    const agent = project.nodes.find((n) => n.kind === "agent" && n.attrs.model)!;
    expect(subtitleOf(agent)).toBe(agent.attrs.model);
    const mcp = project.nodes.find((n) => n.kind === "mcp_server")!;
    expect(subtitleOf(mcp)).toBe(mcp.attrs.url ?? mcp.attrs.command);
  });
});

describe("search and kinds", () => {
  it("matches names case-insensitively; empty query matches nothing", () => {
    const g = buildFlow(project);
    expect(searchNodes(g.nodes, "")).toEqual([]);
    const first = project.nodes[0]!;
    expect(searchNodes(g.nodes, first.name.toUpperCase())).toContain(first.id);
  });

  it("lists present kinds", () => {
    expect(kindsPresent(project)).toContain("agent");
  });
});

describe("layoutGraph", () => {
  const g = layoutGraph(buildFlow(project));

  it("sizes groups to contain their children", () => {
    for (const grp of g.nodes.filter((n) => n.type === "graph")) {
      const kids = g.nodes.filter((n) => n.parentId === grp.id);
      for (const k of kids) {
        expect(k.position.x + k.width!).toBeLessThanOrEqual(grp.width!);
        expect(k.position.y + k.height!).toBeLessThanOrEqual(grp.height!);
      }
    }
  });

  it("does not stack top-level nodes on one spot", () => {
    const spots = new Set(g.nodes.filter((n) => !n.parentId).map((n) => `${n.position.x},${n.position.y}`));
    expect(spots.size).toBeGreaterThan(g.nodes.filter((n) => !n.parentId).length / 2);
  });

  it("gives every node a finite position", () => {
    expect(g.nodes.every((n) => Number.isFinite(n.position.x) && Number.isFinite(n.position.y))).toBe(true);
  });
});

describe("transport helpers", () => {
  it("wraps a bare Project", () => {
    expect(toGraphResult(project).project).toBe(project);
  });
  it("builds vscode:// links with 1-based column", () => {
    expect(revealUrl("/a/b/", "x/y.py", 3, 0)).toBe("vscode://file/a/b/x/y.py:3:1");
  });
});
