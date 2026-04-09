/**
 * Persistence layer for spatial workspace state.
 * Uses localStorage for panel layouts and IndexedDB for larger data.
 */

const LAYOUT_KEY = "spatial-workspace-layout";
const NOTES_KEY = "spatial-workspace-notes";

interface PanelLayout {
  id: string;
  type: string;
  position: [number, number, number];
  scale: number;
}

interface WorkspaceState {
  panels: PanelLayout[];
  lastSaved: number;
}

/** Save the current workspace layout. */
export function saveLayout(panels: PanelLayout[]): void {
  const state: WorkspaceState = {
    panels,
    lastSaved: Date.now(),
  };
  try {
    localStorage.setItem(LAYOUT_KEY, JSON.stringify(state));
  } catch {
    console.warn("Failed to save layout — storage may be full.");
  }
}

/** Load the saved workspace layout, if any. */
export function loadLayout(): PanelLayout[] | null {
  try {
    const raw = localStorage.getItem(LAYOUT_KEY);
    if (!raw) return null;
    const state: WorkspaceState = JSON.parse(raw);
    return state.panels;
  } catch {
    return null;
  }
}

/** Save note content by panel ID. */
export function saveNoteContent(panelId: string, content: string): void {
  try {
    const notes = loadAllNotes();
    notes[panelId] = content;
    localStorage.setItem(NOTES_KEY, JSON.stringify(notes));
  } catch {
    console.warn("Failed to save note content.");
  }
}

/** Load note content for a panel. */
export function loadNoteContent(panelId: string): string | null {
  const notes = loadAllNotes();
  return notes[panelId] ?? null;
}

/** Load all saved notes. */
function loadAllNotes(): Record<string, string> {
  try {
    const raw = localStorage.getItem(NOTES_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

/** Clear all saved workspace data. */
export function clearWorkspaceData(): void {
  try {
    localStorage.removeItem(LAYOUT_KEY);
    localStorage.removeItem(NOTES_KEY);
  } catch {
    // Ignore
  }
}
