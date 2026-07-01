import React from "react";
import { Composition } from "remotion";
import { OfframpDemo, DEMO_DURATION, FPS } from "./OfframpDemo";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="offramp"
      component={OfframpDemo}
      durationInFrames={DEMO_DURATION}
      fps={FPS}
      width={1080}
      height={1350}
    />
  );
};
