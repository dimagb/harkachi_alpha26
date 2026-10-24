export function plural(value: number, forms: readonly [string, string, string]): string {
  const lastHundred = Math.abs(value) % 100;
  const lastDigit = lastHundred % 10;
  const form = lastHundred >= 11 && lastHundred <= 14 ? forms[2] : lastDigit === 1 ? forms[0] : lastDigit >= 2 && lastDigit <= 4 ? forms[1] : forms[2];
  return `${value} ${form}`;
}
