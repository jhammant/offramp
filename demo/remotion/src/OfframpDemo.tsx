import React from "react";
import {
  AbsoluteFill,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  Easing,
} from "remotion";

export const FPS = 30;

// ---- Catppuccin Mocha palette (matches demo/hero.png) --------------------
const C = {
  base: "#181825",
  mantle: "#11111b",
  crust: "#0d0d15",
  surface: "#1e1e2e",
  surface2: "#252537",
  overlay: "#313244",
  line: "#45475a",
  text: "#cdd6f4",
  sub: "#a6adc8",
  muted: "#7f849c",
  teal: "#94e2d5",
  green: "#a6e3a1",
  peach: "#fab387",
  red: "#f38ba8",
  blue: "#89b4fa",
  mauve: "#cba6f7",
  sky: "#89dceb",
};
const MONO = "'SF Mono','JetBrains Mono','Menlo',monospace";
const SANS =
  "-apple-system,BlinkMacSystemFont,'Segoe UI','Inter',system-ui,sans-serif";

// ---- intrinsic sizes of the cropped real stills --------------------------
const IMG = {
  analyze: { src: "analyze.png", w: 1160, h: 1260 },
  replay: { src: "replay.png", w: 1039, h: 202 },
  optimize: { src: "optimize.png", w: 1212, h: 944 },
};

// ---- timing --------------------------------------------------------------
const T = {
  intro: 75,
  beat: 225,
  beatShort: 195,
  outro: 120,
};
const START = {
  intro: 0,
  b1: 75,
  b2: 75 + T.beat, // 300
  b3: 75 + T.beat + T.beatShort, // 495
  outro: 75 + T.beat + T.beatShort + T.beat, // 720
};
export const DEMO_DURATION = START.outro + T.outro; // 840 (28s)

// ---- background ----------------------------------------------------------
const Background: React.FC = () => (
  <AbsoluteFill
    style={{
      background: `radial-gradient(1200px 720px at 82% -8%, rgba(148,226,213,0.10), transparent 60%),
                   radial-gradient(1000px 700px at 0% 118%, rgba(137,180,250,0.09), transparent 55%),
                   linear-gradient(165deg, #1b1b2b 0%, ${C.base} 55%, ${C.mantle} 100%)`,
    }}
  />
);

const Wordmark: React.FC<{ size: number }> = ({ size }) => (
  <div style={{ display: "flex", alignItems: "baseline", gap: size * 0.22 }}>
    <span style={{ fontFamily: MONO, fontSize: size, color: C.teal, fontWeight: 600 }}>
      ❯
    </span>
    <span
      style={{
        fontFamily: MONO,
        fontSize: size,
        color: C.text,
        fontWeight: 700,
        letterSpacing: -size * 0.02,
      }}
    >
      offramp
    </span>
  </div>
);

