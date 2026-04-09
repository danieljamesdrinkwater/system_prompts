import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { animated, useSpring } from "@react-spring/three";
import * as THREE from "three";

export type EnvironmentMode = "passthrough" | "space" | "focus" | "calm";

interface EnvironmentProps {
  mode: EnvironmentMode;
}

const STAR_COUNT = 800;
const DUST_COUNT = 200;

/**
 * Immersive procedural environment backgrounds.
 * Crossfades between modes over 2 seconds.
 *
 * Modes:
 * - passthrough: transparent (XR passthrough visible)
 * - space: dark skybox, stars, nebula glow
 * - focus: deep navy gradient dome, aurora effect
 * - calm: warm sunset gradient, floating dust particles
 */
export function Environment({ mode }: EnvironmentProps) {
  const isActive = mode !== "passthrough";

  const { opacity } = useSpring({
    opacity: isActive ? 1 : 0,
    config: { duration: 2000 },
  });

  return (
    <animated.group visible={opacity.to((v) => v > 0.001)}>
      {mode === "space" && <SpaceEnvironment opacity={opacity} />}
      {mode === "focus" && <FocusEnvironment opacity={opacity} />}
      {mode === "calm" && <CalmEnvironment opacity={opacity} />}
    </animated.group>
  );
}

// ---------------------------------------------------------------------------
// Space: dark sphere, star particles, nebula glow
// ---------------------------------------------------------------------------

function SpaceEnvironment({ opacity }: { opacity: ReturnType<typeof useSpring>["opacity"] }) {
  const starsRef = useRef<THREE.Points>(null);
  const nebulaRef = useRef<THREE.Mesh>(null);
  const timeRef = useRef(0);

  const starPositions = useMemo(() => {
    const positions = new Float32Array(STAR_COUNT * 3);
    for (let i = 0; i < STAR_COUNT; i++) {
      // Distribute on a large sphere shell
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = 8 + Math.random() * 2;
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);
    }
    return positions;
  }, []);

  const starSizes = useMemo(() => {
    const sizes = new Float32Array(STAR_COUNT);
    for (let i = 0; i < STAR_COUNT; i++) {
      sizes[i] = Math.random() * 0.04 + 0.01;
    }
    return sizes;
  }, []);

  useFrame((_, delta) => {
    timeRef.current += delta;

    // Slow star rotation
    if (starsRef.current) {
      starsRef.current.rotation.y += delta * 0.01;
      starsRef.current.rotation.x += delta * 0.003;
    }

    // Pulse the nebula
    if (nebulaRef.current) {
      const mat = nebulaRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity = 0.06 + Math.sin(timeRef.current * 0.3) * 0.02;
    }
  });

  return (
    <animated.group>
      {/* Dark sky dome */}
      <mesh scale={[-1, 1, 1]}>
        <sphereGeometry args={[12, 32, 32]} />
        <animated.meshBasicMaterial
          color="#050510"
          side={THREE.BackSide}
          transparent
          opacity={opacity}
        />
      </mesh>

      {/* Star field */}
      <points ref={starsRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[starPositions, 3]}
            count={STAR_COUNT}
          />
          <bufferAttribute
            attach="attributes-size"
            args={[starSizes, 1]}
            count={STAR_COUNT}
          />
        </bufferGeometry>
        <animated.pointsMaterial
          color="#ffffff"
          size={0.03}
          transparent
          opacity={opacity.to((v) => v * 0.9)}
          sizeAttenuation
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </points>

      {/* Nebula glow -- large colored sphere */}
      <mesh ref={nebulaRef} position={[3, 2, -6]}>
        <sphereGeometry args={[2.5, 16, 16]} />
        <meshBasicMaterial
          color="#4B0082"
          transparent
          opacity={0.06}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      {/* Secondary nebula accent */}
      <mesh position={[-4, -1, -5]}>
        <sphereGeometry args={[2, 16, 16]} />
        <animated.meshBasicMaterial
          color="#1a3a6a"
          transparent
          opacity={opacity.to((v) => v * 0.05)}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
    </animated.group>
  );
}

