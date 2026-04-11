/** Remove the base URL prefix from a path. */
export function stripBasePrefix(path: string, basePath: string): string {
  const prefix = basePath.endsWith("/") ? basePath.slice(0, -1) : basePath;
  return path.startsWith(prefix) ? path.slice(prefix.length) : path;
}

/** Ensure leading slash, remove trailing slash (except for root). */
export function normalizePath(path: string): string {
  let result = path;
  if (!result.startsWith("/")) result = "/" + result;
  if (result.endsWith("/") && result.length > 1) result = result.slice(0, -1);
  return result;
}

/** Test whether a path matches /kommune/<id> (exactly one segment). */
export function isKommunePath(path: string): boolean {
  return /^\/kommune\/[^/]+$/.test(path);
}
