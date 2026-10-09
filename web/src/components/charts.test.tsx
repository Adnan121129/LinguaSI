import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ChartCard } from "@/components/charts";

const ROWS = [
  { week: "Sep 29", writing: 6, speaking: 5.5 },
  { week: "Oct 6", writing: 6.5, speaking: null },
];
const COLUMNS = [
  { key: "week", label: "Week" },
  { key: "writing", label: "Writing" },
  { key: "speaking", label: "Speaking" },
];

describe("ChartCard", () => {
  it("titles every chart with the question it answers and offers a table view of the same data", () => {
    render(
      <ChartCard question="Are my bands improving?" rows={ROWS} columns={COLUMNS} legend={[{ label: "Writing", color: "red" }, { label: "Speaking", color: "blue" }]}>
        <div>chart drawing</div>
      </ChartCard>,
    );
    const card = screen.getByRole("region", { name: "Are my bands improving?" });
    expect(within(card).getByText("chart drawing")).toBeInTheDocument();
    expect(within(card).getByRole("list", { name: "Legend" })).toHaveTextContent("WritingSpeaking");

    fireEvent.click(within(card).getByRole("button", { name: "Table" }));
    const table = within(card).getByRole("table");
    expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Week", "Writing", "Speaking"]);
    expect(within(table).getAllByRole("row")[2]).toHaveTextContent("Oct 66.5—");
    expect(within(card).getByRole("button", { name: "Chart" })).toHaveAttribute("aria-pressed", "true");
    expect(within(card).queryByText("chart drawing")).not.toBeInTheDocument();
  });

  it("leaves out the legend for a single series, where the title already names it", () => {
    render(
      <ChartCard question="How many words do I know?" rows={ROWS} columns={COLUMNS} legend={[{ label: "Words", color: "red" }]}>
        <div>chart</div>
      </ChartCard>,
    );
    expect(screen.queryByRole("list", { name: "Legend" })).not.toBeInTheDocument();
  });
});
