import { appHref } from "@/lib/routes";

describe("appHref", () => {
  it("opens the screens the API links to, keeping their parameters", () => {
    expect(appHref("/practice/new?focus=articles")).toBe("/practice/new?focus=articles");
    expect(appHref("/reading?types=true_false_not_given")).toBe("/reading?types=true_false_not_given");
    expect(appHref("/speaking?mode=part1")).toBe("/speaking?mode=part1");
  });

  it("translates the few web-only paths", () => {
    expect(appHref("/dashboard")).toBe("/");
    expect(appHref("/onboarding/diagnostic")).toBe("/diagnostic");
    expect(appHref(null)).toBe("/");
  });
});
