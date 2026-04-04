export const weekdayShort: Record<string, string> = {
  mandag: "man",
  tirsdag: "tir",
  onsdag: "ons",
  torsdag: "tor",
  fredag: "fre",
  lørdag: "lør",
  søndag: "søn",
};

export function formatDateShort(dateStr: string): string {
  const [, month, day] = dateStr.split("-");
  return `${day}.${month}`;
}

export function formatDateLong(dateStr: string): string {
  const [year, month, day] = dateStr.split("-");
  return `${day}.${month}.${year}`;
}