// ---- intro ---------------------------------------------------------------
const Intro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: { damping: 200 } });
  const y = interpolate(s, [0, 1], [26, 0]);
  const op = interpolate(frame, [0, 12], [0, 1], { extrapolateRight: "clamp" });
  const tagOp = interpolate(frame, [10, 24], [0, 1], { extrapolateRight: "clamp" });
  const fadeOut = interpolate(frame, [T.intro - 12, T.intro], [1, 0], {
    extrapolateLeft: "clamp",
  });
  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        opacity: fadeOut,
      }}
    >
      <div style={{ opacity: op, transform: `translateY(${y}px)`, textAlign: "center" }}>
        <Wordmark size={110} />
        <div
          style={{
            fontFamily: SANS,
            fontSize: 34,
            color: C.text,
            marginTop: 30,
            opacity: tagOp,
            fontWeight: 500,
          }}
        >
          Cut your cloud AI bill —{" "}
          <span style={{ color: C.teal }}>before you route a single call.</span>
        </div>
        <div
          style={{
            fontFamily: MONO,
            fontSize: 20,
            color: C.muted,
            marginTop: 18,
            opacity: tagOp,
            letterSpacing: 1,
          }}
        >
          analyze → replay-eval → govern
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ---- terminal window -----------------------------------------------------
const TerminalCard: React.FC<{
  src: string;
  w: number;
  h: number;
  left: number;
  top: number;
  label: string;
}> = ({ src, w, h, left, top, label }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame, fps, config: { damping: 200 }, durationInFrames: 18 });
  const scaleIn = interpolate(pop, [0, 1], [0.96, 1]);
  const op = interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp" });
  // top-down "printing" reveal of the terminal body
  const reveal = interpolate(frame, [6, 26], [100, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const bar = 44;
  return (
    <div
      style={{
        position: "absolute",
        left,
        top,
        width: w,
        opacity: op,
        transform: `scale(${scaleIn})`,
        transformOrigin: "top left",
        borderRadius: 16,
        overflow: "hidden",
        border: `1px solid ${C.line}`,
        boxShadow: "0 30px 70px rgba(0,0,0,0.45)",
        background: C.surface,
      }}
    >
      <div
        style={{
          height: bar,
          background: C.surface2,
          display: "flex",
          alignItems: "center",
          paddingLeft: 18,
          gap: 9,
          borderBottom: `1px solid ${C.overlay}`,
        }}
      >
        <span style={{ width: 13, height: 13, borderRadius: 99, background: "#f38ba8" }} />
        <span style={{ width: 13, height: 13, borderRadius: 99, background: "#f9e2af" }} />
        <span style={{ width: 13, height: 13, borderRadius: 99, background: "#a6e3a1" }} />
        <span
          style={{
            fontFamily: MONO,
            fontSize: 17,
            color: C.muted,
            marginLeft: 14,
          }}
        >
          {label}
        </span>
      </div>
      <div style={{ position: "relative", height: h, background: C.base }}>
        <Img
          src={staticFile(src)}
          style={{
            width: w,
            height: h,
            display: "block",
            clipPath: `inset(0 0 ${reveal}% 0)`,
          }}
        />
      </div>
    </div>
  );
};

// ---- callout chip --------------------------------------------------------
const Callout: React.FC<{
  text: string;
  color: string;
  x: number;
  y: number;
  delay: number;
}> = ({ text, color, x, y, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, config: { damping: 180, stiffness: 120 } });
  const op = interpolate(s, [0, 1], [0, 1]);
  const tx = interpolate(s, [0, 1], [-18, 0]);
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        transform: `translate(${tx}px, -50%)`,
        opacity: op,
        display: "flex",
        alignItems: "center",
        gap: 12,
        maxWidth: 372,
      }}
    >
      <div style={{ fontSize: 22, color, marginLeft: -6, lineHeight: 1 }}>◄</div>
      <div
        style={{
          background: "rgba(30,30,46,0.92)",
          border: `1px solid ${color}`,
          borderLeft: `4px solid ${color}`,
          borderRadius: 12,
          padding: "12px 16px",
          fontFamily: SANS,
          fontSize: 25,
          lineHeight: 1.25,
          color: C.text,
          fontWeight: 500,
          boxShadow: "0 8px 26px rgba(0,0,0,0.35)",
        }}
      >
        {text}
      </div>
    </div>
  );
};

type CalloutSpec = { text: string; color: string; yFrac: number };

// ---- a beat: header + terminal + callouts --------------------------------
const Beat: React.FC<{
  num: string;
  title: string;
  subtitle: string;
  accent: string;
  img: { src: string; w: number; h: number };
  callouts: CalloutSpec[];
  cmd: string;
}> = ({ num, title, subtitle, accent, img, callouts, cmd }) => {
  const frame = useCurrentFrame();
  const headOp = interpolate(frame, [0, 12], [0, 1], { extrapolateRight: "clamp" });
  const headY = interpolate(frame, [0, 14], [16, 0], { extrapolateRight: "clamp" });

  const termLeft = 56;
  const termTop = 246;
  const maxW = 600;
  const maxH = 812;
  const scale = Math.min(maxW / img.w, maxH / img.h);
  const termW = img.w * scale;
  const termH = img.h * scale;

  // callout column, with enforced min vertical spacing so short terminals
  // (e.g. replay) don't stack their chips on top of one another.
  const colX = termLeft + termW + 46;
  const bodyTop = termTop + 44; // below the window title bar
  const minGap = 104;
  let prevY = -Infinity;
  const positions = callouts.map((c) => {
    let y = bodyTop + c.yFrac * termH;
    if (y - prevY < minGap) y = prevY + minGap;
    prevY = y;
    return y;
  });

  return (
    <AbsoluteFill>
      {/* header */}
      <div
        style={{
          position: "absolute",
          left: 56,
          top: 92,
          opacity: headOp,
          transform: `translateY(${headY}px)`,
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", gap: 18 }}>
          <span style={{ fontFamily: MONO, fontSize: 40, color: accent, fontWeight: 700 }}>
            {num}
          </span>
          <span style={{ fontFamily: SANS, fontSize: 46, color: C.text, fontWeight: 700 }}>
            {title}
          </span>
        </div>
        <div style={{ fontFamily: SANS, fontSize: 27, color: C.sub, marginTop: 8 }}>
          {subtitle}
        </div>
        <div style={{ fontFamily: MONO, fontSize: 19, color: C.muted, marginTop: 12 }}>
          <span style={{ color: C.teal }}>❯</span> {cmd}
        </div>
      </div>

      <TerminalCard
        src={img.src}
        w={termW}
        h={termH}
        left={termLeft}
        top={termTop}
        label={cmd}
      />

      {callouts.map((c, i) => (
        <Callout
          key={i}
          text={c.text}
          color={c.color}
          x={colX}
          y={positions[i]}
          delay={30 + i * 16}
        />
      ))}
    </AbsoluteFill>
  );
};

// ---- outro ---------------------------------------------------------------
const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: { damping: 200 } });
  const y = interpolate(s, [0, 1], [24, 0]);
  const op = interpolate(frame, [0, 12], [0, 1], { extrapolateRight: "clamp" });
  const l2 = interpolate(frame, [12, 26], [0, 1], { extrapolateRight: "clamp" });
  const l3 = interpolate(frame, [22, 38], [0, 1], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ opacity: op, transform: `translateY(${y}px)`, textAlign: "center" }}>
        <Wordmark size={104} />
        <div
          style={{
            fontFamily: SANS,
            fontSize: 32,
            color: C.text,
            marginTop: 28,
            opacity: l2,
            fontWeight: 500,
          }}
        >
          Analysis is <span style={{ color: C.teal }}>100% read-only</span>. Nothing
          reroutes until you say so.
        </div>
        <div
          style={{
            marginTop: 34,
            opacity: l3,
            fontFamily: MONO,
            fontSize: 30,
            color: C.text,
            background: "rgba(30,30,46,0.9)",
            border: `1px solid ${C.line}`,
            borderRadius: 14,
            padding: "16px 28px",
            display: "inline-block",
          }}
        >
          <span style={{ color: C.muted }}>Apache-2.0 · no dependencies</span>
          <br />
          <span style={{ color: C.green }}>github.com/jhammant/offramp</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ---- footer step indicator ----------------------------------------------
