import { screen, userEvent } from "@testing-library/react-native";

import { AnswerRecorder } from "@/components/answer-recorder";

import { renderWithProviders } from "@/test/render";

const recording = { uri: "file:///answer.m4a", mimeType: "audio/mp4", durationSeconds: 12.4, pauses: { measured: true as const, count: 2, long_count: 0, total_silence_seconds: 1.6 } };
const mockRecorder = { phase: "idle" as "idle" | "recording", error: null, elapsed: 0, level: null, start: jest.fn(), stop: jest.fn() };

jest.mock("@/hooks/use-answer-recorder", () => ({ useAnswerRecorder: () => mockRecorder }));

describe("AnswerRecorder", () => {
  beforeEach(() => {
    mockRecorder.phase = "idle";
    mockRecorder.start.mockReset();
    mockRecorder.stop.mockReset();
  });

  it("sends a typed answer, labelled as typed", async () => {
    const onAnswer = jest.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    await renderWithProviders(<AnswerRecorder serverStt={false} onAnswer={onAnswer} />);
    await user.press(screen.getByRole("button", { name: "Type instead" }));
    await user.type(screen.getByLabelText("Your answer"), "I live in a small flat.");
    await user.press(screen.getByRole("button", { name: "Send answer" }));
    expect(onAnswer).toHaveBeenCalledWith({ recording: null, transcript: "I live in a small flat.", source: "typed" });
  });

  it("without server transcription keeps the recording and asks for the words", async () => {
    mockRecorder.phase = "recording";
    mockRecorder.stop.mockResolvedValue(recording);
    const onAnswer = jest.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    await renderWithProviders(<AnswerRecorder serverStt={false} onAnswer={onAnswer} />);
    await user.press(screen.getByRole("button", { name: "Stop" }));
    expect(await screen.findByText(/Your recording is saved/)).toBeOnTheScreen();
    expect(onAnswer).not.toHaveBeenCalled();
    await user.type(screen.getByLabelText("Your answer"), "It is quiet and close to work.");
    await user.press(screen.getByRole("button", { name: "Send answer" }));
    expect(onAnswer).toHaveBeenCalledWith({ recording, transcript: "It is quiet and close to work.", source: "typed" });
  });

  it("with server transcription sends the recording straight away", async () => {
    mockRecorder.phase = "recording";
    mockRecorder.stop.mockResolvedValue(recording);
    const onAnswer = jest.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    await renderWithProviders(<AnswerRecorder serverStt onAnswer={onAnswer} />);
    await user.press(screen.getByRole("button", { name: "Stop & send" }));
    expect(onAnswer).toHaveBeenCalledWith({ recording, transcript: null, source: null });
  });
});
