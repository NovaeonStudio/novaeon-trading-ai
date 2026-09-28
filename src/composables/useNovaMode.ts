/** Simple (default, plain language) vs Pro (full trader detail). Persisted per browser. */
const mode = useStorage<'simple' | 'pro'>('nova-mode', 'simple');

export function useNovaMode() {
  const simple = computed(() => mode.value === 'simple');
  return {
    mode,
    simple,
    toggleMode: () => {
      mode.value = mode.value === 'simple' ? 'pro' : 'simple';
    },
  };
}