// ---------------------------------------------------------------------------
// Focus: deep navy gradient dome, aurora bands
// ---------------------------------------------------------------------------

function FocusEnvironment({ opacity }: { opacity: ReturnType<typeof useSpring>["opacity"] }) {
  const auroraRef = useRef<THREE.Group>(null);
  const timeRef = useRef(0);

  // Aurora band vertex positions -- wavy horizontal ribbons
  const auroraBands = useMemo(() => {
    return [
      { y: 4, color: "#00ff88", width: 8, segments: 40 },
      { y: 4.8, color: "#00aaff", width: 6, segments: 30 },
      { y: 3.5, color: "#7B68EE", width: 7, segments: 35 },
    ].map((band) => {
      const positions = new Float32Array(band.segments * 3 * 2);
      for (let i = 0; i < band.segments; i++) {
        const t = i / (band.segments - 1);
        const x = (t - 0.5) * band.width;
        // Top vertex
        positions[i * 6] = x;
        positions[i * 6 + 1] = band.y + 0.3;
        positions[i * 6 + 2] = -6;
        // Bottom vertex
        positions[i * 6 + 3] = x;
        positions[i * 6 + 4] = band.y - 0.3;
        positions[i * 6 + 5] = -6;
      }

      const indices: number[] = [];
      for (let i = 0; i < band.segments - 1; i++) {
        const a = i * 2;
        const b = i * 2 + 1;
        const c = i * 2 + 2;
        const d = i * 2 + 3;
        indices.push(a, b, c, b, d, c);
      }

      return { positions, indices: new Uint16Array(indices), color: band.color, segments: band.segments };
    });
  }, []);

  useFrame((_, delta) => {
    timeRef.current += delta;

    if (auroraRef.current) {
      auroraRef.current.children.forEach((child, bandIndex) => {
        if (child instanceof THREE.Mesh) {
          const geo = child.geometry as THREE.BufferGeometry;
          const pos = geo.attributes.position as THREE.BufferAttribute;
          const segments = pos.count / 2;

          for (let i = 0; i < segments; i++) {
            const t = i / (segments - 1);
            const wave = Math.sin(t * 4 + timeRef.current * 0.5 + bandIndex * 1.5) * 0.2;
            const wave2 = Math.sin(t * 7 + timeRef.current * 0.3) * 0.1;
            // Shift y of top and bottom vertices
            pos.setY(i * 2, 4 + bandIndex * 0.6 + 0.3 + wave + wave2);
            pos.setY(i * 2 + 1, 4 + bandIndex * 0.6 - 0.3 + wave + wave2);
          }
          pos.needsUpdate = true;
        }
      });
    }
  });

  return (
    <animated.group>
      {/* Navy gradient dome */}
      <mesh scale={[-1, 1, 1]}>
        <sphereGeometry args={[12, 32, 32]} />
        <animated.meshBasicMaterial
          color="#0a0a2e"
          side={THREE.BackSide}
          transparent
          opacity={opacity}
        />
      </mesh>

      {/* Subtle horizon glow */}
      <mesh position={[0, -2, -8]} rotation={[-Math.PI / 6, 0, 0]}>
        <planeGeometry args={[20, 6]} />
        <animated.meshBasicMaterial
          color="#1a2a5a"
          transparent
          opacity={opacity.to((v) => v * 0.15)}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      {/* Aurora bands */}
      <group ref={auroraRef}>
        {auroraBands.map((band, i) => (
          <mesh key={i}>
            <bufferGeometry>
              <bufferAttribute
                attach="attributes-position"
                args={[band.positions, 3]}
                count={band.segments * 2}
              />
              <bufferAttribute
                attach="index"
                args={[band.indices, 1]}
                count={band.indices.length}
              />
            </bufferGeometry>
            <animated.meshBasicMaterial
              color={band.color}
              transparent
              opacity={opacity.to((v) => v * 0.12)}
              side={THREE.DoubleSide}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
            />
          </mesh>
        ))}
      </group>
    </animated.group>
  );
}

