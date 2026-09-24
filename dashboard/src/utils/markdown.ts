/**
 * Markdown helpers for workspace / SkillHub documents that often carry a
 * leading YAML frontmatter block (``---`` ... ``---``).
 */

export interface SplitMarkdownFrontmatter {
  /** Raw YAML between the delimiters, or null when absent. */
  raw: string | null;
  /** Markdown body with frontmatter removed. */
  body: string;
}

/**
 * Split a markdown string into YAML frontmatter and body.
 *
 * When no valid frontmatter exists, ``raw`` is null and ``body`` is the
 * original text (leading whitespace trimmed).
 */
export function splitMarkdownFrontmatter(s: string): SplitMarkdownFrontmatter {
  const match = s.match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/);
  if (!match) {
    return { raw: null, body: s.replace(/^\uFEFF/, "").trimStart() };
  }
  return {
    raw: match[1] ?? "",
    body: s
      .slice(match[0].length)
      .replace(/^\uFEFF/, "")
      .trimStart(),
  };
}

/**
 * Strip YAML frontmatter from the beginning of a markdown string.
 *
 * Many .md files start with a YAML header wrapped in `---` delimiters.
 * Markdown renderers treat `---` as <hr> and dump the YAML as plain text.
 */
export const stripFrontmatter = (s: string): string =>
  splitMarkdownFrontmatter(s).body;
