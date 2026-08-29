export function printTable(rows: Record<string, string>[]): void {
  if (rows.length === 0) {
    console.log("(none)");
    return;
  }
  const columns = Object.keys(rows[0]);
  const widths = columns.map((col) =>
    Math.max(col.length, ...rows.map((r) => (r[col] ?? "").length)),
  );

  const line = (cells: string[]) =>
    cells.map((cell, i) => cell.padEnd(widths[i])).join("  ");

  console.log(line(columns.map((c) => c.toUpperCase())));
  console.log(line(widths.map((w) => "-".repeat(w))));
  for (const row of rows) {
    console.log(line(columns.map((c) => row[c] ?? "")));
  }
}

export function fail(message: string): never {
  console.error(`Error: ${message}`);
  process.exit(1);
}
