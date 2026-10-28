const image = /!\[([^\]]*)\]\(([^)\s]+)\)/g;
const link = /\[([^\]]+)\]\(([^)\s]+)\)/g;
const b64 = /[A-Za-z0-9+/]{40,}={0,2}/;

export function filterMarkdown(text: string, allowHosts: string[] = []): string {
  const withoutImages = text.replace(image, (_match, alt: string, url: string) => {
    let host = "";
    try {
      host = new URL(url, "http://local").hostname;
    } catch {
      host = "";
    }
    if (url.startsWith("/") || allowHosts.includes(host)) {
      return _match;
    }
    return alt || "[image removed]";
  });
  return withoutImages.replace(link, (match, label: string, url: string) => {
    const query = url.includes("?") ? url.slice(url.indexOf("?") + 1) : "";
    if (query.length > 200 || b64.test(query)) {
      return `${label} (link hidden)`;
    }
    return match;
  });
}

export const linkRel = "noopener noreferrer nofollow";
