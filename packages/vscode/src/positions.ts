import type { Node, Range as IrRange } from "@agentsdiagram/protocol/src/ir";
import * as vscode from "vscode";

/** IR columns are 0-based code points; VS Code wants UTF-16 code units. */
export function codePointsToUtf16(line: string, column: number): number {
  let units = 0;
  let points = 0;
  for (const ch of line) {
    if (points >= column) break;
    units += ch.length;
    points++;
  }
  return units;
}

export function utf16ToCodePoints(line: string, character: number): number {
  return Array.from(line.slice(0, character)).length;
}

export function irRangeToVsCode(doc: vscode.TextDocument, range: IrRange): vscode.Range {
  const pos = (p: IrRange["start"]) => {
    const line = Math.min(Math.max(p.line - 1, 0), doc.lineCount - 1);
    return new vscode.Position(line, codePointsToUtf16(doc.lineAt(line).text, p.column));
  };
  return new vscode.Range(pos(range.start), pos(range.end));
}

const cmp = (a: IrRange["start"], b: IrRange["start"]) => a.line - b.line || a.column - b.column;

/** Innermost node (smallest range) of `file` whose source range contains the IR position. */
export function innermostNode(nodes: Node[], file: string, at: IrRange["start"]): Node | null {
  let best: Node | null = null;
  for (const node of nodes) {
    const src = node.source;
    if (!src || src.file !== file) continue;
    if (cmp(src.range.start, at) > 0 || cmp(at, src.range.end) > 0) continue;
    if (!best || (cmp(best.source!.range.start, src.range.start) <= 0 && cmp(src.range.end, best.source!.range.end) <= 0)) {
      best = node;
    }
  }
  return best;
}
