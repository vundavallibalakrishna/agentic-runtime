/** The message key that names a file's type in plain words, or "" when it is not a known one. */
const KEYS: [RegExp, string][] = [
  [/wordprocessingml|msword/, "word"],
  [/spreadsheetml|ms-excel/, "excel"],
  [/presentationml|ms-powerpoint/, "powerpoint"],
  [/^application\/pdf$/, "pdf"],
  [/^text\/csv$/, "csv"],
  [/^text\/markdown$/, "markdown"],
  [/^text\/html$/, "html"],
  [/^text\/plain$/, "text"],
  [/^application\/json$/, "json"],
  [/^image\//, "image"],
  [/^message\/rfc822$|ms-outlook/, "email"],
];

export function fileTypeKey(mediaType: string | null | undefined): string {
  const value = ((mediaType ?? "").toLowerCase().split(";")[0] ?? "").trim();
  return KEYS.find(([pattern]) => pattern.test(value))?.[1] ?? "";
}
