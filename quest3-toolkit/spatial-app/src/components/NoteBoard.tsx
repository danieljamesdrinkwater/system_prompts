import { useState, useRef } from "react";
import { Text } from "@react-three/drei";
import type { Group } from "three";

interface NoteBoardProps {
  width: number;
  height: number;
}

interface StickyNote {
  id: string;
  text: string;
  color: string;
  position: [number, number];
}

const NOTE_COLORS = ["#FFE066", "#A3D9FF", "#FFB3BA", "#BAFFC9", "#E8DAEF"];
const NOTE_SIZE = 0.08;

/**
 * Spatial sticky note board — visionOS-style.
 * Displays colored sticky notes on a glass surface.
 * Tap to add notes, tap a note to edit.
 */
export function NoteBoard({ width, height }: NoteBoardProps) {
  const groupRef = useRef<Group>(null);
  const [notes, setNotes] = useState<StickyNote[]>([
    { id: "1", text: "Welcome to\nSpatial Workspace", color: NOTE_COLORS[0], position: [-0.08, 0.06] },
    { id: "2", text: "Pinch to\ninteract", color: NOTE_COLORS[1], position: [0.08, 0.06] },
    { id: "3", text: "Grab the bar\nto move panels", color: NOTE_COLORS[2], position: [0, -0.06] },
  ]);

  const handleBoardClick = (e: { point: { x: number; y: number }; stopPropagation: () => void }) => {
    e.stopPropagation();
    const newNote: StickyNote = {
      id: Date.now().toString(),
      text: "New note",
      color: NOTE_COLORS[Math.floor(Math.random() * NOTE_COLORS.length)],
      position: [
        (Math.random() - 0.5) * (width - NOTE_SIZE),
        (Math.random() - 0.5) * (height - NOTE_SIZE),
      ],
    };
    setNotes((prev) => [...prev, newNote]);
  };

  return (
    <group ref={groupRef}>
      {/* Title */}
      <Text
        position={[0, height / 2 - 0.02, 0.001]}
        fontSize={0.016}
        color="#ffffff"
        anchorX="center"
        anchorY="top"
        font={undefined}
      >
        Notes
      </Text>

      {/* Clickable board area */}
      <mesh onClick={handleBoardClick}>
        <planeGeometry args={[width, height - 0.04]} />
        <meshBasicMaterial transparent opacity={0} />
      </mesh>

      {/* Sticky notes */}
      {notes.map((note) => (
        <StickyNoteCard key={note.id} note={note} />
      ))}
    </group>
  );
}

function StickyNoteCard({ note }: { note: StickyNote }) {
  const [hovered, setHovered] = useState(false);

  return (
    <group
      position={[note.position[0], note.position[1], 0.003]}
      onPointerOver={() => setHovered(true)}
      onPointerOut={() => setHovered(false)}
    >
      {/* Note background */}
      <mesh>
        <planeGeometry args={[NOTE_SIZE, NOTE_SIZE]} />
        <meshPhysicalMaterial
          color={note.color}
          transparent
          opacity={hovered ? 0.95 : 0.85}
          roughness={0.8}
          metalness={0}
        />
      </mesh>

      {/* Shadow */}
      <mesh position={[0.002, -0.002, -0.001]}>
        <planeGeometry args={[NOTE_SIZE, NOTE_SIZE]} />
        <meshBasicMaterial color="#000000" transparent opacity={0.1} />
      </mesh>

      {/* Note text */}
      <Text
        position={[0, 0, 0.001]}
        fontSize={0.009}
        color="#333333"
        anchorX="center"
        anchorY="middle"
        maxWidth={NOTE_SIZE - 0.01}
        textAlign="center"
        font={undefined}
      >
        {note.text}
      </Text>
    </group>
  );
}
