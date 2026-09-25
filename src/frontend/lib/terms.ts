/**
 * Shared helpers for labelling, ordering and filtering courses by academic term.
 *
 * Term options are always derived from the loaded course data instead of a
 * hardcoded list, so the UI stays correct as terms are added or removed.
 */

/** Label used for courses that do not carry a term or year. */
export const UNSCHEDULED_TERM = 'Unscheduled';

/** Minimal shape needed to derive a term label from a course. */
export interface TermCourse {
  term?: string | null;
  year?: number | null;
}

/** An option shown in the term filter dropdown. */
export interface TermOption {
  value: string;
  count: number;
}

/**
 * Build the canonical label for a course's term, e.g. "Fall 2026".
 *
 * Falls back to "Unscheduled" when neither term nor year is set.
 */
export function courseTermLabel(course: TermCourse): string {
  const label = [course.term, course.year].filter(Boolean).join(' ').trim();
  return label || UNSCHEDULED_TERM;
}

/** Chronological rank of a term name within a single year. */
function termRank(term: string): number {
  switch (term.trim().toLowerCase()) {
    case 'winter':
      return 1;
    case 'spring':
      return 2;
    case 'summer':
      return 3;
    case 'fall':
    case 'autumn':
      return 4;
    default:
      return 0;
  }
}

/** Split a term label into its year and term rank for ordering. */
function parseTermLabel(label: string): { year: number; rank: number } {
  const parts = label.split(' ').filter(Boolean);
  const yearPart = Number(parts[parts.length - 1]);
  const year = Number.isFinite(yearPart) ? yearPart : 0;
  const term = parts.slice(0, -1).join(' ');
  return { year, rank: termRank(term) };
}

/**
 * Sort term labels newest first: "Fall 2026" before "Summer 2026" before
 * "Winter 2025". Unscheduled courses are always listed last.
 */
export function sortTermLabels(labels: string[]): string[] {
  return [...labels].sort((a, b) => {
    if (a === UNSCHEDULED_TERM) return b === UNSCHEDULED_TERM ? 0 : 1;
    if (b === UNSCHEDULED_TERM) return -1;
    const left = parseTermLabel(a);
    const right = parseTermLabel(b);
    if (left.year !== right.year) return right.year - left.year;
    if (left.rank !== right.rank) return right.rank - left.rank;
    return a.localeCompare(b);
  });
}

/**
 * Build the term filter options (label + course count) from a course list.
 *
 * The result is sorted newest first so the most relevant term is at the top.
 */
export function buildTermOptions<T extends TermCourse>(courses: T[]): TermOption[] {
  const counts = new Map<string, number>();
  for (const course of courses) {
    const label = courseTermLabel(course);
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  return sortTermLabels([...counts.keys()]).map((value) => ({
    value,
    count: counts.get(value) ?? 0,
  }));
}