// ---------------------------------------------------------------------------
// Calm: warm sunset gradient, floating dust particles
// ---------------------------------------------------------------------------

function CalmEnvironment({ opacity }: { opacity: ReturnType<typeof useSpring>["opacity"] }) {
  const dustRef = useRef<THREE.Points>(null);
  const timeRef = useRef(0);

  const dustPositions = useMemo(() => {
    const positions = new Float32Array(DUST_COUNT * 3);
    for (let i = 0; i < DUST_COUNT; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 10;
      positions[i * 3 + 1] = Math.random() * 5 - 1;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 10;
    }
    return positions;
  }, []);

  const dustSpeeds = useMemo(() => {
    const speeds = new Float32Array(DUST_COUNT * 3);
    for (let i = 0; i < DUST_COUNT; i++) {
      speeds[i * 3] = (Math.random() - 0.5) * 0.05;
      speeds[i * 3 + 1] = Math.random() * 0.02 + 0.005;
      speeds[i * 3 + 2] = (Math.random() - 0.5) * 0.05;
    }
    return speeds;
  }, []);

  useFrame((_, delta) => {
    timeRef.current += delta;

    if (dustRef.current) {
      const pos = dustRef.current.geometry.attributes.position as THREE.BufferAttribute;
      for (let i = 0; i < DUST_COUNT; i++) {
        let x = pos.getX(i) + dustSpeeds[i * 3] * delta;
        let y = pos.getY(i) + dustSpeeds[i * 3 + 1] * delta;
        let z = pos.getZ(i) + dustSpeeds[i * 3 + 2] * delta;

        // Wrap particles
        if (y > 4) y = -1;
        if (Math.abs(x) > 5) x = -x * 0.5;
        if (Math.abs(z) > 5) z = -z * 0.5;

        pos.setXYZ(i, x, y, z);
      }
      pos.needsUpdate = true;

      // Gentle sway
      dustRef.current.rotation.y = Math.sin(timeRef.current * 0.05) * 0.1;
    }
  });

  return (
    <animated.group>
      {/* Warm sunset dome -- upper hemisphere */}
      <mesh scale={[-1, 1, 1]}>
        <sphereGeometry args={[12, 32, 32, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <animated.meshBasicMaterial
          color="#2a1520"
          side={THREE.BackSide}
          transparent
          opacity={opacity}
        />
      </mesh>

      {/* Lower hemisphere -- warmer tone */}
      <mesh scale={[-1, 1, 1]}>
        <sphereGeometry args={[12, 32, 32, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2]} />
        <animated.meshBasicMaterial
          color="#1a1018"
          side={THREE.BackSide}
          transparent
          opacity={opacity}
        />
      </mesh>

      {/* Sunset horizon glow */}
      <mesh position={[0, 0, -10]} rotation={[0, 0, 0]}>
        <planeGeometry args={[24, 8]} />
        <animated.meshBasicMaterial
          color="#ff6633"
          transparent
          opacity={opacity.to((v) => v * 0.1)}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      {/* Warm overhead ambient */}
      <mesh position={[0, 6, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <circleGeometry args={[5, 32]} />
        <animated.meshBasicMaterial
          color="#ffaa44"
          transparent
          opacity={opacity.to((v) => v * 0.04)}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* Floating dust particles */}
      <points ref={dustRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[dustPositions, 3]}
            count={DUST_COUNT}
          />
        </bufferGeometry>
        <animated.pointsMaterial
          color="#ffddaa"
          size={0.02}
          transparent
          opacity={opacity.to((v) => v * 0.5)}
          sizeAttenuation
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </points>
    </animated.group>
  );
}