const StepDots: React.FC<{ active: number }> = ({ active }) => (
  <div
    style={{
      position: "absolute",
      bottom: 44,
      left: 0,
      right: 0,
      display: "flex",
      justifyContent: "center",
      gap: 14,
    }}
  >
    {[0, 1, 2].map((i) => (
      <div
        key={i}
        style={{
          width: i === active ? 40 : 12,
          height: 12,
          borderRadius: 99,
          background: i === active ? C.teal : C.overlay,
          transition: "all 0.3s",
        }}
      />
    ))}
  </div>
);

// ---- root composition ----------------------------------------------------
export const OfframpDemo: React.FC = () => {
  return (
    <AbsoluteFill style={{ background: C.base }}>
      <Background />

      <Sequence from={START.intro} durationInFrames={T.intro}>
        <Intro />
      </Sequence>

      <Sequence from={START.b1} durationInFrames={T.beat}>
        <Beat
          num="01"
          title="Analyze"
          subtitle="Read your real spend. Rank the savings by risk."
          accent={C.blue}
          cmd="offramp analyze --dry-run --cloud aws"
          img={IMG.analyze}
          callouts={[
            { text: "Your real spend — read-only, no inference", color: C.blue, yFrac: 0.2 },
            { text: "SAFE $413 · same weights, cheaper host, no quality change", color: C.green, yFrac: 0.42 },
            { text: "ADVISORY · a cheaper model is a quality bet", color: C.peach, yFrac: 0.66 },
          ]}
        />
        <StepDots active={0} />
      </Sequence>

      <Sequence from={START.b2} durationInFrames={T.beatShort}>
        <Beat
          num="02"
          title="Replay-eval"
          subtitle="Prove the swap on your own prompts — live."
          accent={C.teal}
          cmd="offramp replay llama-3.3-70b gpt-oss-120b --live"
          img={IMG.replay}
          callouts={[
            { text: "A real live call on Groq — LLM-as-judge, not a mock", color: C.teal, yFrac: 0.34 },
            { text: "0.85 agreement on your prompts", color: C.blue, yFrac: 0.58 },
            { text: "VERDICT: RECOMMEND", color: C.green, yFrac: 0.82 },
          ]}
        />
        <StepDots active={1} />
      </Sequence>

      <Sequence from={START.b3} durationInFrames={T.beat}>
        <Beat
          num="03"
          title="Govern"
          subtitle="A plan you can actually sign off on."
          accent={C.peach}
          cmd="offramp optimize --dry-run --cloud aws"
          img={IMG.optimize}
          callouts={[
            { text: "APPLY $413 — safe, auto-applicable", color: C.green, yFrac: 0.18 },
            { text: "STAGE $4,048 — passed eval, needs your sign-off", color: C.peach, yFrac: 0.5 },
            { text: "HOLD — eval rejected, quality too low", color: C.red, yFrac: 0.78 },
          ]}
        />
        <StepDots active={2} />
      </Sequence>

      <Sequence from={START.outro} durationInFrames={T.outro}>
        <Outro />
      </Sequence>
    </AbsoluteFill>
  );
};
