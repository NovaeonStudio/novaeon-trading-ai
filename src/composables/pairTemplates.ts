import { t } from '@/i18n';

const pairTemplates = ref([
  {
    description: () => t('charts.pairTemplates.allUsdt'),
    pairs: ['.*/USDT'],
  },
  {
    description: () => t('charts.pairTemplates.allUsdtFutures'),
    pairs: ['.*/USDT:USDT'],
  },
]);

export function usePairTemplates() {
  return {
    // Descriptions are translated on read, so the list follows a language switch.
    pairTemplates: computed(() =>
      pairTemplates.value.map((x, idx) => ({ ...x, description: x.description(), idx })),
    ),
  };
}
