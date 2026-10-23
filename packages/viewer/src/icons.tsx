// Line icons on a 16px grid (1.5px stroke, currentColor). Drawn for agentsdiagram, no icon library.
import type { Kind } from "./model";

type Extra = "search" | "problems" | "copy" | "check" | "sun" | "moon" | "close" | "code" | "filter";
type EditIcons = "plus" | "link" | "unlink" | "edit" | "trash";

const PATHS: Record<Kind | Extra | EditIcons, string> = {
  // a head with an antenna and two eyes
  agent: "M8 1.8v2.2 M4 4h8a1.5 1.5 0 0 1 1.5 1.5v6A1.5 1.5 0 0 1 12 13H4a1.5 1.5 0 0 1-1.5-1.5v-6A1.5 1.5 0 0 1 4 4z M6 8.2v.6 M10 8.2v.6 M6.2 10.8h3.6",
  // a wrench
  tool: "M10.4 2.2a3.2 3.2 0 0 0-3.9 4.2L2.4 10.5a1.5 1.5 0 0 0 2.1 2.1l4.1-4.1a3.2 3.2 0 0 0 4.2-3.9l-2 2-1.8-.5-.5-1.8z",
  // three stacked layers
  toolset: "M8 2 14 5 8 8 2 5z M2 8l6 3 6-3 M2 11l6 3 6-3",
  // a plug
  mcp_server: "M5.5 1.5v3 M10.5 1.5v3 M3.5 4.5h9v2.5a4.5 4.5 0 0 1-9 0z M8 11.5v3",
  // a gear-like chip
  native_tool: "M5 3h6a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z M6.5 6.5h3v3h-3z M6 1v2 M10 1v2 M6 13v2 M10 13v2 M1 6h2 M1 10h2 M13 6h2 M13 10h2",
  // a spark
  capability: "M8 1.5 9.4 6.6 14.5 8 9.4 9.4 8 14.5 6.6 9.4 1.5 8 6.6 6.6z",
  // a branching arrow
  workflow: "M3 2.5v11 M3 8h5a3 3 0 0 0 3-3V2.5 M9 4.5l2-2 2 2 M3 8h5a3 3 0 0 1 3 3v2.5",
  // a globe
  external_tool_source: "M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13z M1.5 8h13 M8 1.5c1.8 1.8 2.6 4 2.6 6.5S9.8 12.7 8 14.5C6.2 12.7 5.4 10.5 5.4 8S6.2 3.3 8 1.5z",
  // connected nodes
  graph: "M3.5 2a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z M12.5 6.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z M3.5 11a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z M5 3.8l6 3.6 M5 12.2l6-3.6",
  // a step: a small diamond
  graph_step: "M8 2.5 13.5 8 8 13.5 2.5 8z",
  // a dashed question mark
  dynamic: "M5.8 5.6A2.3 2.3 0 0 1 10.3 6c0 1.6-2.3 1.9-2.3 3.4 M8 12v.4",
  search: "M7 2.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9z M10.3 10.3l3.2 3.2",
  problems: "M8 2 14.5 13.5h-13z M8 6.5v3 M8 11.5v.3",
  copy: "M5.5 5.5h7v8h-7z M3.5 10.5v-8h7",
  check: "M3 8.5l3 3 7-7",
  sun: "M8 5a3 3 0 1 0 0 6 3 3 0 0 0 0-6z M8 1v1.5 M8 13.5V15 M1 8h1.5 M13.5 8H15 M3 3l1 1 M12 12l1 1 M3 13l1-1 M12 4l1-1",
  moon: "M13.5 9.5A5.5 5.5 0 0 1 6.5 2.5a5.5 5.5 0 1 0 7 7z",
  close: "M4 4l8 8 M12 4l-8 8",
  code: "M5.5 4.5 2 8l3.5 3.5 M10.5 4.5 14 8l-3.5 3.5",
  filter: "M2 3.5h12 M4.5 8h7 M6.5 12.5h3",
  plus: "M8 3v10 M3 8h10",
  // two chain links, and the same links apart
  link: "M7 9a2.5 2.5 0 0 0 3.5 0l2.3-2.3a2.5 2.5 0 0 0-3.5-3.5L8.6 3.9 M9 7a2.5 2.5 0 0 0-3.5 0L3.2 9.3a2.5 2.5 0 0 0 3.5 3.5l.7-.7",
  unlink: "M9.3 3.2a2.5 2.5 0 0 1 3.5 3.5L11.3 8.2 M6.7 12.8a2.5 2.5 0 0 1-3.5-3.5l1.5-1.5 M2.5 2.5l2 2 M13.5 13.5l-2-2",
  edit: "M10.5 2.5l3 3L6 13H3v-3z M9 4l3 3",
  trash: "M2.5 4.5h11 M6.5 4.5V3h3v1.5 M4 4.5l.7 9h6.6l.7-9 M6.8 7v4.5 M9.2 7v4.5",
};

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 16, className }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
