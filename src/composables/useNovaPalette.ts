/** Shared open state of the ⌘K command palette (opened by shortcut or the header button). */
const open = ref(false);

export function useNovaPalette() {
  return {
    paletteOpen: open,
    togglePalette: () => {
      open.value = !open.value;
    },
  };
}
