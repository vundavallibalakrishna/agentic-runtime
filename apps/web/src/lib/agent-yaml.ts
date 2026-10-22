/** A small YAML subset so the form and the definition text stay in sync. */

export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

function quote(value: string): string {
  return `"${value.replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n")}"`;
}

function emit(value: JsonValue, indent: number): string {
  const pad = "  ".repeat(indent);
  if (value === null) {
    return "null";
  }
  if (typeof value === "boolean" || typeof value === "number") {
    return String(value);
  }
  if (typeof value === "string") {
    return quote(value);
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return "[]";
    }
    return value
      .map((item) => {
        if (item && typeof item === "object" && !Array.isArray(item)) {
          const body = emit(item, 0);
          const [first, ...rest] = body.split("\n");
          const head = `${pad}- ${first ?? ""}`;
          const tail = rest.map((line) => `${pad}  ${line}`).join("\n");
          return tail ? `${head}\n${tail}` : head;
        }
        return `${pad}- ${emit(item, 0)}`;
      })
      .join("\n");
  }
  const entries = Object.entries(value);
  if (entries.length === 0) {
    return "{}";
  }
  return entries
    .map(([key, item]) => {
      if (item && typeof item === "object") {
        const nested = emit(item, indent + 1);
        if (nested === "[]" || nested === "{}") {
          return `${pad}${key}: ${nested}`;
        }
        return `${pad}${key}:\n${nested}`;
      }
      return `${pad}${key}: ${emit(item, 0)}`;
    })
    .join("\n");
}

export function definitionToYaml(value: JsonValue): string {
  return `${emit(value, 0)}\n`;
}

function unquote(token: string): JsonValue {
  const trimmed = token.trim();
  if (trimmed === "null") {
    return null;
  }
  if (trimmed === "true") {
    return true;
  }
  if (trimmed === "false") {
    return false;
  }
  if (trimmed === "[]") {
    return [];
  }
  if (trimmed === "{}") {
    return {};
  }
  if (/^-?\d+(\.\d+)?$/.test(trimmed)) {
    return Number(trimmed);
  }
  if (trimmed.startsWith('"') && trimmed.endsWith('"')) {
    return trimmed.slice(1, -1).replace(/\\n/g, "\n").replace(/\\"/g, '"').replace(/\\\\/g, "\\");
  }
  throw new Error("YAML value is not valid");
}

type Line = { indent: number; text: string };

function linesOf(source: string): Line[] {
  return source
    .split("\n")
    .map((text) => ({ indent: text.match(/^ */)?.[0].length ?? 0, text: text.trim() }))
    .filter((line) => line.text.length > 0 && !line.text.startsWith("#"));
}

function lineAt(lines: Line[], index: number): Line | undefined {
  return lines[index];
}

function parseBlock(
  lines: Line[],
  index: number,
  indent: number,
): { value: JsonValue; index: number } {
  const first = lineAt(lines, index);
  if (!first || first.indent < indent) {
    return { value: {}, index };
  }
  if (first.text.startsWith("- ")) {
    const items: JsonValue[] = [];
    let cursor = index;
    while (
      lineAt(lines, cursor)?.indent === indent &&
      lineAt(lines, cursor)?.text.startsWith("- ")
    ) {
      const current = lineAt(lines, cursor);
      if (!current) {
        break;
      }
      const rest = current.text.slice(2);
      cursor += 1;
      if (rest.includes(": ") || rest.endsWith(":")) {
        const childIndent = current.indent + 2;
        const mappingLines: Line[] = [{ indent: childIndent, text: rest }];
        let child = lineAt(lines, cursor);
        while (
          child &&
          child.indent >= childIndent &&
          !(child.indent === indent && child.text.startsWith("- "))
        ) {
          mappingLines.push(child);
          cursor += 1;
          child = lineAt(lines, cursor);
        }
        items.push(parseMapping(mappingLines, 0, childIndent).value);
      } else {
        items.push(unquote(rest));
      }
    }
    return { value: items, index: cursor };
  }
  return parseMapping(lines, index, indent);
}

function parseMapping(
  lines: Line[],
  index: number,
  indent: number,
): { value: JsonValue; index: number } {
  const body: Record<string, JsonValue> = {};
  let cursor = index;
  while (lineAt(lines, cursor)?.indent === indent) {
    const current = lineAt(lines, cursor);
    if (!current) {
      break;
    }
    const splitAt = current.text.indexOf(":");
    if (splitAt < 0) {
      throw new Error("YAML value is not valid");
    }
    const key = current.text.slice(0, splitAt).trim();
    const rest = current.text.slice(splitAt + 1).trim();
    if (rest) {
      body[key] = unquote(rest);
      cursor += 1;
      continue;
    }
    const next = lines[cursor + 1];
    if (!next || next.indent <= indent) {
      body[key] = {};
      cursor += 1;
      continue;
    }
    const nested = parseBlock(lines, cursor + 1, next.indent);
    body[key] = nested.value;
    cursor = nested.index;
  }
  return { value: body, index: cursor };
}

export function yamlToDefinition(source: string): JsonValue {
  const lines = linesOf(source);
  if (lines.length === 0) {
    return {};
  }
  return parseBlock(lines, 0, lines[0]?.indent ?? 0).value;
}
