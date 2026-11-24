/** One run of text on one side of a comparison, and whether the other side lacks it. */
export type DiffPart = { text: string; changed: boolean };

// Past this many words on either side the table of matches is not worth building:
// the passages are shown whole.
const MAX_WORDS = 1500;

function words(text: string): string[] {
  return text.split(/(\s+)/).filter((piece) => piece !== "");
}

function gather(tokens: string[], kept: boolean[]): DiffPart[] {
  const parts: DiffPart[] = [];
  tokens.forEach((token, index) => {
    // White space between two changed words is part of the same change.
    const blank = token.trim() === "";
    const changed = blank
      ? kept[index - 1] === false && kept[index + 1] === false
      : kept[index] === false;
    const last = parts.at(-1);
    if (last && last.changed === changed) last.text += token;
    else parts.push({ text: token, changed });
  });
  return parts;
}

/**
 * Mark the words each of two passages has that the other does not.
 *
 * Words are matched in order (the longest run of words both sides share, as a sequence), so
 * a sentence with one figure changed marks that figure and nothing else. White space is
 * never a difference.
 */
export function wordDiff(before: string, after: string): { before: DiffPart[]; after: DiffPart[] } {
  const left = words(before);
  const right = words(after);
  const a = left.map((token, index) => ({ token, index })).filter((item) => item.token.trim());
  const b = right.map((token, index) => ({ token, index })).filter((item) => item.token.trim());
  const keptLeft: boolean[] = left.map((token) => token.trim() === "");
  const keptRight: boolean[] = right.map((token) => token.trim() === "");
  if (a.length > MAX_WORDS || b.length > MAX_WORDS) {
    return {
      before: before ? [{ text: before, changed: false }] : [],
      after: after ? [{ text: after, changed: false }] : [],
    };
  }
  // A flat table: cell (i, j) is the longest shared sequence of a[i..] and b[j..].
  const width = b.length + 1;
  const table = new Int32Array((a.length + 1) * width);
  const cell = (i: number, j: number) => table[i * width + j] ?? 0;
  const word = (list: typeof a, index: number) => list[index]?.token ?? "";
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      table[i * width + j] =
        word(a, i) === word(b, j)
          ? cell(i + 1, j + 1) + 1
          : Math.max(cell(i + 1, j), cell(i, j + 1));
    }
  }
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (word(a, i) === word(b, j)) {
      keptLeft[a[i]?.index ?? -1] = true;
      keptRight[b[j]?.index ?? -1] = true;
      i += 1;
      j += 1;
    } else if (cell(i + 1, j) >= cell(i, j + 1)) {
      i += 1;
    } else {
      j += 1;
    }
  }
  return { before: gather(left, keptLeft), after: gather(right, keptRight) };
}
