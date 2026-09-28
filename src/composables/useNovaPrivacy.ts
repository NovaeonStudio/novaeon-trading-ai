/** App-wide privacy mode: blurs every element marked with the `nova-money` class. Persisted per browser. */
const privacy = useStorage('nova-privacy', false);

watch(
  privacy,
  (on) => {
    document.documentElement.classList.toggle('nova-privacy', on);
  },
  { immediate: true },
);

export function useNovaPrivacy() {
  return {
    privacy,
    togglePrivacy: () => {
      privacy.value = !privacy.value;
    },
  };
}
