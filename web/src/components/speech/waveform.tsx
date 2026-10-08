"use client";

import { useEffect, useRef, type MutableRefObject } from "react";

/** Live microphone level bars drawn from the recorder's rolling level history. */
export function Waveform({ levels, active }: { levels: MutableRefObject<number[]>; active: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!active) return;
    let frame = 0;
    const draw = () => {
      const canvas = canvasRef.current;
      const ctx = canvas?.getContext("2d");
      if (canvas && ctx) {
        const { width, height } = canvas;
        ctx.clearRect(0, 0, width, height);
        const color = getComputedStyle(canvas).getPropertyValue("color") || "#4f46e5";
        ctx.fillStyle = color;
        const bars = 60;
        const barWidth = width / bars;
        const data = levels.current;
        for (let i = 0; i < bars; i++) {
          const value = data[data.length - bars + i] ?? 0;
          const h = Math.max(2, value * height);
          ctx.fillRect(i * barWidth + 1, (height - h) / 2, barWidth - 2, h);
        }
      }
      frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [active, levels]);

  return <canvas ref={canvasRef} width={480} height={64} className="h-16 w-full text-primary" aria-hidden />;
}
