export type PaymentRow = { number: number; date: string; payment: number; interest: number; principal: number; balance: number };

// Money remains integer rubles. The final payment pays the remaining principal.
export function calculateSchedule(amount: number, rate: number, months: number, issuedAt: string): PaymentRow[] {
  const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'Europe/Moscow', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date(issuedAt));
  const part = (type: string) => Number(parts.find((item) => item.type === type)!.value);
  const issued = new Date(Date.UTC(part('year'), part('month') - 1, part('day')));
  const monthlyRate = rate / 1200;
  const payment = Math.round(monthlyRate === 0 ? amount / months : amount * monthlyRate / (1 - (1 + monthlyRate) ** -months));
  const rateUnits = BigInt(Math.round(rate * 100));
  let balance = amount;
  return Array.from({ length: months }, (_, index) => {
    const interest = Number((BigInt(balance) * rateUnits + 60000n) / 120000n);
    const principal = index === months - 1 ? balance : Math.min(balance, payment - interest);
    balance -= principal;
    const first = new Date(Date.UTC(issued.getUTCFullYear(), issued.getUTCMonth() + index + 1, 1));
    const lastDay = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate();
    first.setUTCDate(Math.min(issued.getUTCDate(), lastDay));
    return { number: index + 1, date: first.toISOString().slice(0, 10), payment: principal + interest, interest, principal, balance };
  });
}
