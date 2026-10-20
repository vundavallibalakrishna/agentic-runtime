import DOMPurify from "dompurify";

/** Strip active content before any HTML preview is inserted into the page. */
export function sanitizeHtml(value: string): string {
  return DOMPurify.sanitize(value, { FORBID_TAGS: ["script", "style"] });
}
