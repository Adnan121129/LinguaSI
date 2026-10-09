import { checkTestDate } from "@/lib/validation";

const TODAY = new Date(2026, 9, 8, 9, 30); // 8 Oct 2026, local time

describe("checkTestDate", () => {
  it("accepts an empty value (no test booked) and future dates", () => {
    expect(checkTestDate("", TODAY)).toBeNull();
    expect(checkTestDate("2026-10-08", TODAY)).toBeNull();
    expect(checkTestDate("2027-03-14", TODAY)).toBeNull();
  });

  it("explains what is wrong with other values", () => {
    expect(checkTestDate("14/03/2027", TODAY)).toMatch(/YYYY-MM-DD/);
    expect(checkTestDate("2027-02-30", TODAY)).toBe("That date doesn't exist.");
    expect(checkTestDate("2026-10-07", TODAY)).toBe("Choose a date in the future.");
  });

  it("works in calendar days in every timezone", () => {
    const original = process.env.TZ;
    try {
      for (const tz of ["Asia/Dhaka", "Pacific/Auckland", "America/Los_Angeles"]) {
        process.env.TZ = tz;
        expect(checkTestDate("2027-01-01", new Date(2026, 9, 8))).toBeNull();
      }
    } finally {
      process.env.TZ = original;
    }
  });
});
