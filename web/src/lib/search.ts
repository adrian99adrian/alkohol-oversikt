/** NFC-normalize and lowercase a string for accent-safe comparison. */
export function normalizeSearch(str: string): string {
  return str.normalize("NFC").toLowerCase();
}

/** Filter a list of named items by normalized substring match. */
export function filterMunicipalities<T extends { name: string }>(
  items: T[],
  query: string,
): T[] {
  const normalizedQuery = normalizeSearch(query);
  return items.filter((item) =>
    normalizeSearch(item.name).includes(normalizedQuery),
  );
}
