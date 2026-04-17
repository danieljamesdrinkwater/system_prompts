import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Text } from "@react-three/drei";
import * as THREE from "three";

interface BarDataItem {
  label: string;
  value: number;
  color: string;
}

interface VolumetricPanelProps {
  width: number;
  height: number;
  data?: BarDataItem[];
}

const DEFAULT_DATA: BarDataItem[] = [
  { label: "Mon", value: 0.7, color: "#7B68EE" },
  { label: "Tue", value: 0.45, color: "#4ECDC4" },
  { label: "Wed", value: 0.9, color: "#FFE066" },
  { label: "Thu", value: 0.55, color: "#FF6B6B" },
  { label: "Fri", value: 0.8, color: "#A3D9FF" },
];

const PARTICLE_COUNT = 60;

/**
 * Volumetric 3D content panel -- visionOS-style.
 * Displays a 3D bar chart with emissive glow and
 * floating particles behind glass for depth.
 */
export function VolumetricPanel({ width, height, data }: VolumetricPanelProps) {
  const chartData = data ?? DEFAULT_DATA;
  const particlesRef = useRef<THREE.Points>(null);
  const barsRef = useRef<THREE.Group>(null);
  const timeRef = useRef(0);

  // Generate random particle positions within panel bounds
  const particlePositions = useMemo(() => {
    const positions = new Float32Array(PARTICLE_COUNT * 3);
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      positions[i * 3] = (Math.random() - 0.5) * (width - 0.04);
      positions[i * 3 + 1] = (Math.random() - 0.5) * (height - 0.06);
      positions[i * 3 + 2] = (Math.random() - 0.5) * 0.04 - 0.01;
    }
    return positions;
  }, [width, height]);

  // Store per-particle drift speeds
  const particleSpeeds = useMemo(() => {
    const speeds = new Float32Array(PARTICLE_COUNT * 3);
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      speeds[i * 3] = (Math.random() - 0.5) * 0.003;
      speeds[i * 3 + 1] = Math.random() * 0.002 + 0.001;
      speeds[i * 3 + 2] = (Math.random() - 0.5) * 0.001;
    }
    return speeds;
  }, []);

  // Animate particles floating upward and bars gently pulsing
  useFrame((_, delta) => {
    timeRef.current += delta;

    if (particlesRef.current) {
      const geo = particlesRef.current.geometry;
      const pos = geo.attributes.position as THREE.BufferAttribute;
      const halfW = (width - 0.04) / 2;
      const halfH = (height - 0.06) / 2;

      for (let i = 0; i < PARTICLE_COUNT; i++) {
        let x = pos.getX(i) + particleSpeeds[i * 3] * delta;
        let y = pos.getY(i) + particleSpeeds[i * 3 + 1] * delta;
        const z = pos.getZ(i) + particleSpeeds[i * 3 + 2] * delta;

        // Wrap particles that drift out of bounds
        if (y > halfH) y = -halfH;
        if (x > halfW) x = -halfW;
        if (x < -halfW) x = halfW;

        pos.setXYZ(i, x, y, Math.max(-0.03, Math.min(0.01, z)));
      }
      pos.needsUpdate = true;
    }

    // Gentle scale pulse on bars
    if (barsRef.current) {
      barsRef.current.children.forEach((child, i) => {
        if (child instanceof THREE.Mesh) {
          const pulse = 1.0 + Math.sin(timeRef.current * 1.5 + i * 0.8) * 0.03;
          child.scale.y = pulse;
        }
      });
    }
  });

  // Chart layout
  const maxValue = Math.max(...chartData.map((d) => d.value), 0.01);
  const chartAreaWidth = width - 0.08;
  const chartAreaHeight = height - 0.12;
  const barWidth = Math.min(0.04, chartAreaWidth / chartData.length - 0.01);
  const barDepth = 0.02;
  const spacing = chartAreaWidth / chartData.length;

  return (
    <group>
      {/* Title */}
      <Text
        position={[0, height / 2 - 0.02, 0.001]}
        fontSize={0.016}
        color="#ffffff"
        anchorX="center"
        anchorY="top"
        font={undefined}
      >
        Volumetric Data
      </Text>

      {/* Floating particles background */}
      <points ref={particlesRef} position={[0, 0, -0.005]}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[particlePositions, 3]}
            count={PARTICLE_COUNT}
          />
        </bufferGeometry>
        <pointsMaterial
          color="#aabbff"
          size={0.003}
          transparent
          opacity={0.4}
          sizeAttenuation
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </points>

      {/* 3D Bar chart */}
      <group ref={barsRef} position={[-(chartAreaWidth / 2) + spacing / 2, -(chartAreaHeight / 2) + 0.01, 0.01]}>
        {chartData.map((item, index) => {
          const barHeight = (item.value / maxValue) * (chartAreaHeight - 0.04);
          const x = index * spacing;

          return (
            <group key={item.label} position={[x, 0, 0]}>
              {/* 3D bar -- rounded box geometry with emissive glow */}
              <mesh position={[0, barHeight / 2, 0]}>
                <roundedBoxGeometry args={[barWidth, barHeight, barDepth, 4, 0.005]} />
                <meshStandardMaterial
                  color={item.color}
                  emissive={item.color}
                  emissiveIntensity={0.35}
                  transparent
                  opacity={0.85}
                  roughness={0.3}
                  metalness={0.1}
                />
              </mesh>

              {/* Bar glow halo */}
              <mesh position={[0, barHeight / 2, -0.005]}>
                <planeGeometry args={[barWidth + 0.015, barHeight + 0.015]} />
                <meshBasicMaterial
                  color={item.color}
                  transparent
                  opacity={0.08}
                  blending={THREE.AdditiveBlending}
                  depthWrite={false}
                />
              </mesh>

              {/* Value label above bar */}
              <Text
                position={[0, barHeight + 0.015, 0.01]}
                fontSize={0.009}
                color="#ffffff"
                anchorX="center"
                anchorY="bottom"
                font={undefined}
              >
                {Math.round(item.value * 100)}
              </Text>

              {/* Category label below */}
              <Text
                position={[0, -0.012, 0.01]}
                fontSize={0.008}
                color="#999999"
                anchorX="center"
                anchorY="top"
                font={undefined}
              >
                {item.label}
              </Text>
            </group>
          );
        })}
      </group>

      {/* Baseline */}
      <mesh position={[0, -(chartAreaHeight / 2) + 0.008, 0.005]}>
        <planeGeometry args={[chartAreaWidth + 0.01, 0.001]} />
        <meshBasicMaterial color="#555577" transparent opacity={0.5} />
      </mesh>
    </group>
  );
}
