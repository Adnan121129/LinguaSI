import { pauseStats } from "@/lib/pauses";

const speech = (n: number) => Array(n).fill(-20);
const silence = (n: number) => Array(n).fill(-60);

describe("pauseStats", () => {
  it("counts pauses between words, flags long ones and ignores leading and trailing silence", () => {
    const levels = [...silence(10), ...speech(10), ...silence(8), ...speech(10), ...silence(25), ...speech(5), ...silence(30)];
    expect(pauseStats(levels, 0.1)).toEqual({ measured: true, count: 2, long_count: 1, total_silence_seconds: 3.3 });
  });

  it("ignores short gaps that are just between syllables", () => {
    expect(pauseStats([...speech(10), ...silence(3), ...speech(10)], 0.1)).toEqual({ measured: true, count: 0, long_count: 0, total_silence_seconds: 0 });
  });

  it("returns nothing rather than inventing numbers when there were no level readings or no speech", () => {
    expect(pauseStats([])).toBeNull();
    expect(pauseStats(silence(50))).toBeNull();
  });
});
