/**
 * Spatial Audio hook for the Quest 3 workspace.
 *
 * Procedural sounds positioned in 3D via the Web Audio API.
 * No external audio files required — all sounds are synthesized
 * from oscillators and noise bursts.
 */

export type SoundType =
  | "panelOpen"
  | "panelClose"
  | "panelSnap"
  | "hoverEnter"
  | "selectionConfirm";

type Position3D = [number, number, number];

let audioContext: AudioContext | null = null;
let masterGain: GainNode | null = null;
let currentVolume = 0.3;

function getContext(): AudioContext {
  if (!audioContext) {
    audioContext = new AudioContext();
    masterGain = audioContext.createGain();
    masterGain.gain.value = currentVolume;
    masterGain.connect(audioContext.destination);
  }
  // Resume if suspended (browsers require user gesture)
  if (audioContext.state === "suspended") {
    audioContext.resume();
  }
  return audioContext;
}

function getMasterGain(): GainNode {
  getContext();
  return masterGain!;
}

/**
 * Create a PannerNode positioned in 3D space.
 */
function createPanner(ctx: AudioContext, position: Position3D): PannerNode {
  const panner = ctx.createPanner();
  panner.panningModel = "HRTF";
  panner.distanceModel = "inverse";
  panner.refDistance = 1;
  panner.maxDistance = 10;
  panner.rolloffFactor = 1;
  panner.coneInnerAngle = 360;
  panner.coneOuterAngle = 360;
  panner.coneOuterGain = 0;
  panner.positionX.value = position[0];
  panner.positionY.value = position[1];
  panner.positionZ.value = position[2];
  return panner;
}

/**
 * Panel open: soft glass resonance.
 * Sine at 440Hz with a quick exponential fade-out over ~200ms.
 */
function playPanelOpen(ctx: AudioContext, panner: PannerNode): void {
  const now = ctx.currentTime;

  const osc = ctx.createOscillator();
  osc.type = "sine";
  osc.frequency.value = 440;

  const env = ctx.createGain();
  env.gain.setValueAtTime(0.4, now);
  env.gain.exponentialRampToValueAtTime(0.001, now + 0.2);

  osc.connect(env);
  env.connect(panner);
  panner.connect(getMasterGain());

  osc.start(now);
  osc.stop(now + 0.25);
}

/**
 * Panel close: lower glass tap.
 * Sine at 220Hz with a quick decay over ~150ms.
 */
function playPanelClose(ctx: AudioContext, panner: PannerNode): void {
  const now = ctx.currentTime;

  const osc = ctx.createOscillator();
  osc.type = "sine";
  osc.frequency.value = 220;

  const env = ctx.createGain();
  env.gain.setValueAtTime(0.35, now);
  env.gain.exponentialRampToValueAtTime(0.001, now + 0.15);

  osc.connect(env);
  env.connect(panner);
  panner.connect(getMasterGain());

  osc.start(now);
  osc.stop(now + 0.2);
}

/**
 * Panel snap: subtle click.
 * Very short white-noise burst (~30ms) to simulate a tactile snap.
 */
function playPanelSnap(ctx: AudioContext, panner: PannerNode): void {
  const now = ctx.currentTime;

  const bufferSize = Math.floor(ctx.sampleRate * 0.03);
  const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < bufferSize; i++) {
    data[i] = (Math.random() * 2 - 1) * (1 - i / bufferSize);
  }

  const source = ctx.createBufferSource();
  source.buffer = buffer;

  const env = ctx.createGain();
  env.gain.setValueAtTime(0.3, now);
  env.gain.exponentialRampToValueAtTime(0.001, now + 0.03);

  source.connect(env);
  env.connect(panner);
  panner.connect(getMasterGain());

  source.start(now);
}

/**
 * Hover enter: gentle high tick.
 * Sine at 880Hz, very short (~50ms) with quick fade.
 */
function playHoverEnter(ctx: AudioContext, panner: PannerNode): void {
  const now = ctx.currentTime;

  const osc = ctx.createOscillator();
  osc.type = "sine";
  osc.frequency.value = 880;

  const env = ctx.createGain();
  env.gain.setValueAtTime(0.2, now);
  env.gain.exponentialRampToValueAtTime(0.001, now + 0.05);

  osc.connect(env);
  env.connect(panner);
  panner.connect(getMasterGain());

  osc.start(now);
  osc.stop(now + 0.08);
}

/**
 * Selection confirm: two-tone chime.
 * 523Hz (C5) for 100ms then 659Hz (E5) for 150ms.
 */
function playSelectionConfirm(ctx: AudioContext, panner: PannerNode): void {
  const now = ctx.currentTime;

  // First tone: C5
  const osc1 = ctx.createOscillator();
  osc1.type = "sine";
  osc1.frequency.value = 523;

  const env1 = ctx.createGain();
  env1.gain.setValueAtTime(0.3, now);
  env1.gain.exponentialRampToValueAtTime(0.001, now + 0.1);

  osc1.connect(env1);
  env1.connect(panner);

  // Second tone: E5
  const osc2 = ctx.createOscillator();
  osc2.type = "sine";
  osc2.frequency.value = 659;

  const env2 = ctx.createGain();
  env2.gain.setValueAtTime(0, now);
  env2.gain.setValueAtTime(0.3, now + 0.1);
  env2.gain.exponentialRampToValueAtTime(0.001, now + 0.25);

  osc2.connect(env2);
  env2.connect(panner);

  panner.connect(getMasterGain());

  osc1.start(now);
  osc1.stop(now + 0.12);
  osc2.start(now + 0.1);
  osc2.stop(now + 0.3);
}

/**
 * Play a spatial sound at the given 3D position.
 */
export function playSound(
  type: SoundType,
  position: Position3D = [0, 0, 0]
): void {
  const ctx = getContext();
  const panner = createPanner(ctx, position);

  switch (type) {
    case "panelOpen":
      playPanelOpen(ctx, panner);
      break;
    case "panelClose":
      playPanelClose(ctx, panner);
      break;
    case "panelSnap":
      playPanelSnap(ctx, panner);
      break;
    case "hoverEnter":
      playHoverEnter(ctx, panner);
      break;
    case "selectionConfirm":
      playSelectionConfirm(ctx, panner);
      break;
  }
}

/**
 * Set the master volume (0.0 to 1.0).
 */
export function setVolume(v: number): void {
  currentVolume = Math.max(0, Math.min(1, v));
  if (masterGain) {
    masterGain.gain.value = currentVolume;
  }
}
