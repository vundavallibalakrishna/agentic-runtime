/**
 * A masked value is written as `[KIND]`, such as `[EMAIL_ADDRESS]` (data protection §5).
 * Markdown reads a line that starts with `[KIND]: …` as a link definition and draws nothing
 * for it, so part of an answer vanished. Before the text reaches the Markdown parser, each
 * token becomes inline code, which Markdown never reads as anything else and which shows
 * the token as what it is: a mark where a value was taken out.
 */

// A kind is upper case with underscores. A token followed by `(`, `[` or `]` is Markdown
// link syntax, not a mask. One already inside backticks is left as it is.
const token = /(`+)[^`]*\1|\[([A-Z][A-Z0-9_]{1,40})\](?![([\]])/g;

export function markMasked(text: string): string {
  return text.replace(token, (match, _fence: string | undefined, kind: string | undefined) =>
    kind ? `\`[${kind}]\`` : match,
  );
}
