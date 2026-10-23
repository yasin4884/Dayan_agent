/** تبدیل تاریخ میلادی ↔ شمسی و نمایش با ساعت تهران */

const WEEKDAYS = ["یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه"];
const MONTHS = [
  "فروردین",
  "اردیبهشت",
  "خرداد",
  "تیر",
  "مرداد",
  "شهریور",
  "مهر",
  "آبان",
  "آذر",
  "دی",
  "بهمن",
  "اسفند",
];

function div(a: number, b: number) {
  return Math.floor(a / b);
}

/** الگوریتم استاندارد جلالی */
export function gregorianToJalali(gy: number, gm: number, gd: number) {
  const g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
  let jy = gy <= 1600 ? 0 : 979;
  gy -= gy <= 1600 ? 621 : 1600;
  const gy2 = gm > 2 ? gy + 1 : gy;
  let days =
    365 * gy +
    div(gy2 + 3, 4) -
    div(gy2 + 99, 100) +
    div(gy2 + 399, 400) -
    80 +
    gd +
    g_d_m[gm - 1];
  jy += 33 * div(days, 12053);
  days %= 12053;
  jy += 4 * div(days, 1461);
  days %= 1461;
  if (days > 365) {
    jy += div(days - 1, 365);
    days = (days - 1) % 365;
  }
  const jm = days < 186 ? 1 + div(days, 31) : 7 + div(days - 186, 30);
  const jd = 1 + (days < 186 ? days % 31 : (days - 186) % 30);
  return { jy, jm, jd };
}

export function jalaliToGregorian(jy: number, jm: number, jd: number) {
  let gy = jy <= 979 ? 621 : 1600;
  jy -= jy <= 979 ? 0 : 979;
  const days =
    365 * jy +
    div(jy, 33) * 8 +
    div((jy % 33) + 3, 4) +
    78 +
    jd +
    (jm < 7 ? (jm - 1) * 31 : (jm - 7) * 30 + 186);
  gy += 400 * div(days, 146097);
  let d = days % 146097;
  if (d >= 36525) {
    gy += 100 * div(--d, 36524);
    d %= 36524;
    if (d >= 365) d++;
  }
  gy += 4 * div(d, 1461);
  d %= 1461;
  if (d >= 366) {
    gy += div(d - 1, 365);
    d = (d - 1) % 365;
  }
  const sal_a = [
    0,
    31,
    (gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0 ? 29 : 28,
    31,
    30,
    31,
    30,
    31,
    31,
    30,
    31,
    30,
    31,
  ];
  let gm = 0;
  for (gm = 1; gm <= 12 && d >= sal_a[gm]; gm++) d -= sal_a[gm];
  return { gy, gm, gd: d + 1 };
}

export function tehranNow(): Date {
  const s = new Date().toLocaleString("en-US", { timeZone: "Asia/Tehran" });
  return new Date(s);
}

export function formatJalaliDate(date: Date = tehranNow()) {
  const { jy, jm, jd } = gregorianToJalali(date.getFullYear(), date.getMonth() + 1, date.getDate());
  const weekday = WEEKDAYS[date.getDay()];
  return {
    weekday,
    day: jd,
    month: jm,
    monthName: MONTHS[jm - 1],
    year: jy,
    text: `${weekday} ${jd} ${MONTHS[jm - 1]} ${jy}`,
    short: `${jy}/${String(jm).padStart(2, "0")}/${String(jd).padStart(2, "0")}`,
  };
}

export function formatTime(date: Date = tehranNow()) {
  const h = String(date.getHours()).padStart(2, "0");
  const m = String(date.getMinutes()).padStart(2, "0");
  const s = String(date.getSeconds()).padStart(2, "0");
  return `${h}:${m}:${s}`;
}

/** ورودی YYYY-MM-DD میلادی یا YYYY/MM/DD شمسی → متن شمسی */
export function displayDate(raw?: string | null): string {
  if (!raw) return "—";
  const s = String(raw).trim();
  // شمسی با /
  const j = s.match(/^(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})$/);
  if (j) {
    const jy = Number(j[1]);
    const jm = Number(j[2]);
    const jd = Number(j[3]);
    if (jy > 1300 && jy < 1500) {
      return `${jd} ${MONTHS[jm - 1] || ""} ${jy}`.trim();
    }
    // میلادی
    const { jy: y, jm: m, jd: d } = gregorianToJalali(jy, jm, jd);
    return `${d} ${MONTHS[m - 1]} ${y}`;
  }
  const dt = new Date(s);
  if (!Number.isNaN(dt.getTime())) {
    return formatJalaliDate(dt).text.replace(/^[^\s]+\s/, ""); // بدون weekday
  }
  return s;
}

export function gregorianISOFromJalali(jy: number, jm: number, jd: number): string {
  const { gy, gm, gd } = jalaliToGregorian(jy, jm, jd);
  return `${gy}-${String(gm).padStart(2, "0")}-${String(gd).padStart(2, "0")}`;
}

export { MONTHS, WEEKDAYS };
